"""Owner dashboard aggregates and owner/admin booking listings.

Date ranges are **turf-local** calendar dates: a booking belongs to the local date
of its ``start_at`` in its turf's timezone (computed in SQL with
``timezone(turf.timezone, start_at)::date``). When ``from``/``to`` are omitted each
turf uses its own local "today".

Formulas (PRP Module 5):

- occupancy % = booked minutes (confirmed + completed) / (open minutes x days -
  blocked minutes) x 100, rounded to 1 decimal.
- revenue = sum of ``total_amount`` of confirmed + completed bookings minus those
  whose payment has been refunded. Cancelled bookings never count as revenue, so
  ``refunds`` (sum of refunded bookings) is reported separately and not
  subtracted a second time.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from sqlalchemy import (
    Date,
    Integer,
    Select,
    case,
    cast,
    extract,
    func,
    literal,
    or_,
    select,
)
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.config import settings
from app.exceptions import BadRequestError, NotFoundError
from app.models import BlockedSlot, Booking, BookingStatus, RefundStatus, Turf, User
from app.schemas.booking import BookingRead
from app.schemas.common import PaginationParams
from app.schemas.dashboard import OwnerSummary, RevenuePoint
from app.services.availability import to_local_date
from app.services.booking_service import booking_load_options, paginate

MAX_RANGE_DAYS = 366
UPCOMING_LIMIT = 5
REVENUE_DEFAULT_DAYS = 30
EARNING_STATUSES = (BookingStatus.confirmed, BookingStatus.completed)

GroupBy = Literal["day", "week"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def booking_local_date() -> ColumnElement[date]:
    """SQL: the turf-local date of a booking's start (requires a join to ``turfs``)."""
    return cast(func.timezone(Turf.timezone, Booking.start_at), Date)


def _local_today(now: datetime) -> ColumnElement[date]:
    """SQL: each turf's local date at ``now``."""
    return cast(func.timezone(Turf.timezone, literal(now)), Date)


def _validate_range(date_from: date | None, date_to: date | None) -> None:
    """Reject inverted or overly long ranges with 400 ``INVALID_DATE_RANGE``."""
    if date_from is not None and date_to is not None:
        if date_from > date_to:
            raise BadRequestError("'from' must be on or before 'to'", code="INVALID_DATE_RANGE")
        if (date_to - date_from).days + 1 > MAX_RANGE_DAYS:
            raise BadRequestError(
                f"Date range cannot exceed {MAX_RANGE_DAYS} days", code="INVALID_DATE_RANGE"
            )


def owner_turfs(db: Session, owner: User, turf_id: int | None = None) -> list[Turf]:
    """Return the owner's turfs (optionally one), raising 404 for a foreign ``turf_id``."""
    stmt = select(Turf).where(Turf.owner_id == owner.id).order_by(Turf.id)
    if turf_id is not None:
        stmt = stmt.where(Turf.id == turf_id)
    turfs = list(db.execute(stmt).scalars().all())
    if turf_id is not None and not turfs:
        raise NotFoundError("Turf not found")
    return turfs


def _range_bounds(
    date_from: date | None, date_to: date | None, now: datetime
) -> tuple[ColumnElement[date], ColumnElement[date]]:
    """SQL lower/upper date bounds, falling back to each turf's local today."""
    today = _local_today(now)
    lower = literal(date_from, Date) if date_from is not None else today
    upper = literal(date_to, Date) if date_to is not None else today
    return lower, upper


