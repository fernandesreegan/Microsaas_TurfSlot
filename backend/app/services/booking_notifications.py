"""Build and dispatch booking-related transactional emails.

Services return :class:`EmailJob` lists so that emails are only queued after the
database transaction has been committed; routers then call :func:`dispatch`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import BackgroundTasks

from app.config import settings
from app.models import Booking, User
from app.services.email import format_local, format_money, queue_email


@dataclass(frozen=True, slots=True)
class EmailJob:
    """One email to send: recipient address, template name and its context."""

    to: str
    template: str
    context: dict[str, Any]


def booking_context(
    booking: Booking,
    recipient: User,
    *,
    is_owner: bool,
    refund_amount: int | None = None,
    cancelled_by: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Return the shared template context for a booking email.

    Requires ``booking.turf`` and ``booking.player`` to be loadable. Times are
    rendered in the turf's timezone and amounts with the booking currency.
    """
    turf = booking.turf
    context: dict[str, Any] = {
        "recipient_name": recipient.full_name,
        "booking_ref": booking.booking_ref,
        "turf_name": turf.name,
        "turf_address": turf.address,
        "start_local": format_local(booking.start_at, turf.timezone),
        "end_local": format_local(booking.end_at, turf.timezone),
        "amount": format_money(booking.total_amount, booking.currency),
        "booking_url": f"{settings.FRONTEND_URL.rstrip('/')}/bookings/{booking.id}",
        "is_owner": is_owner,
    }
    if refund_amount is not None:
        context["refund_amount"] = format_money(refund_amount, booking.currency)
    if cancelled_by is not None:
        context["cancelled_by"] = cancelled_by
    if reason:
        context["reason"] = reason
    return context


def _player_and_owner(template: str, booking: Booking, **extra: Any) -> list[EmailJob]:
    """Build the same template for the player and the turf owner."""
    player = booking.player
    owner = booking.turf.owner
    return [
        EmailJob(player.email, template, booking_context(booking, player, is_owner=False, **extra)),
        EmailJob(owner.email, template, booking_context(booking, owner, is_owner=True, **extra)),
    ]


def booking_confirmed_jobs(booking: Booking) -> list[EmailJob]:
    """``booking_confirmed`` for player + owner."""
    return _player_and_owner("booking_confirmed", booking)


def booking_cancelled_jobs(
    booking: Booking, *, refund_amount: int | None, reason: str | None
) -> list[EmailJob]:
    """``booking_cancelled`` for player + owner (with refund amount when refunding)."""
    cancelled_by = booking.cancelled_by.value if booking.cancelled_by else None
    return _player_and_owner(
        "booking_cancelled",
        booking,
        refund_amount=refund_amount,
        cancelled_by=cancelled_by,
        reason=reason,
    )


def _player_only(template: str, booking: Booking, **extra: Any) -> list[EmailJob]:
    """Build a template addressed to the player only."""
    player = booking.player
    return [
        EmailJob(player.email, template, booking_context(booking, player, is_owner=False, **extra))
    ]


def refund_processed_jobs(booking: Booking, amount: int) -> list[EmailJob]:
    """``refund_processed`` for the player."""
    return _player_only("refund_processed", booking, refund_amount=amount)


def refund_failed_jobs(booking: Booking, amount: int) -> list[EmailJob]:
    """``refund_failed`` for the player."""
    return _player_only("refund_failed", booking, refund_amount=amount)


def late_payment_refunded_jobs(booking: Booking, amount: int) -> list[EmailJob]:
    """``late_payment_refunded`` for the player."""
    return _player_only("late_payment_refunded", booking, refund_amount=amount)


def dispatch(background_tasks: BackgroundTasks, jobs: list[EmailJob]) -> None:
    """Queue every job as a FastAPI background task (sent after the response)."""
    for job in jobs:
        queue_email(background_tasks, job.to, job.template, job.context)
