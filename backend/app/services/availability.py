"""Timezone-aware slot engine: day grids, price resolution and slot statuses.

All public functions take/return UTC-aware datetimes. A turf's slot grid is built
from local wall-clock times in ``ZoneInfo(turf.timezone)`` and then converted to UTC:

* Grid starts are ``opening_time + k * slot_duration`` while the local wall-clock
  slot end is ``<= closing_time``.
* Each slot lasts exactly ``slot_duration_minutes`` of real (UTC) time, so
  ``end_at = start_at + duration``.
* DST: a local start time that does not exist (spring-forward gap) is skipped;
  an ambiguous local time (fall-back) uses ``fold=0`` (the first occurrence).
  A slot that would overlap the previous kept slot (only possible around a
  spring-forward transition with 90-minute slots) is dropped, so grid slots
  never overlap. Always take a slot's ``end_at`` from the grid.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import BlockedSlot, Booking, BookingStatus, Turf, TurfPricingRule
from app.schemas.slot import DaySlots, SlotRead, SlotStatus

logger = logging.getLogger(__name__)

__all__ = [
    "booking_window",
    "compute_slot_statuses",
    "get_day_slots",
    "is_grid_aligned",
    "local_day_grid",
    "resolve_slot_price",
    "to_local_date",
    "turf_ids_with_availability",
]


@dataclass(frozen=True, slots=True)
class _BookingSpan:
    """Minimal booking data needed to compute slot statuses."""

    turf_id: int
    start_at: datetime
    end_at: datetime
    status: BookingStatus
    hold_expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class _BlockSpan:
    """Minimal blocked-range data needed to compute slot statuses."""

    turf_id: int
    start_at: datetime
    end_at: datetime


def _as_utc(value: datetime) -> datetime:
    """Return ``value`` as a UTC-aware datetime (naive values are assumed UTC)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _local_to_utc(naive_local: datetime, tz: ZoneInfo) -> datetime | None:
    """Convert a naive local wall time to UTC, or None if it does not exist (DST gap)."""
    aware = naive_local.replace(tzinfo=tz, fold=0)
    as_utc = aware.astimezone(UTC)
    if as_utc.astimezone(tz).replace(tzinfo=None) != naive_local:
        return None
    return as_utc


def local_day_grid(turf: Turf, local_date: date) -> list[tuple[datetime, datetime]]:
    """Return the UTC ``(start_at, end_at)`` pairs of every slot on a turf-local date.

    Args:
        turf: The turf (uses ``timezone``, ``opening_time``, ``closing_time`` and
            ``slot_duration_minutes``).
        local_date: Calendar date in the turf's timezone.

    Returns:
        Chronologically ordered, non-overlapping UTC-aware slot ranges.
    """
    tz = ZoneInfo(turf.timezone)
    duration = timedelta(minutes=turf.slot_duration_minutes)
    day_close = datetime.combine(local_date, turf.closing_time)
    cursor = datetime.combine(local_date, turf.opening_time)
    grid: list[tuple[datetime, datetime]] = []
    while cursor + duration <= day_close:
        start_utc = _local_to_utc(cursor, tz)
        if start_utc is not None and (not grid or start_utc >= grid[-1][1]):
            grid.append((start_utc, start_utc + duration))
        cursor += duration
    return grid


def to_local_date(turf: Turf, dt_utc: datetime) -> date:
    """Return the turf-local calendar date of a UTC instant."""
    return _as_utc(dt_utc).astimezone(ZoneInfo(turf.timezone)).date()


def is_grid_aligned(turf: Turf, start_at_utc: datetime) -> bool:
    """Return True if ``start_at_utc`` is the start of a slot in the turf's grid."""
    start = _as_utc(start_at_utc)
    return any(
        slot_start == start for slot_start, _ in local_day_grid(turf, to_local_date(turf, start))
    )


def resolve_slot_price(
    turf: Turf, rules: Sequence[TurfPricingRule], slot_start_utc: datetime
) -> int:
    """Return the price (minor units) of the slot starting at ``slot_start_utc``.

    A rule applies when ``start_time <= local start time < end_time``. A rule for
    the slot's specific local weekday (0=Mon..6=Sun) beats an every-day
    (``day_of_week is None``) rule; with no matching rule ``turf.base_price`` applies.
    """
    local = _as_utc(slot_start_utc).astimezone(ZoneInfo(turf.timezone))
    weekday = local.weekday()
    local_time = local.time().replace(tzinfo=None)
    every_day_price: int | None = None
    for rule in rules:
        if not rule.start_time <= local_time < rule.end_time:
            continue
        if rule.day_of_week == weekday:
            return rule.price
        if rule.day_of_week is None and every_day_price is None:
            every_day_price = rule.price
    return every_day_price if every_day_price is not None else turf.base_price


def booking_window(turf: Turf, now_utc: datetime) -> tuple[date, date]:
    """Return ``(today_local, today_local + BOOKING_WINDOW_DAYS)`` for the turf."""
    today = to_local_date(turf, now_utc)
    return today, today + timedelta(days=settings.BOOKING_WINDOW_DAYS)


def _overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """Half-open range overlap test: ``[a_start, a_end) && [b_start, b_end)``."""
    return a_start < b_end and b_start < a_end


