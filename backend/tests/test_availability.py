"""Unit tests for the availability engine (grid, statuses, prices, DST)."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    BlockedSlot,
    Booking,
    BookingStatus,
    Turf,
    TurfPricingRule,
    User,
    UserRole,
)
from app.services.availability import (
    booking_window,
    get_day_slots,
    is_grid_aligned,
    local_day_grid,
    resolve_slot_price,
    to_local_date,
    turf_ids_with_availability,
)


def _turf(**overrides: Any) -> Turf:
    """Build an unsaved turf for pure-function tests."""
    values: dict[str, Any] = {
        "id": 1,
        "timezone": "Asia/Kolkata",
        "slot_duration_minutes": 60,
        "opening_time": time(6, 0),
        "closing_time": time(23, 0),
        "base_price": 1000,
        "currency": "INR",
    }
    values.update(overrides)
    return Turf(**values)


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def _rule(day: int | None, start: time, end: time, price: int) -> TurfPricingRule:
    return TurfPricingRule(day_of_week=day, start_time=start, end_time=end, price=price)


# ---------------------------------------------------------------------------
# Grid
# ---------------------------------------------------------------------------


def test_grid_60_minutes_kolkata() -> None:
    grid = local_day_grid(_turf(), date(2026, 11, 20))
    assert len(grid) == 17
    # 06:00 IST == 00:30 UTC
    assert grid[0] == (_utc(2026, 11, 20, 0, 30), _utc(2026, 11, 20, 1, 30))
    # last slot 22:00-23:00 IST == 16:30-17:30 UTC
    assert grid[-1] == (_utc(2026, 11, 20, 16, 30), _utc(2026, 11, 20, 17, 30))
    for (_, end), (start, _) in itertools.pairwise(grid):
        assert end == start


def test_grid_90_minutes_stops_at_closing_boundary() -> None:
    turf = _turf(slot_duration_minutes=90, opening_time=time(6, 0), closing_time=time(10, 0))
    grid = local_day_grid(turf, date(2026, 11, 20))
    # 06:00-07:30, 07:30-09:00; 09:00-10:30 would exceed closing.
    assert len(grid) == 2
    assert grid[-1][1] == _utc(2026, 11, 20, 3, 30)  # 09:00 IST


def test_grid_30_minutes_exact_closing() -> None:
    turf = _turf(slot_duration_minutes=30, opening_time=time(8, 0), closing_time=time(10, 0))
    grid = local_day_grid(turf, date(2026, 11, 20))
    assert len(grid) == 4
    assert all(end - start == timedelta(minutes=30) for start, end in grid)
    assert grid[-1][1] == _utc(2026, 11, 20, 4, 30)  # 10:00 IST


def test_grid_too_short_day_is_empty() -> None:
    turf = _turf(slot_duration_minutes=90, opening_time=time(6, 0), closing_time=time(7, 0))
    assert local_day_grid(turf, date(2026, 11, 20)) == []


def test_grid_dst_spring_forward_london() -> None:
    turf = _turf(timezone="Europe/London", opening_time=time(0, 0), closing_time=time(5, 0))
    grid = local_day_grid(turf, date(2026, 3, 29))
    # 01:00 local does not exist -> skipped; 02:00 BST == 01:00 UTC.
    assert [s for s, _ in grid] == [
        _utc(2026, 3, 29, 0),
        _utc(2026, 3, 29, 1),
        _utc(2026, 3, 29, 2),
        _utc(2026, 3, 29, 3),
    ]
    assert all(end - start == timedelta(hours=1) for start, end in grid)


def test_grid_dst_spring_forward_90_minutes_never_overlaps() -> None:
    turf = _turf(
        timezone="Europe/London",
        slot_duration_minutes=90,
        opening_time=time(0, 30),
        closing_time=time(5, 0),
    )
    grid = local_day_grid(turf, date(2026, 3, 29))
    assert grid == [
        (_utc(2026, 3, 29, 0, 30), _utc(2026, 3, 29, 2, 0)),
        (_utc(2026, 3, 29, 2, 30), _utc(2026, 3, 29, 4, 0)),
    ]


def test_grid_dst_fall_back_london_uses_first_occurrence() -> None:
    turf = _turf(timezone="Europe/London", opening_time=time(0, 0), closing_time=time(4, 0))
    grid = local_day_grid(turf, date(2026, 10, 25))
    assert [s for s, _ in grid] == [
        _utc(2026, 10, 24, 23),  # 00:00 BST
        _utc(2026, 10, 25, 0),  # 01:00 BST (fold=0)
        _utc(2026, 10, 25, 2),  # 02:00 GMT
        _utc(2026, 10, 25, 3),  # 03:00 GMT
    ]


def test_grid_regular_london_day_offsets() -> None:
    turf = _turf(timezone="Europe/London", opening_time=time(9, 0), closing_time=time(11, 0))
    summer = local_day_grid(turf, date(2026, 7, 1))
    winter = local_day_grid(turf, date(2026, 12, 1))
    assert summer[0][0] == _utc(2026, 7, 1, 8)
    assert winter[0][0] == _utc(2026, 12, 1, 9)


# ---------------------------------------------------------------------------
# Local date / alignment / window
# ---------------------------------------------------------------------------


def test_to_local_date_crosses_midnight_kolkata() -> None:
    turf = _turf()
    assert to_local_date(turf, _utc(2026, 11, 20, 18, 45)) == date(2026, 11, 21)
    assert to_local_date(turf, _utc(2026, 11, 20, 18, 15)) == date(2026, 11, 20)
    # naive values are treated as UTC
    assert to_local_date(turf, datetime(2026, 11, 20, 18, 45)) == date(2026, 11, 21)


def test_is_grid_aligned() -> None:
    turf = _turf()
    assert is_grid_aligned(turf, _utc(2026, 11, 20, 0, 30))
    assert is_grid_aligned(turf, _utc(2026, 11, 20, 16, 30))
    assert not is_grid_aligned(turf, _utc(2026, 11, 20, 1, 0))
    assert not is_grid_aligned(turf, _utc(2026, 11, 20, 17, 30))  # closing time
    assert not is_grid_aligned(turf, _utc(2026, 11, 20, 0, 0))  # before opening


def test_booking_window() -> None:
    turf = _turf()
    start, end = booking_window(turf, _utc(2026, 11, 20, 19, 0))  # 00:30 IST on the 21st
    assert start == date(2026, 11, 21)
    assert end == date(2026, 11, 21) + timedelta(days=settings.BOOKING_WINDOW_DAYS)


# ---------------------------------------------------------------------------
# Price resolution
# ---------------------------------------------------------------------------


def test_price_falls_back_to_base() -> None:
    assert resolve_slot_price(_turf(), [], _utc(2026, 11, 20, 0, 30)) == 1000


def test_price_every_day_rule_and_boundaries() -> None:
    turf = _turf()
    rules = [_rule(None, time(18, 0), time(21, 0), 1500)]
    # 18:00 IST == 12:30 UTC -> rule start is inclusive
    assert resolve_slot_price(turf, rules, _utc(2026, 11, 20, 12, 30)) == 1500
    # 20:00 IST -> inside
    assert resolve_slot_price(turf, rules, _utc(2026, 11, 20, 14, 30)) == 1500
    # 21:00 IST -> end is exclusive
    assert resolve_slot_price(turf, rules, _utc(2026, 11, 20, 15, 30)) == 1000


def test_price_specific_day_beats_every_day() -> None:
    turf = _turf()
    # 2026-11-21 is a Saturday (5).
    rules = [
        _rule(None, time(18, 0), time(21, 0), 1500),
        _rule(5, time(18, 0), time(19, 0), 2000),
    ]
    assert resolve_slot_price(turf, rules, _utc(2026, 11, 21, 12, 30)) == 2000
    # Saturday 19:00 -> only every-day rule matches
    assert resolve_slot_price(turf, rules, _utc(2026, 11, 21, 13, 30)) == 1500
    # Friday 18:00 -> every-day rule
    assert resolve_slot_price(turf, rules, _utc(2026, 11, 20, 12, 30)) == 1500
    # Order independence
    assert resolve_slot_price(turf, list(reversed(rules)), _utc(2026, 11, 21, 12, 30)) == 2000


def test_price_uses_local_weekday() -> None:
    turf = _turf()
    rules = [_rule(5, time(0, 0), time(23, 59), 3000)]  # Saturday only
    # 2026-11-20 19:00 UTC is Saturday 00:30 IST
    assert resolve_slot_price(turf, rules, _utc(2026, 11, 20, 19, 0)) == 3000
    # 2026-11-20 18:00 UTC is Friday 23:30 IST
    assert resolve_slot_price(turf, rules, _utc(2026, 11, 20, 18, 0)) == 1000


# ---------------------------------------------------------------------------
# get_day_slots against the database
# ---------------------------------------------------------------------------

DAY = date(2026, 11, 20)  # Kolkata turf: 06:00 IST == 00:30 UTC


def _slot_utc(hour_local: int) -> datetime:
    """UTC start of the Kolkata slot starting at ``hour_local``:00 on DAY."""
    return datetime(2026, 11, 20, hour_local, 0, tzinfo=UTC) - timedelta(hours=5, minutes=30)


@pytest.fixture()
def owner(make_user: Callable[..., User]) -> User:
    return make_user(UserRole.owner)


@pytest.fixture()
def player(make_user: Callable[..., User]) -> User:
    return make_user(UserRole.player)


@pytest.fixture()
def add_booking(db: Session, player: User) -> Callable[..., Booking]:
    counter = {"n": 0}

    def _add(
        turf: Turf,
        start: datetime,
        slots: int = 1,
        status: BookingStatus = BookingStatus.confirmed,
        hold_expires_at: datetime | None = None,
    ) -> Booking:
        counter["n"] += 1
        booking = Booking(
            booking_ref=f"AV{counter['n']:06d}",
            player_id=player.id,
            turf_id=turf.id,
            start_at=start,
            end_at=start + timedelta(minutes=turf.slot_duration_minutes * slots),
            slot_count=slots,
            total_amount=1000 * slots,
            currency="INR",
            status=status,
            hold_expires_at=hold_expires_at,
        )
        db.add(booking)
        db.commit()
        return booking

    return _add


def test_get_day_slots_statuses_and_precedence(
    db: Session,
    owner: User,
    make_turf: Callable[..., Turf],
    add_booking: Callable[..., Booking],
) -> None:
    turf = make_turf(owner, base_price=1000)
    now = _slot_utc(8) + timedelta(minutes=10)  # 08:10 IST
    add_booking(turf, _slot_utc(10), status=BookingStatus.confirmed)
    add_booking(
        turf,
        _slot_utc(11),
        status=BookingStatus.pending,
        hold_expires_at=now + timedelta(minutes=5),
    )
    add_booking(  # expired hold -> available
        turf,
        _slot_utc(12),
        status=BookingStatus.pending,
        hold_expires_at=now - timedelta(minutes=1),
    )
    add_booking(turf, _slot_utc(13), status=BookingStatus.cancelled)
    add_booking(turf, _slot_utc(14), status=BookingStatus.expired)
    # past + booked -> past
    add_booking(turf, _slot_utc(7), status=BookingStatus.confirmed)
    db.add(
        BlockedSlot(
            turf_id=turf.id, start_at=_slot_utc(15), end_at=_slot_utc(17), created_by=owner.id
        )
    )
    db.commit()

    day = get_day_slots(db, turf, DAY, now)
    by_hour = {(s.start_at + timedelta(hours=5, minutes=30)).hour: s.status for s in day.slots}
    assert day.turf_id == turf.id
    assert day.date == DAY
    assert day.timezone == "Asia/Kolkata"
    assert day.currency == "INR"
    assert len(day.slots) == 17
    assert by_hour[6] == "past"
    assert by_hour[7] == "past"
    assert by_hour[8] == "past"  # started at 08:00 <= now
    assert by_hour[9] == "available"
    assert by_hour[10] == "booked"
    assert by_hour[11] == "held"
    assert by_hour[12] == "available"
    assert by_hour[13] == "available"
    assert by_hour[14] == "available"
    assert by_hour[15] == "blocked"
    assert by_hour[16] == "blocked"
    assert by_hour[17] == "available"


def test_get_day_slots_block_beats_booking(
    db: Session,
    owner: User,
    make_turf: Callable[..., Turf],
    add_booking: Callable[..., Booking],
) -> None:
    turf = make_turf(owner)
    add_booking(turf, _slot_utc(10), status=BookingStatus.confirmed)
    db.add(
        BlockedSlot(
            turf_id=turf.id, start_at=_slot_utc(10), end_at=_slot_utc(11), created_by=owner.id
        )
    )
    db.commit()
    day = get_day_slots(db, turf, DAY, _slot_utc(6) - timedelta(days=1))
    assert day.slots[4].status == "blocked"


def test_get_day_slots_multi_slot_booking_and_prices(
    db: Session,
    owner: User,
    make_turf: Callable[..., Turf],
    add_booking: Callable[..., Booking],
) -> None:
    turf = make_turf(owner, base_price=1000)
    db.add(
        TurfPricingRule(
            turf_id=turf.id, day_of_week=None, start_time=time(18), end_time=time(21), price=1500
        )
    )
    db.commit()
    db.refresh(turf)
    add_booking(turf, _slot_utc(18), slots=2, status=BookingStatus.confirmed)
    day = get_day_slots(db, turf, DAY, _slot_utc(6) - timedelta(days=1))
    by_hour = {(s.start_at + timedelta(hours=5, minutes=30)).hour: s for s in day.slots}
    assert by_hour[18].status == "booked"
    assert by_hour[19].status == "booked"
    assert by_hour[20].status == "available"
    assert by_hour[17].price == 1000
    assert by_hour[18].price == 1500
    assert by_hour[20].price == 1500
    assert by_hour[21].price == 1000


def test_get_day_slots_ignores_other_turfs_and_days(
    db: Session,
    owner: User,
    make_turf: Callable[..., Turf],
    add_booking: Callable[..., Booking],
) -> None:
    turf = make_turf(owner)
    other = make_turf(owner)
    add_booking(other, _slot_utc(10))
    add_booking(turf, _slot_utc(10) + timedelta(days=1))
    day = get_day_slots(db, turf, DAY, _slot_utc(6) - timedelta(days=1))
    assert {s.status for s in day.slots} == {"available"}


def test_get_day_slots_empty_grid(db: Session, owner: User, make_turf: Callable[..., Turf]) -> None:
    turf = make_turf(owner, slot_duration_minutes=90, opening_time=time(6), closing_time=time(7))
    day = get_day_slots(db, turf, DAY)
    assert day.slots == []


def test_day_slots_json_serialization(
    db: Session, owner: User, make_turf: Callable[..., Turf]
) -> None:
    turf = make_turf(owner)
    payload = get_day_slots(db, turf, DAY, _slot_utc(6) - timedelta(days=1)).model_dump(mode="json")
    assert payload["date"] == "2026-11-20"
    assert payload["slots"][0]["start_at"] == "2026-11-20T00:30:00Z"
    assert payload["slots"][0]["end_at"] == "2026-11-20T01:30:00Z"


def test_turf_ids_with_availability(
    db: Session,
    owner: User,
    make_turf: Callable[..., Turf],
    add_booking: Callable[..., Booking],
) -> None:
    free = make_turf(owner)
    full = make_turf(owner, opening_time=time(10), closing_time=time(12))
    blocked = make_turf(owner, opening_time=time(10), closing_time=time(11))
    add_booking(full, _slot_utc(10), slots=2)
    db.add(
        BlockedSlot(
            turf_id=blocked.id, start_at=_slot_utc(10), end_at=_slot_utc(11), created_by=owner.id
        )
    )
    db.commit()
    now = _slot_utc(6) - timedelta(days=1)
    assert turf_ids_with_availability(db, [free, full, blocked], DAY, now) == {free.id}
    # Outside the booking window -> nothing
    far = DAY + timedelta(days=settings.BOOKING_WINDOW_DAYS + 5)
    assert turf_ids_with_availability(db, [free], far, now) == set()
    # All slots in the past -> nothing
    assert turf_ids_with_availability(db, [free], DAY, _slot_utc(23)) == set()