def _open_minutes(
    turfs: Sequence[Turf], date_from: date | None, date_to: date | None, now: datetime
) -> int:
    """Sum of opening-hours minutes x days in range over ``turfs``."""
    total = 0
    for turf in turfs:
        today = to_local_date(turf, now)
        start = date_from or today
        end = date_to or today
        days = (end - start).days + 1
        opening = datetime.combine(today, turf.opening_time)
        closing = datetime.combine(today, turf.closing_time)
        total += int((closing - opening).total_seconds() // 60) * max(days, 0)
    return total


def owner_summary(
    db: Session,
    owner: User,
    date_from: date | None = None,
    date_to: date | None = None,
    turf_id: int | None = None,
    now: datetime | None = None,
) -> OwnerSummary:
    """Compute the owner's KPI summary with aggregate SQL (no per-booking queries)."""
    current = now or _utcnow()
    _validate_range(date_from, date_to)
    turfs = owner_turfs(db, owner, turf_id)
    currency = turfs[0].currency if turfs else settings.DEFAULT_CURRENCY
    if not turfs:
        return OwnerSummary(
            bookings_today=0,
            upcoming_bookings=[],
            occupancy_pct=0.0,
            revenue=0,
            refunds=0,
            cancellations=0,
            currency=currency,
        )
    turf_ids = [t.id for t in turfs]
    lower, upper = _range_bounds(date_from, date_to, current)
    local_date = booking_local_date()
    in_range = local_date.between(lower, upper)
    earning = Booking.status.in_(EARNING_STATUSES)
    not_refunded = Booking.refund_status != RefundStatus.refunded
    minutes = extract("epoch", Booking.end_at - Booking.start_at) / 60

    row = db.execute(
        select(
            func.count(Booking.id).filter(earning, local_date == _local_today(current)),
            func.coalesce(func.sum(minutes).filter(earning, in_range), 0),
            func.coalesce(
                func.sum(Booking.total_amount).filter(earning, not_refunded, in_range), 0
            ),
            func.coalesce(
                func.sum(Booking.total_amount).filter(
                    Booking.refund_status == RefundStatus.refunded, in_range
                ),
                0,
            ),
            func.count(Booking.id).filter(Booking.status == BookingStatus.cancelled, in_range),
        )
        .select_from(Booking)
        .join(Turf, Turf.id == Booking.turf_id)
        .where(Booking.turf_id.in_(turf_ids))
    ).one()
    bookings_today, booked_minutes, revenue, refunds, cancellations = row

    block_date = cast(func.timezone(Turf.timezone, BlockedSlot.start_at), Date)
    blocked_minutes = db.execute(
        select(
            func.coalesce(
                func.sum(extract("epoch", BlockedSlot.end_at - BlockedSlot.start_at) / 60), 0
            )
        )
        .select_from(BlockedSlot)
        .join(Turf, Turf.id == BlockedSlot.turf_id)
        .where(BlockedSlot.turf_id.in_(turf_ids), block_date.between(lower, upper))
    ).scalar_one()

    available = _open_minutes(turfs, date_from, date_to, current) - float(blocked_minutes)
    occupancy = round(float(booked_minutes) / available * 100, 1) if available > 0 else 0.0

    upcoming = (
        db.execute(
            select(Booking)
            .options(*booking_load_options())
            .where(
                Booking.turf_id.in_(turf_ids),
                Booking.status == BookingStatus.confirmed,
                Booking.start_at > current,
            )
            .order_by(Booking.start_at.asc(), Booking.id.asc())
            .limit(UPCOMING_LIMIT)
        )
        .unique()
        .scalars()
        .all()
    )
    return OwnerSummary(
        bookings_today=int(bookings_today),
        upcoming_bookings=[BookingRead.from_booking(b, current) for b in upcoming],
        occupancy_pct=occupancy,
        revenue=int(revenue),
        refunds=int(refunds),
        cancellations=int(cancellations),
        currency=currency,
    )


def revenue_series(
    db: Session,
    owner: User,
    date_from: date | None = None,
    date_to: date | None = None,
    group_by: GroupBy = "day",
    turf_id: int | None = None,
    now: datetime | None = None,
) -> list[RevenuePoint]:
    """Revenue and earning-booking counts per local day or ISO week (Monday start).

    Defaults to the last 30 local days. When both ``from`` and ``to`` are given,
    empty periods are filled with zeros.
    """
    current = now or _utcnow()
    _validate_range(date_from, date_to)
    turfs = owner_turfs(db, owner, turf_id)
    if not turfs:
        return []
    today = _local_today(current)
    lower: ColumnElement[date] = (
        literal(date_from, Date)
        if date_from is not None
        else cast(today - literal(REVENUE_DEFAULT_DAYS - 1, Integer), Date)
    )
    upper: ColumnElement[date] = literal(date_to, Date) if date_to is not None else today
    local_ts = func.timezone(Turf.timezone, Booking.start_at)
    bucket = cast(func.date_trunc(group_by, local_ts), Date).label("bucket")
    earning = Booking.status.in_(EARNING_STATUSES)
    revenue_expr = func.coalesce(
        func.sum(
            case((Booking.refund_status != RefundStatus.refunded, Booking.total_amount), else_=0)
        ),
        0,
    )
    rows = db.execute(
        select(bucket, revenue_expr, func.count(Booking.id))
        .select_from(Booking)
        .join(Turf, Turf.id == Booking.turf_id)
        .where(
            Booking.turf_id.in_([t.id for t in turfs]),
            earning,
            cast(local_ts, Date).between(lower, upper),
        )
        .group_by(bucket)
        .order_by(bucket)
    ).all()
    points = {
        r[0]: RevenuePoint(period_start=r[0], revenue=int(r[1]), bookings=int(r[2])) for r in rows
    }
    if date_from is not None and date_to is not None:
        step = timedelta(days=7 if group_by == "week" else 1)
        cursor = (
            date_from - timedelta(days=date_from.weekday()) if group_by == "week" else date_from
        )
        while cursor <= date_to:
            points.setdefault(cursor, RevenuePoint(period_start=cursor, revenue=0, bookings=0))
            cursor += step
    return [points[k] for k in sorted(points)]


# ---------------------------------------------------------------------------
# Listings
# ---------------------------------------------------------------------------


def _with_turf_join(stmt: Select[Booking]) -> Select[Booking]:
    """Join ``turfs`` so turf-local date filters can be applied."""
    return stmt.join(Turf, Turf.id == Booking.turf_id)


def list_owner_bookings(
    db: Session,
    owner: User,
    pagination: PaginationParams,
    turf_id: int | None = None,
    local_date: date | None = None,
    status: BookingStatus | None = None,
) -> tuple[list[Booking], int]:
    """Bookings on the owner's turfs, filtered by turf, turf-local date and status."""
    if turf_id is not None:
        owner_turfs(db, owner, turf_id)
    stmt = _with_turf_join(select(Booking)).where(Turf.owner_id == owner.id)
    if turf_id is not None:
        stmt = stmt.where(Booking.turf_id == turf_id)
    if local_date is not None:
        stmt = stmt.where(booking_local_date() == local_date)
    if status is not None:
        stmt = stmt.where(Booking.status == status)
    stmt = stmt.order_by(Booking.start_at.desc(), Booking.id.desc())
    return paginate(db, stmt, pagination)


def list_admin_bookings(
    db: Session,
    pagination: PaginationParams,
    status: BookingStatus | None = None,
    turf_id: int | None = None,
    q: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[list[Booking], int]:
    """All bookings with filters: status, turf, player name/email/booking ref, local dates."""
    _validate_range(date_from, None if date_from is None else date_to)
    stmt = _with_turf_join(select(Booking))
    if status is not None:
        stmt = stmt.where(Booking.status == status)
    if turf_id is not None:
        stmt = stmt.where(Booking.turf_id == turf_id)
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.join(User, User.id == Booking.player_id).where(
            or_(
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
                Booking.booking_ref.ilike(pattern),
            )
        )
    local_date = booking_local_date()
    if date_from is not None:
        stmt = stmt.where(local_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(local_date <= date_to)
    stmt = stmt.order_by(Booking.start_at.desc(), Booking.id.desc())
    return paginate(db, stmt, pagination)
