"""Dodo Payments webhook processing: idempotent storage and event dispatch.

Payload shape (from ``dodopayments.types.*WebhookEvent`` in the installed SDK)::

    {"business_id": str, "type": "payment.succeeded", "timestamp": str,
     "data": {"payment_id": str, "checkout_session_id": str | None,
              "metadata": {"booking_id": "...", ...}, "total_amount": int, ...}}

Refund events carry a ``Refund`` object in ``data`` (``refund_id``, ``payment_id``,
``metadata``, ``amount``...).

The event row is inserted with ``ON CONFLICT DO NOTHING`` in the same transaction
as the processing, so a concurrent duplicate delivery blocks on the unique index
until the first one commits and is then skipped; a processing error rolls back the
insert so the provider's retry is processed again.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import (
    Booking,
    BookingStatus,
    Payment,
    PaymentStatus,
    RefundStatus,
    Turf,
    WebhookEvent,
)
from app.services.booking_notifications import (
    EmailJob,
    booking_confirmed_jobs,
    late_payment_refunded_jobs,
    refund_failed_jobs,
    refund_processed_jobs,
)
from app.services.booking_service import is_exclusion_violation, request_refund
from app.services.payment_gateway import InvalidWebhookSignature, PaymentGateway

logger = logging.getLogger(__name__)

PROVIDER = "dodo"
LATE_PAYMENT_REFUND_REASON = "Slot no longer available when payment completed"

WebhookResult = Literal["processed", "duplicate", "ignored"]


@dataclass(slots=True)
class WebhookOutcome:
    """Result of processing a webhook plus emails to send after commit."""

    status: WebhookResult
    emails: list[EmailJob] = field(default_factory=list)


def _header(headers: Mapping[str, str], name: str) -> str | None:
    """Case-insensitive header lookup."""
    lowered = name.lower()
    for key, value in headers.items():
        if key.lower() == lowered:
            return value
    return None


def _data(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return ``payload["data"]`` as a dict (empty if missing/malformed)."""
    data = payload.get("data")
    return data if isinstance(data, dict) else {}


def _metadata_booking_id(data: Mapping[str, Any]) -> int | None:
    """Extract ``metadata.booking_id`` as an int, if present and valid."""
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        return None
    try:
        return int(metadata["booking_id"])
    except (KeyError, TypeError, ValueError):
        return None


def _lock_booking(db: Session, booking_id: int) -> Booking | None:
    """Load a booking FOR UPDATE with turf/owner/player/payments."""
    return (
        db.execute(
            select(Booking)
            .options(
                joinedload(Booking.turf).joinedload(Turf.owner),
                joinedload(Booking.player),
                selectinload(Booking.payments),
            )
            .where(Booking.id == booking_id)
            .with_for_update(of=Booking)
        )
        .unique()
        .scalar_one_or_none()
    )


def _find_payment(db: Session, data: Mapping[str, Any]) -> Payment | None:
    """Locate our Payment row by provider payment id, then checkout session id."""
    payment_id = data.get("payment_id")
    if payment_id:
        found = db.execute(
            select(Payment).where(Payment.provider_payment_id == str(payment_id))
        ).scalar_one_or_none()
        if found is not None:
            return found
    session_id = data.get("checkout_session_id")
    if session_id:
        return (
            db.execute(
                select(Payment)
                .where(Payment.checkout_session_id == str(session_id))
                .order_by(Payment.id.desc())
            )
            .scalars()
            .first()
        )
    return None


def _resolve(db: Session, data: Mapping[str, Any]) -> tuple[Booking | None, Payment | None]:
    """Find the booking (metadata first, then via the payment) and the matching payment."""
    payment = _find_payment(db, data)
    booking_id = _metadata_booking_id(data)
    if booking_id is None and payment is not None:
        booking_id = payment.booking_id
    if booking_id is None:
        return None, payment
    booking = _lock_booking(db, booking_id)
    if booking is None:
        return None, payment
    if payment is not None and payment.booking_id != booking.id:
        logger.warning("Webhook payment %s does not belong to booking %s", payment.id, booking.id)
        payment = None
    return booking, payment


