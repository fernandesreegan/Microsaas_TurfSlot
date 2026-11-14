"""Booking request/response schemas (see SHARED API CONTRACT in the PRP)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import overload

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.config import settings
from app.models import Booking, BookingStatus, CancelledBy, RefundStatus


@overload
def to_utc(value: datetime) -> datetime: ...
@overload
def to_utc(value: None) -> None: ...
def to_utc(value: datetime | None) -> datetime | None:
    """Normalise an aware datetime to UTC so it serialises with a ``Z`` suffix."""
    return value.astimezone(UTC) if value is not None else None


class BookingTurfSummary(BaseModel):
    """Compact turf info embedded in a booking."""

    id: int
    name: str
    slug: str
    city: str
    timezone: str


class BookingPlayerSummary(BaseModel):
    """Compact player info embedded in a booking."""

    id: int
    full_name: str
    email: str


class BookingCreate(BaseModel):
    """Request body for ``POST /bookings``."""

    turf_id: int = Field(gt=0)
    start_at: AwareDatetime
    slot_count: int = Field(ge=1, le=100)


class CancelRequest(BaseModel):
    """Request body for ``POST /bookings/{id}/cancel``."""

    reason: str | None = Field(default=None, max_length=500)


class BookingRead(BaseModel):
    """Booking as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_ref: str
    turf: BookingTurfSummary
    player: BookingPlayerSummary
    start_at: datetime
    end_at: datetime
    slot_count: int
    total_amount: int
    currency: str
    status: BookingStatus
    hold_expires_at: datetime | None
    cancelled_by: CancelledBy | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    refund_status: RefundStatus
    refund_eligible: bool
    created_at: datetime

    @classmethod
    def from_booking(cls, booking: Booking, now: datetime | None = None) -> BookingRead:
        """Build the response from an ORM booking with ``turf`` and ``player`` loaded.

        ``refund_eligible`` is true when the booking is confirmed and starts at least
        ``FREE_CANCELLATION_HOURS`` from ``now``.
        """
        current = now or datetime.now(UTC)
        turf = booking.turf
        player = booking.player
        eligible = booking.status == BookingStatus.confirmed and (
            booking.start_at - current >= timedelta(hours=settings.FREE_CANCELLATION_HOURS)
        )
        return cls(
            id=booking.id,
            booking_ref=booking.booking_ref,
            turf=BookingTurfSummary(
                id=turf.id,
                name=turf.name,
                slug=turf.slug,
                city=turf.city_display,
                timezone=turf.timezone,
            ),
            player=BookingPlayerSummary(
                id=player.id, full_name=player.full_name, email=player.email
            ),
            start_at=to_utc(booking.start_at),
            end_at=to_utc(booking.end_at),
            slot_count=booking.slot_count,
            total_amount=booking.total_amount,
            currency=booking.currency,
            status=booking.status,
            hold_expires_at=to_utc(booking.hold_expires_at),
            cancelled_by=booking.cancelled_by,
            cancelled_at=to_utc(booking.cancelled_at),
            cancellation_reason=booking.cancellation_reason,
            refund_status=booking.refund_status,
            refund_eligible=eligible,
            created_at=to_utc(booking.created_at),
        )


class BookingCheckout(BaseModel):
    """Response of ``POST /bookings`` and ``POST /bookings/{id}/checkout``."""

    booking: BookingRead
    checkout_url: str
