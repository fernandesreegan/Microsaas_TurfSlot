"""Schemas for slot availability and owner-blocked slots."""

from __future__ import annotations

import datetime as dt
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, PlainSerializer, model_validator


def serialize_utc(value: datetime) -> str:
    """Serialize a datetime as ISO 8601 in UTC with a ``Z`` suffix.

    Naive datetimes are assumed to already be UTC.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


UtcDatetime = Annotated[datetime, PlainSerializer(serialize_utc, return_type=str)]
"""A datetime that is always rendered as ``YYYY-MM-DDTHH:MM:SSZ`` in responses."""

SlotStatus = Literal["available", "held", "booked", "blocked", "past"]


class SlotRead(BaseModel):
    """One bookable slot of a turf's day grid."""

    start_at: UtcDatetime
    end_at: UtcDatetime
    status: SlotStatus
    price: int


class DaySlots(BaseModel):
    """All slots of a turf for one turf-local date."""

    turf_id: int
    date: dt.date
    timezone: str
    currency: str
    slots: list[SlotRead]


class BlockedSlotCreate(BaseModel):
    """A range the owner wants to block. Bounds must be timezone-aware."""

    start_at: AwareDatetime
    end_at: AwareDatetime
    reason: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _check_order(self) -> BlockedSlotCreate:
        """Require ``end_at`` to be after ``start_at``."""
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be after start_at")
        return self


class BlockedSlotRead(BaseModel):
    """A stored blocked range."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    turf_id: int
    start_at: UtcDatetime
    end_at: UtcDatetime
    reason: str | None
    created_at: UtcDatetime