def _payment_for_success(db: Session, booking: Booking, data: Mapping[str, Any]) -> Payment:
    """Return the payment row to mark succeeded, creating one if we never saw it."""
    provider_id = data.get("payment_id")
    candidates = [p for p in booking.payments if p.status == PaymentStatus.pending]
    payment = candidates[-1] if candidates else None
    if payment is None:
        amount = data.get("total_amount")
        payment = Payment(
            booking_id=booking.id,
            provider=PROVIDER,
            checkout_session_id=data.get("checkout_session_id"),
            amount=int(amount) if isinstance(amount, int) else booking.total_amount,
            currency=booking.currency,
            status=PaymentStatus.pending,
        )
        db.add(payment)
        booking.payments.append(payment)
    if provider_id:
        payment.provider_payment_id = str(provider_id)
    return payment


def _try_reconfirm(db: Session, booking: Booking) -> bool:
    """Re-confirm an expired/cancelled booking inside a SAVEPOINT.

    Returns:
        True if confirmed; False if the slot was taken (exclusion violation).
    """
    savepoint = db.begin_nested()
    booking.status = BookingStatus.confirmed
    booking.cancelled_by = None
    booking.cancelled_at = None
    booking.cancellation_reason = None
    try:
        db.flush()
    except IntegrityError as exc:
        savepoint.rollback()
        if not is_exclusion_violation(exc):
            raise
        # Objects modified inside the savepoint are expired and reload as before.
        return False
    savepoint.commit()
    return True


def _handle_payment_succeeded(
    db: Session, gateway: PaymentGateway, data: Mapping[str, Any]
) -> list[EmailJob]:
    """Mark the payment succeeded and confirm (or re-confirm / auto-refund) the booking."""
    booking, payment = _resolve(db, data)
    if booking is None:
        logger.warning("payment.succeeded for unknown booking: %s", data.get("payment_id"))
        return []
    already_paid = [
        p
        for p in booking.payments
        if p.status == PaymentStatus.succeeded and (payment is None or p.id != payment.id)
    ]
    if payment is None or payment.status != PaymentStatus.succeeded:
        payment = payment or _payment_for_success(db, booking, data)
        if data.get("payment_id"):
            payment.provider_payment_id = str(data["payment_id"])
        payment.status = PaymentStatus.succeeded
    db.flush()

    if booking.status == BookingStatus.pending:
        booking.status = BookingStatus.confirmed
        booking.hold_expires_at = None
        return booking_confirmed_jobs(booking)

    if booking.status in (BookingStatus.confirmed, BookingStatus.completed):
        if already_paid:
            logger.warning("Duplicate payment %s for booking %s; refunding", payment.id, booking.id)
            request_refund(db, booking, payment, gateway, "Duplicate payment")
        return []

    # expired or cancelled: late payment
    if _try_reconfirm(db, booking):
        booking.hold_expires_at = None
        logger.info("Late payment re-confirmed booking %s", booking.id)
        return booking_confirmed_jobs(booking)
    logger.info("Late payment for booking %s; slot taken, auto-refunding", booking.id)
    request_refund(db, booking, payment, gateway, LATE_PAYMENT_REFUND_REASON)
    return late_payment_refunded_jobs(booking, payment.amount)


def _handle_payment_failed(db: Session, data: Mapping[str, Any]) -> list[EmailJob]:
    """Mark the payment failed; the booking stays pending until its hold expires."""
    booking, payment = _resolve(db, data)
    if payment is None and booking is not None:
        pending = [p for p in booking.payments if p.status == PaymentStatus.pending]
        payment = pending[-1] if pending else None
    if payment is None:
        logger.warning("payment.failed for unknown payment: %s", data.get("payment_id"))
        return []
    if payment.status == PaymentStatus.pending:
        payment.status = PaymentStatus.failed
        if data.get("payment_id") and payment.provider_payment_id is None:
            payment.provider_payment_id = str(data["payment_id"])
    return []


