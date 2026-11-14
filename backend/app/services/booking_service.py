"""Booking lifecycle: creation (concurrency-safe), checkout, state machine, cancellation.

Double booking is prevented by the ``bookings_no_overlap`` exclusion constraint; an
INSERT/UPDATE that violates it raises ``IntegrityError`` with SQLSTATE ``23P01``,
which is mapped to 409 ``SLOT_UNAVAILABLE``.
"""

from __future__ import annotations

import logging
import secrets
import string
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise

from sqlalchemy import ColumnElement, Select, and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.sql.base import ExecutableOption

from app.config import settings
from app.exceptions import (
    AppError,
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.models import (
    BlockedSlot,
    Booking,
    BookingStatus,
    CancelledBy,
    Payment,
    PaymentStatus,
    RefundStatus,
    Turf,
    User,
    UserRole,
)
from app.schemas.booking import BookingCreate
from app.schemas.common import PaginationParams
from app.services.availability import (
    booking_window,
    local_day_grid,
    resolve_slot_price,
    to_local_date,
)
from app.services.booking_notifications import EmailJob, booking_cancelled_jobs
from app.services.payment_gateway import PaymentGateway, PaymentGatewayError

logger = logging.getLogger(__name__)

EXCLUSION_VIOLATION = "23P01"
UNIQUE_VIOLATION = "23505"
BOOKING_REF_ALPHABET = string.ascii_uppercase + string.digits
BOOKING_REF_LENGTH = 8
_MAX_REF_ATTEMPTS = 5

ALLOWED_TRANSITIONS: dict[BookingStatus, frozenset[BookingStatus]] = {
    BookingStatus.pending: frozenset(
        {BookingStatus.confirmed, BookingStatus.cancelled, BookingStatus.expired}
    ),
    BookingStatus.confirmed: frozenset({BookingStatus.cancelled, BookingStatus.completed}),
    BookingStatus.cancelled: frozenset(),
    BookingStatus.completed: frozenset(),
    BookingStatus.expired: frozenset(),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def utcnow() -> datetime:
    """Current time as an aware UTC datetime."""
    return datetime.now(UTC)


def sqlstate(exc: IntegrityError) -> str | None:
    """Return the PostgreSQL SQLSTATE of a DBAPI error wrapped by SQLAlchemy."""
    orig = exc.orig
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


def is_exclusion_violation(exc: IntegrityError) -> bool:
    """True if the error is an exclusion-constraint violation (double booking)."""
    return sqlstate(exc) == EXCLUSION_VIOLATION


def generate_booking_ref() -> str:
    """Return a random 8-character uppercase alphanumeric booking reference."""
    return "".join(secrets.choice(BOOKING_REF_ALPHABET) for _ in range(BOOKING_REF_LENGTH))


def can_transition(current: BookingStatus, target: BookingStatus) -> bool:
    """Return True if the state machine allows ``current -> target``."""
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


def transition(booking: Booking, target: BookingStatus) -> None:
    """Move ``booking`` to ``target`` or raise 409 ``INVALID_TRANSITION``."""
    if not can_transition(booking.status, target):
        raise ConflictError(
            f"Cannot change booking from {booking.status.value} to {target.value}",
            code="INVALID_TRANSITION",
        )
    booking.status = target


def booking_load_options() -> tuple[ExecutableOption, ...]:
    """Eager-load options for building ``BookingRead`` (turf + player) without N+1."""
    return (joinedload(Booking.turf), joinedload(Booking.player))


def _booking_query() -> Select[Booking]:
    """Base SELECT for bookings with turf, turf owner and player eagerly loaded."""
    return select(Booking).options(
        joinedload(Booking.turf).joinedload(Turf.owner), joinedload(Booking.player)
    )


def get_booking_with_relations(db: Session, booking_id: int) -> Booking | None:
    """Fetch a booking with turf (+owner) and player loaded."""
    return (
        db.execute(_booking_query().where(Booking.id == booking_id)).unique().scalar_one_or_none()
    )


def get_visible_booking(db: Session, booking_id: int, user: User) -> Booking:
    """Return a booking the user may see (player, turf owner or admin) or raise 404.

    A 404 (not 403) is used so that booking ids are not leaked.
    """
    booking = get_booking_with_relations(db, booking_id)
    if booking is None or not _can_view(booking, user):
        raise NotFoundError("Booking not found")
    return booking


def _can_view(booking: Booking, user: User) -> bool:
    """Player, owner of the booked turf, or admin."""
    return (
        user.role == UserRole.admin
        or booking.player_id == user.id
        or booking.turf.owner_id == user.id
    )


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class CheckoutOutcome:
    """A booking plus the hosted checkout URL to redirect the player to."""

    booking: Booking
    checkout_url: str


@dataclass(slots=True)
class _SlotPlan:
    start_at: datetime
    end_at: datetime
    slot_starts: list[datetime] = field(default_factory=list)
    local_date: date | None = None


def _plan_slots(turf: Turf, start_at: datetime, slot_count: int) -> _SlotPlan:
    """Validate grid alignment / opening hours and return the consecutive slot range."""
    local_date = to_local_date(turf, start_at)
    grid = local_day_grid(turf, local_date)
    index = next((i for i, (s, _) in enumerate(grid) if s == start_at), None)
    if index is None:
        raise BadRequestError(
            "start_at must be the start of a slot on this turf", code="SLOT_NOT_ALIGNED"
        )
    chosen = grid[index : index + slot_count]
    if len(chosen) < slot_count:
        raise BadRequestError(
            "The requested slots run past the turf's closing time",
            code="OUTSIDE_OPENING_HOURS",
        )
    for (_, prev_end), (next_start, _) in pairwise(chosen):
        if prev_end != next_start:
            raise BadRequestError("Slots must be consecutive", code="SLOTS_NOT_CONSECUTIVE")
    return _SlotPlan(
        start_at=chosen[0][0],
        end_at=chosen[-1][1],
        slot_starts=[s for s, _ in chosen],
        local_date=local_date,
    )


def _validate_request(
    db: Session, player: User, data: BookingCreate, now: datetime
) -> tuple[Turf, _SlotPlan]:
    """Run every booking validation rule and return the turf and the slot plan."""
    if not player.is_verified:
        raise ForbiddenError("Please verify your email address first", code="EMAIL_NOT_VERIFIED")
    turf = db.execute(
        select(Turf).options(selectinload(Turf.pricing_rules)).where(Turf.id == data.turf_id)
    ).scalar_one_or_none()
    if turf is None or not turf.is_active:
        raise NotFoundError("Turf not found")
    if turf.owner_id == player.id:
        raise BadRequestError("You cannot book your own turf", code="OWN_TURF")
    if not 1 <= data.slot_count <= settings.MAX_SLOTS_PER_BOOKING:
        raise BadRequestError(
            f"slot_count must be between 1 and {settings.MAX_SLOTS_PER_BOOKING}",
            code="INVALID_SLOT_COUNT",
        )
    start_at = data.start_at.astimezone(UTC)
    if start_at <= now:
        raise BadRequestError("Cannot book a slot in the past", code="SLOT_IN_PAST")
    plan = _plan_slots(turf, start_at, data.slot_count)
    window_start, window_end = booking_window(turf, now)
    if plan.local_date is None or not window_start <= plan.local_date <= window_end:
        raise BadRequestError(
            f"Bookings are only allowed up to {settings.BOOKING_WINDOW_DAYS} days ahead",
            code="OUTSIDE_BOOKING_WINDOW",
        )
    blocked = db.execute(
        select(BlockedSlot.id).where(
            BlockedSlot.turf_id == turf.id,
            BlockedSlot.start_at < plan.end_at,
            BlockedSlot.end_at > plan.start_at,
        )
    ).first()
    if blocked is not None:
        raise ConflictError("One or more slots are blocked", code="SLOT_UNAVAILABLE")
    return turf, plan


def expire_stale_holds(db: Session, now: datetime, turf_id: int | None = None) -> int:
    """Mark pending bookings whose hold has lapsed as expired (no commit).

    Returns:
        Number of bookings expired.
    """
    stmt = (
        update(Booking)
        .where(
            Booking.status == BookingStatus.pending,
            Booking.hold_expires_at < now,
        )
        .values(status=BookingStatus.expired)
        .execution_options(synchronize_session=False)
    )
    if turf_id is not None:
        stmt = stmt.where(Booking.turf_id == turf_id)
    return int(db.execute(stmt).rowcount or 0)  # type: ignore[attr-defined]


def _insert_booking(
    db: Session, player: User, turf: Turf, plan: _SlotPlan, total: int, now: datetime
) -> Booking:
    """Expire stale holds and insert the pending booking in one transaction.

    Retries on the (astronomically unlikely) booking_ref collision.

    Raises:
        ConflictError: 409 ``SLOT_UNAVAILABLE`` on an exclusion-constraint violation.
    """
    for _attempt in range(_MAX_REF_ATTEMPTS):
        expire_stale_holds(db, now, turf.id)
        booking = Booking(
            booking_ref=generate_booking_ref(),
            player_id=player.id,
            turf_id=turf.id,
            start_at=plan.start_at,
            end_at=plan.end_at,
            slot_count=len(plan.slot_starts),
            total_amount=total,
            currency=turf.currency,
            status=BookingStatus.pending,
            hold_expires_at=now + timedelta(minutes=settings.BOOKING_HOLD_MINUTES),
            refund_status=RefundStatus.none,
        )
        db.add(booking)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            if is_exclusion_violation(exc):
                raise ConflictError(
                    "That slot was just booked by someone else", code="SLOT_UNAVAILABLE"
                ) from exc
            if sqlstate(exc) == UNIQUE_VIOLATION and "booking_ref" in str(exc.orig):
                logger.warning("booking_ref collision; retrying")
                continue
            raise
        return booking
    raise AppError(500, "Could not allocate a booking reference", code="INTERNAL_ERROR")


def _start_checkout(db: Session, booking: Booking, player: User, gateway: PaymentGateway) -> str:
    """Create a provider checkout for ``booking`` and record a pending Payment.

    Raises:
        PaymentGatewayError: Propagated from the gateway (caller decides what to do).
    """
    result = gateway.create_checkout(booking, player)
    payment = Payment(
        booking_id=booking.id,
        provider="dodo",
        provider_payment_id=result.provider_payment_id,
        checkout_session_id=result.checkout_session_id,
        amount=booking.total_amount,
        currency=booking.currency,
        status=PaymentStatus.pending,
    )
    db.add(payment)
    db.commit()
    return result.checkout_url


def create_booking(
    db: Session,
    player: User,
    data: BookingCreate,
    gateway: PaymentGateway,
    now: datetime | None = None,
) -> CheckoutOutcome:
    """Validate, insert a pending hold and open a checkout session.

    Raises:
        ForbiddenError: 403 ``EMAIL_NOT_VERIFIED``.
        NotFoundError: Unknown or inactive turf.
        BadRequestError: ``OWN_TURF``, ``INVALID_SLOT_COUNT``, ``SLOT_NOT_ALIGNED``,
            ``OUTSIDE_OPENING_HOURS``, ``SLOT_IN_PAST``, ``OUTSIDE_BOOKING_WINDOW``.
        ConflictError: 409 ``SLOT_UNAVAILABLE`` (blocked or already held/booked).
        AppError: 502 ``PAYMENT_PROVIDER_ERROR`` if the checkout cannot be created
            (the hold is released by cancelling the booking).
    """
    current = now or utcnow()
    turf, plan = _validate_request(db, player, data, current)
    rules = list(turf.pricing_rules)
    total = sum(resolve_slot_price(turf, rules, start) for start in plan.slot_starts)
    booking = _insert_booking(db, player, turf, plan, total, current)
    try:
        checkout_url = _start_checkout(db, booking, player, gateway)
    except PaymentGatewayError as exc:
        db.rollback()
        logger.error("Checkout creation failed for booking %s: %s", booking.id, exc)
        booking.status = BookingStatus.cancelled
        booking.cancelled_by = CancelledBy.system
        booking.cancelled_at = current
        booking.cancellation_reason = "Payment provider unavailable"
        db.commit()
        raise AppError(
            502, "Payment provider is unavailable, please try again", "PAYMENT_PROVIDER_ERROR"
        ) from exc
    loaded = get_booking_with_relations(db, booking.id)
    assert loaded is not None  # noqa: S101 - just committed
    return CheckoutOutcome(booking=loaded, checkout_url=checkout_url)


def renew_checkout(
    db: Session,
    booking_id: int,
    player: User,
    gateway: PaymentGateway,
    now: datetime | None = None,
) -> CheckoutOutcome:
    """Create a fresh checkout for a still-held pending booking of ``player``.

    Raises:
        NotFoundError: The booking does not exist or belongs to someone else.
        ConflictError: 409 ``HOLD_EXPIRED`` if not pending or the hold has lapsed.
        AppError: 502 ``PAYMENT_PROVIDER_ERROR`` on a gateway failure.
    """
    current = now or utcnow()
    booking = get_booking_with_relations(db, booking_id)
    if booking is None or booking.player_id != player.id:
        raise NotFoundError("Booking not found")
    if (
        booking.status != BookingStatus.pending
        or booking.hold_expires_at is None
        or booking.hold_expires_at <= current
    ):
        raise ConflictError("Your hold on this slot has expired", code="HOLD_EXPIRED")
    try:
        checkout_url = _start_checkout(db, booking, player, gateway)
    except PaymentGatewayError as exc:
        db.rollback()
        raise AppError(
            502, "Payment provider is unavailable, please try again", "PAYMENT_PROVIDER_ERROR"
        ) from exc
    return CheckoutOutcome(booking=booking, checkout_url=checkout_url)


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


def succeeded_payment(booking: Booking) -> Payment | None:
    """Return the most recent succeeded payment of a booking, if any."""
    paid = [p for p in booking.payments if p.status == PaymentStatus.succeeded]
    return paid[-1] if paid else None


def request_refund(
    db: Session, booking: Booking, payment: Payment, gateway: PaymentGateway, reason: str
) -> bool:
    """Ask the gateway for a full refund; updates ids/statuses (caller commits).

    Returns:
        True if the refund request was accepted, False if the gateway failed
        (``booking.refund_status`` is then ``failed``).
    """
    try:
        result = gateway.refund(payment, reason)
    except PaymentGatewayError:
        logger.error(
            "Refund request failed for booking %s (payment %s)",
            booking.id,
            payment.id,
            exc_info=True,
        )
        booking.refund_status = RefundStatus.failed
        return False
    payment.provider_refund_id = result.provider_refund_id
    booking.refund_status = RefundStatus.pending
    return True


def _cancel_actor(booking: Booking, user: User) -> CancelledBy:
    """Map the acting user to ``CancelledBy`` (admin > turf owner > player)."""
    if user.role == UserRole.admin:
        return CancelledBy.admin
    if booking.turf.owner_id == user.id:
        return CancelledBy.owner
    return CancelledBy.player


def cancel_booking(
    db: Session,
    booking_id: int,
    user: User,
    gateway: PaymentGateway,
    reason: str | None = None,
    now: datetime | None = None,
) -> tuple[Booking, list[EmailJob]]:
    """Cancel a booking applying the refund policy.

    Policy: pending -> cancelled, no refund. Confirmed, by the player -> full refund
    if ``start_at - now >= FREE_CANCELLATION_HOURS`` else no refund. Confirmed, by the
    turf owner or an admin -> full refund. Bookings that already started cannot be
    cancelled.

    Returns:
        The updated booking and the emails to queue (player + owner).

    Raises:
        NotFoundError: Booking missing or not visible to ``user``.
        ConflictError: 409 ``INVALID_TRANSITION``.
    """
    current = now or utcnow()
    booking = (
        db.execute(
            _booking_query()
            .options(selectinload(Booking.payments))
            .where(Booking.id == booking_id)
            .with_for_update(of=Booking)
        )
        .unique()
        .scalar_one_or_none()
    )
    if booking is None or not _can_view(booking, user):
        raise NotFoundError("Booking not found")
    if booking.status in (BookingStatus.pending, BookingStatus.confirmed) and (
        booking.start_at <= current
    ):
        raise ConflictError(
            "This booking has already started and cannot be cancelled",
            code="INVALID_TRANSITION",
        )
    was_confirmed = booking.status == BookingStatus.confirmed
    transition(booking, BookingStatus.cancelled)
    actor = _cancel_actor(booking, user)
    booking.cancelled_by = actor
    booking.cancelled_at = current
    booking.cancellation_reason = reason
    booking.hold_expires_at = None

    refund_amount: int | None = None
    payment = succeeded_payment(booking) if was_confirmed else None
    if payment is not None:
        free_window = timedelta(hours=settings.FREE_CANCELLATION_HOURS)
        eligible = actor != CancelledBy.player or booking.start_at - current >= free_window
        if eligible:
            refund_reason = reason or f"Booking {booking.booking_ref} cancelled by {actor.value}"
            if request_refund(db, booking, payment, gateway, refund_reason):
                refund_amount = payment.amount
    db.commit()
    jobs = booking_cancelled_jobs(booking, refund_amount=refund_amount, reason=reason)
    return booking, jobs


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


def _upcoming_condition(now: datetime) -> ColumnElement[bool]:
    """SQL condition for bookings that are still ahead and active."""
    return and_(
        Booking.end_at > now,
        or_(
            Booking.status == BookingStatus.confirmed,
            and_(Booking.status == BookingStatus.pending, Booking.hold_expires_at > now),
        ),
    )


def paginate(
    db: Session, stmt: Select[Booking], pagination: PaginationParams
) -> tuple[list[Booking], int]:
    """Run a bookings SELECT with paging; returns ``(items, total)``."""
    total = db.execute(
        select(func.count()).select_from(stmt.order_by(None).subquery())
    ).scalar_one()
    rows = (
        db.execute(
            stmt.options(*booking_load_options()).offset(pagination.offset).limit(pagination.limit)
        )
        .unique()
        .scalars()
        .all()
    )
    return list(rows), int(total)


def list_player_bookings(
    db: Session,
    player: User,
    pagination: PaginationParams,
    scope: str | None = None,
    status: BookingStatus | None = None,
    now: datetime | None = None,
) -> tuple[list[Booking], int]:
    """List a user's own bookings.

    ``scope=upcoming``: active bookings that have not ended (soonest first).
    ``scope=past``: everything else (most recent first). No scope: all, newest first.
    """
    current = now or utcnow()
    stmt = select(Booking).where(Booking.player_id == player.id)
    if status is not None:
        stmt = stmt.where(Booking.status == status)
    upcoming = _upcoming_condition(current)
    if scope == "upcoming":
        stmt = stmt.where(upcoming).order_by(Booking.start_at.asc(), Booking.id.asc())
    elif scope == "past":
        stmt = stmt.where(~upcoming).order_by(Booking.start_at.desc(), Booking.id.desc())
    else:
        stmt = stmt.order_by(Booking.start_at.desc(), Booking.id.desc())
    return paginate(db, stmt, pagination)
