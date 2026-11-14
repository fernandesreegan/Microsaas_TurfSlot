"""Turf listing and its peak-pricing rules."""

from __future__ import annotations

from datetime import time
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import CreatedAtMixin, TimestampMixin
from app.models.enums import SportType, sport_type_enum

if TYPE_CHECKING:
    from app.models.blocked_slot import BlockedSlot
    from app.models.booking import Booking
    from app.models.user import User


class Turf(TimestampMixin, Base):
    """A bookable sports turf owned by an ``owner`` user.

    ``city`` is the normalized (trimmed, lowercased) value used for search;
    ``city_display`` keeps the owner's original casing for display.
    """

    __tablename__ = "turfs"
    __table_args__ = (
        CheckConstraint("slot_duration_minutes IN (30, 60, 90)", name="slot_duration"),
        CheckConstraint("closing_time > opening_time", name="hours_order"),
        CheckConstraint("base_price >= 0", name="base_price_non_negative"),
        Index("ix_turfs_sport_types", "sport_types", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(160), unique=True)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    address: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100), index=True)
    city_display: Mapped[str] = mapped_column(String(100))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    timezone: Mapped[str] = mapped_column(String(64))
    sport_types: Mapped[list[SportType]] = mapped_column(
        ARRAY(sport_type_enum), default=list, server_default=text("'{}'")
    )
    amenities: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)), default=list, server_default=text("'{}'")
    )
    image_urls: Mapped[list[str]] = mapped_column(
        ARRAY(String(500)), default=list, server_default=text("'{}'")
    )
    slot_duration_minutes: Mapped[int] = mapped_column(Integer)
    opening_time: Mapped[time] = mapped_column(Time)
    closing_time: Mapped[time] = mapped_column(Time)
    base_price: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(CHAR(3))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    owner: Mapped[User] = relationship(back_populates="turfs")
    pricing_rules: Mapped[list[TurfPricingRule]] = relationship(
        back_populates="turf",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TurfPricingRule.start_time",
    )
    blocked_slots: Mapped[list[BlockedSlot]] = relationship(
        back_populates="turf", cascade="all, delete-orphan", passive_deletes=True
    )
    bookings: Mapped[list[Booking]] = relationship(back_populates="turf")

    def __repr__(self) -> str:
        return f"<Turf id={self.id} slug={self.slug!r}>"


class TurfPricingRule(CreatedAtMixin, Base):
    """Price override for a local time range, optionally on a single weekday.

    ``day_of_week``: 0=Mon … 6=Sun, ``NULL`` = every day. Overlap validation is
    done in the service layer.
    """

    __tablename__ = "turf_pricing_rules"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="time_order"),
        CheckConstraint("price >= 0", name="price_non_negative"),
        CheckConstraint(
            "day_of_week IS NULL OR (day_of_week BETWEEN 0 AND 6)", name="day_of_week_range"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    turf_id: Mapped[int] = mapped_column(ForeignKey("turfs.id", ondelete="CASCADE"), index=True)
    day_of_week: Mapped[int | None] = mapped_column(SmallInteger)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    price: Mapped[int] = mapped_column(Integer)
    label: Mapped[str | None] = mapped_column(String(60))

    turf: Mapped[Turf] = relationship(back_populates="pricing_rules")
