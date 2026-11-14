"""Owner dashboard response schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.schemas.booking import BookingRead


class OwnerSummary(BaseModel):
    """Aggregate KPIs for an owner's turfs over a local-date range."""

    bookings_today: int
    upcoming_bookings: list[BookingRead]
    occupancy_pct: float
    revenue: int
    refunds: int
    cancellations: int
    currency: str


class RevenuePoint(BaseModel):
    """Revenue and booking count for one day/week bucket (turf-local dates)."""

    period_start: date
    revenue: int
    bookings: int