def compute_slot_statuses(
    grid: Sequence[tuple[datetime, datetime]],
    bookings: Iterable[_BookingSpan],
    blocks: Iterable[_BlockSpan],
    now_utc: datetime,
) -> list[SlotStatus]:
    """Compute the status of each grid slot (pure function).

    Precedence: ``past`` (start <= now) > ``blocked`` > ``booked`` (confirmed) >
    ``held`` (pending with ``hold_expires_at > now``) > ``available``.
    """
    now = _as_utc(now_utc)
    booking_list = list(bookings)
    block_list = list(blocks)
    statuses: list[SlotStatus] = []
    for start, end in grid:
        status: SlotStatus
        if start <= now:
            status = "past"
        elif any(_overlaps(start, end, b.start_at, b.end_at) for b in block_list):
            status = "blocked"
        elif any(
            b.status == BookingStatus.confirmed and _overlaps(start, end, b.start_at, b.end_at)
            for b in booking_list
        ):
            status = "booked"
        elif any(
            b.status == BookingStatus.pending
            and b.hold_expires_at is not None
            and _as_utc(b.hold_expires_at) > now
            and _overlaps(start, end, b.start_at, b.end_at)
            for b in booking_list
        ):
            status = "held"
        else:
            status = "available"
        statuses.append(status)
    return statuses


def _load_spans(
    db: Session, turf_ids: Sequence[int], range_start: datetime, range_end: datetime
) -> tuple[list[_BookingSpan], list[_BlockSpan]]:
    """Fetch active bookings and blocks overlapping a UTC range (one query each)."""
    booking_rows = db.execute(
        select(
            Booking.turf_id,
            Booking.start_at,
            Booking.end_at,
            Booking.status,
            Booking.hold_expires_at,
        ).where(
            Booking.turf_id.in_(turf_ids),
            Booking.status.in_((BookingStatus.pending, BookingStatus.confirmed)),
            Booking.start_at < range_end,
            Booking.end_at > range_start,
        )
    ).all()
    block_rows = db.execute(
        select(BlockedSlot.turf_id, BlockedSlot.start_at, BlockedSlot.end_at).where(
            BlockedSlot.turf_id.in_(turf_ids),
            BlockedSlot.start_at < range_end,
            BlockedSlot.end_at > range_start,
        )
    ).all()
    bookings = [
        _BookingSpan(
            turf_id=row.turf_id,
            start_at=_as_utc(row.start_at),
            end_at=_as_utc(row.end_at),
            status=BookingStatus(row.status),
            hold_expires_at=_as_utc(row.hold_expires_at) if row.hold_expires_at else None,
        )
        for row in booking_rows
    ]
    blocks = [
        _BlockSpan(turf_id=row.turf_id, start_at=_as_utc(row.start_at), end_at=_as_utc(row.end_at))
        for row in block_rows
    ]
    return bookings, blocks


def get_day_slots(
    db: Session, turf: Turf, local_date: date, now_utc: datetime | None = None
) -> DaySlots:
    """Return every slot of ``turf`` on ``local_date`` with its status and price.

    Runs one query for bookings and one for blocks over the day's UTC range
    (plus the lazy load of ``turf.pricing_rules`` if not already loaded).
    """
    now = _as_utc(now_utc) if now_utc is not None else datetime.now(UTC)
    grid = local_day_grid(turf, local_date)
    slots: list[SlotRead] = []
    if grid:
        bookings, blocks = _load_spans(db, [turf.id], grid[0][0], grid[-1][1])
        statuses = compute_slot_statuses(grid, bookings, blocks, now)
        rules = list(turf.pricing_rules)
        slots = [
            SlotRead(
                start_at=start,
                end_at=end,
                status=status,
                price=resolve_slot_price(turf, rules, start),
            )
            for (start, end), status in zip(grid, statuses, strict=True)
        ]
    return DaySlots(
        turf_id=turf.id,
        date=local_date,
        timezone=turf.timezone,
        currency=turf.currency,
        slots=slots,
    )


def turf_ids_with_availability(
    db: Session, turfs: Sequence[Turf], local_date: date, now_utc: datetime | None = None
) -> set[int]:
    """Return ids of turfs with at least one ``available`` slot on ``local_date``.

    Dates outside a turf's booking window count as unavailable. Uses one bookings
    query and one blocks query for all turfs together.
    """
    now = _as_utc(now_utc) if now_utc is not None else datetime.now(UTC)
    grids: dict[int, list[tuple[datetime, datetime]]] = {}
    for turf in turfs:
        window_start, window_end = booking_window(turf, now)
        if not window_start <= local_date <= window_end:
            continue
        grid = [slot for slot in local_day_grid(turf, local_date) if slot[0] > now]
        if grid:
            grids[turf.id] = grid
    if not grids:
        return set()
    range_start = min(grid[0][0] for grid in grids.values())
    range_end = max(grid[-1][1] for grid in grids.values())
    bookings, blocks = _load_spans(db, list(grids), range_start, range_end)
    result: set[int] = set()
    for turf_id, grid in grids.items():
        turf_bookings = [b for b in bookings if b.turf_id == turf_id]
        turf_blocks = [b for b in blocks if b.turf_id == turf_id]
        if "available" in compute_slot_statuses(grid, turf_bookings, turf_blocks, now):
            result.add(turf_id)
    return result
