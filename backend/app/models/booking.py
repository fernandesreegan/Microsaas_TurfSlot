"""Bookings (consecutive slot ranges on a turf)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    literal_column,
    text,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin
from app.models.enums import (
    BookingStatus,
    CancelledBy,
    RefundStatus,
    booking_status_enum,
    cancelled_by_enum,
    refund_status_enum,
)

if TYPE_CHECKING:
    from app.models.payment import Payment
    from app.models.turf import Turf
    from app.models.user import User

# Statuses that occupy a turf's time range (covered by bookings_no_overlap).
ACTIVE_BOOKING_STATUSES: tuple[BookingStatus, ...] = (
    BookingStatus.pending,
    BookingStatus.confirmed,
)


class Booking(TimestampMixin, Base):
    """A player's booking of ``slot_count`` consecutive slots ``[start_at, end_at)``.

    Double booking is prevented in the database by the ``bookings_no_overlap``
    exclusion constraint over pending/confirmed rows; an insert/update that
    violates it raises ``IntegrityError`` with SQLSTATE 23P01.
    The upper bound on ``slot_count`` (MAX_SLOTS_PER_BOOKING) is enforced in the
    service layer since it is configurable.
    """

    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("end_at > start_at", name="time_order"),
        CheckConstraint("slot_count >= 1", name="slot_count_positive"),
        CheckConstraint("total_amount >= 0", name="total_amount_non_negative"),
        CheckConstraint("booking_ref ~ '^[A-Z0-9]{8}$'", name="booking_ref_format"),
        Index("ix_bookings_turf_id_start_at", "turf_id", "start_at"),
        Index("ix_bookings_status_hold_expires_at", "status", "hold_expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    booking_ref: Mapped[str] = mapped_column(String(8), unique=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    turf_id: Mapped[int] = mapped_column(ForeignKey("turfs.id", ondelete="RESTRICT"), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    slot_count: Mapped[int] = mapped_column(Integer)
    total_amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(CHAR(3))
    status: Mapped[BookingStatus] = mapped_column(
        booking_status_enum,
        default=BookingStatus.pending,
        server_default=BookingStatus.pending.value,
        index=True,
    )
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_by: Mapped[CancelledBy | None] = mapped_column(cancelled_by_enum)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(String(500))
    refund_status: Mapped[RefundStatus] = mapped_column(
        refund_status_enum,
        default=RefundStatus.none,
        server_default=RefundStatus.none.value,
    )

    player: Mapped[User] = relationship(back_populates="bookings")
    turf: Mapped[Turf] = relationship(back_populates="bookings")
    payments: Mapped[list[Payment]] = relationship(
        back_populates="booking", order_by="Payment.created_at"
    )

    def __repr__(self) -> str:
        return f"<Booking id={self.id} ref={self.booking_ref!r} status={self.status}>"


Booking.__table__.append_constraint(  # type: ignore[attr-defined]
    ExcludeConstraint(
        (Booking.__table__.c.turf_id, "="),  # type: ignore[attr-defined]
        (
            func.tstzrange(
                Booking.__table__.c.start_at,  # type: ignore[attr-defined]
                Booking.__table__.c.end_at,  # type: ignore[attr-defined]
                literal_column("'[)'"),
            ),
            "&&",
        ),
        name="bookings_no_overlap",
        using="gist",
        where=text("status IN ('pending', 'confirmed')"),
    )
)