def _refund_target(db: Session, data: Mapping[str, Any]) -> tuple[Booking, Payment] | None:
    """Locate the booking and payment a refund event refers to."""
    booking, payment = _resolve(db, data)
    refund_id = data.get("refund_id")
    if payment is None and refund_id:
        payment = db.execute(
            select(Payment).where(Payment.provider_refund_id == str(refund_id))
        ).scalar_one_or_none()
        if payment is not None and booking is None:
            booking = _lock_booking(db, payment.booking_id)
    if payment is None and booking is not None:
        refundable = [p for p in booking.payments if p.provider_refund_id]
        payment = refundable[-1] if refundable else None
    if booking is None or payment is None:
        logger.warning("Refund event for unknown payment: %s", data.get("payment_id"))
        return None
    return booking, payment


def _handle_refund_succeeded(db: Session, data: Mapping[str, Any]) -> list[EmailJob]:
    """Mark payment refunded and booking refund_status refunded; email the player."""
    target = _refund_target(db, data)
    if target is None:
        return []
    booking, payment = target
    payment.status = PaymentStatus.refunded
    if data.get("refund_id"):
        payment.provider_refund_id = str(data["refund_id"])
    booking.refund_status = RefundStatus.refunded
    amount = data.get("amount")
    return refund_processed_jobs(
        booking, int(amount) if isinstance(amount, int) else payment.amount
    )


def _handle_refund_failed(db: Session, data: Mapping[str, Any]) -> list[EmailJob]:
    """Mark refund failed, log at ERROR and email the player."""
    target = _refund_target(db, data)
    if target is None:
        return []
    booking, payment = target
    payment.status = PaymentStatus.refund_failed
    booking.refund_status = RefundStatus.failed
    logger.error(
        "Refund failed for booking %s (payment %s, refund %s)",
        booking.id,
        payment.id,
        data.get("refund_id"),
    )
    return refund_failed_jobs(booking, payment.amount)


def process_webhook(
    db: Session, gateway: PaymentGateway, body: bytes, headers: Mapping[str, str]
) -> WebhookOutcome:
    """Verify, de-duplicate and process one Dodo webhook delivery.

    Raises:
        InvalidWebhookSignature: Bad signature, stale timestamp or missing ``webhook-id``.
    """
    payload = gateway.verify_webhook(body, headers)
    event_id = _header(headers, "webhook-id")
    if not event_id:
        raise InvalidWebhookSignature("Missing webhook-id header")
    event_type = str(payload.get("type") or "unknown")

    inserted = db.execute(
        pg_insert(WebhookEvent)
        .values(provider=PROVIDER, event_id=event_id, event_type=event_type, payload=payload)
        .on_conflict_do_nothing(index_elements=[WebhookEvent.event_id])
        .returning(WebhookEvent.id)
    ).scalar_one_or_none()
    if inserted is None:
        db.rollback()
        logger.info("Duplicate webhook %s (%s) ignored", event_id, event_type)
        return WebhookOutcome(status="duplicate")

    data = _data(payload)
    status: WebhookResult = "processed"
    try:
        if event_type == "payment.succeeded":
            emails = _handle_payment_succeeded(db, gateway, data)
        elif event_type == "payment.failed":
            emails = _handle_payment_failed(db, data)
        elif event_type == "refund.succeeded":
            emails = _handle_refund_succeeded(db, data)
        elif event_type == "refund.failed":
            emails = _handle_refund_failed(db, data)
        else:
            logger.info("Ignoring unhandled webhook type %s", event_type)
            emails = []
            status = "ignored"
        event = db.get(WebhookEvent, inserted)
        if event is not None:
            event.processed_at = datetime.now(UTC)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return WebhookOutcome(status=status, emails=emails)
