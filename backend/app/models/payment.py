"""Payments and idempotent webhook event log."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CHAR, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import CreatedAtMixin, TimestampMixin
from app.models.enums import PaymentStatus, payment_status_enum

if TYPE_CHECKING:
    from app.models.booking import Booking


class Payment(TimestampMixin, Base):
    """A payment attempt (checkout session) for a booking."""

    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount >= 0", name="amount_non_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id", ondelete="RESTRICT"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32), default="dodo", server_default="dodo")
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    checkout_session_id: Mapped[str | None] = mapped_column(String(255), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(CHAR(3))
    status: Mapped[PaymentStatus] = mapped_column(
        payment_status_enum,
        default=PaymentStatus.pending,
        server_default=PaymentStatus.pending.value,
    )
    provider_refund_id: Mapped[str | None] = mapped_column(String(255))

    booking: Mapped[Booking] = relationship(back_populates="payments")

    def __repr__(self) -> str:
        return f"<Payment id={self.id} booking_id={self.booking_id} status={self.status}>"


class WebhookEvent(CreatedAtMixin, Base):
    """Received provider webhook; ``event_id`` uniqueness gives idempotency."""

    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))
    event_id: Mapped[str] = mapped_column(String(255), unique=True)
    event_type: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
