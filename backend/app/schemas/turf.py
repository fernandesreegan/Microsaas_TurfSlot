"""Schemas for turfs and their pricing rules."""

from __future__ import annotations

from datetime import time
from typing import Annotated, Any, Literal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AfterValidator,
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.config import settings
from app.models.enums import SportType

MAX_IMAGE_URLS = 10
MAX_AMENITIES = 30


def _validate_timezone(value: str) -> str:
    """Require a valid IANA timezone name."""
    if not value or value != value.strip():
        raise ValueError("Invalid IANA timezone")
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("Invalid IANA timezone") from exc
    return value


def _validate_http_url(value: str) -> str:
    """Require an absolute http(s) URL."""
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Image URLs must be absolute http(s) URLs")
    return value


def _validate_whole_minutes(value: time) -> time:
    """Reject times with seconds/microseconds or tz info."""
    if value.second or value.microsecond:
        raise ValueError("Time must be in whole minutes (HH:MM)")
    if value.tzinfo is not None:
        raise ValueError("Time must not include a timezone offset")
    return value


def _format_hhmm(value: time) -> str:
    """Render a time as ``HH:MM``."""
    return value.strftime("%H:%M")


HHMMTime = Annotated[
    time,
    AfterValidator(_validate_whole_minutes),
    PlainSerializer(_format_hhmm, return_type=str),
]
"""A wall-clock time accepted as ``HH:MM`` (or ``HH:MM:00``) and rendered as ``HH:MM``."""

TimezoneName = Annotated[str, StringConstraints(max_length=64), AfterValidator(_validate_timezone)]
ImageUrl = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=500),
    AfterValidator(_validate_http_url),
]
Amenity = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
TurfName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
CityName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Description = Annotated[str, StringConstraints(max_length=5000)]
SlotDuration = Literal[30, 60, 90]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]


def _dedupe(values: list[Any]) -> list[Any]:
    """Remove duplicates while keeping order."""
    return list(dict.fromkeys(values))


# ---------------------------------------------------------------------------
# Turfs
# ---------------------------------------------------------------------------


class TurfCreate(BaseModel):
    """Payload to create a turf (TurfRead minus id/slug/is_active/owner_id)."""

    name: TurfName
    description: Description = ""
    address: Address
    city: CityName
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    timezone: TimezoneName
    sport_types: list[SportType] = Field(min_length=1)
    amenities: list[Amenity] = Field(default_factory=list, max_length=MAX_AMENITIES)
    image_urls: list[ImageUrl] = Field(default_factory=list, max_length=MAX_IMAGE_URLS)
    slot_duration_minutes: SlotDuration
    opening_time: HHMMTime
    closing_time: HHMMTime
    base_price: int = Field(ge=0)
    currency: CurrencyCode = Field(default_factory=lambda: settings.DEFAULT_CURRENCY)

    @field_validator("sport_types", "amenities", "image_urls")
    @classmethod
    def _unique(cls, value: list[Any]) -> list[Any]:
        """Drop duplicate list entries."""
        return _dedupe(value)

    @model_validator(mode="after")
    def _check_hours(self) -> TurfCreate:
        """Require ``closing_time`` to be after ``opening_time``."""
        if self.closing_time <= self.opening_time:
            raise ValueError("closing_time must be after opening_time")
        return self


_NON_NULLABLE_UPDATE_FIELDS = (
    "name",
    "description",
    "address",
    "city",
    "timezone",
    "sport_types",
    "amenities",
    "image_urls",
    "slot_duration_minutes",
    "opening_time",
    "closing_time",
    "base_price",
    "currency",
)


class TurfUpdate(BaseModel):
    """Partial turf update; omitted fields are unchanged. The slug never changes."""

    name: TurfName | None = None
    description: Description | None = None
    address: Address | None = None
    city: CityName | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    timezone: TimezoneName | None = None
    sport_types: list[SportType] | None = Field(default=None, min_length=1)
    amenities: list[Amenity] | None = Field(default=None, max_length=MAX_AMENITIES)
    image_urls: list[ImageUrl] | None = Field(default=None, max_length=MAX_IMAGE_URLS)
    slot_duration_minutes: SlotDuration | None = None
    opening_time: HHMMTime | None = None
    closing_time: HHMMTime | None = None
    base_price: int | None = Field(default=None, ge=0)
    currency: CurrencyCode | None = None

    @field_validator("sport_types", "amenities", "image_urls")
    @classmethod
    def _unique(cls, value: list[Any] | None) -> list[Any] | None:
        """Drop duplicate list entries."""
        return _dedupe(value) if value is not None else None

    @model_validator(mode="after")
    def _check(self) -> TurfUpdate:
        """Reject explicit nulls for required fields and inverted hours."""
        for name in _NON_NULLABLE_UPDATE_FIELDS:
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        if (
            self.opening_time is not None
            and self.closing_time is not None
            and self.closing_time <= self.opening_time
        ):
            raise ValueError("closing_time must be after opening_time")
        return self


class TurfRead(BaseModel):
    """Public turf representation. ``city`` is the display form (original casing)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    description: str
    address: str
    city: str = Field(validation_alias=AliasChoices("city_display", "city"))
    latitude: float | None
    longitude: float | None
    timezone: str
    sport_types: list[SportType]
    amenities: list[str]
    image_urls: list[str]
    slot_duration_minutes: int
    opening_time: HHMMTime
    closing_time: HHMMTime
    base_price: int
    currency: str
    is_active: bool
    owner_id: int


class TurfSearchItem(TurfRead):
    """A turf in search results; ``distance_km`` is set only for location searches."""

    distance_km: float | None = None


# ---------------------------------------------------------------------------
# Pricing rules
# ---------------------------------------------------------------------------


class PricingRuleCreate(BaseModel):
    """A price override for ``[start_time, end_time)`` on one weekday or every day."""

    day_of_week: int | None = Field(default=None, ge=0, le=6, description="0=Mon..6=Sun; null=all")
    start_time: HHMMTime
    end_time: HHMMTime
    price: int = Field(ge=0)
    label: Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] = ""

    @model_validator(mode="after")
    def _check_times(self) -> PricingRuleCreate:
        """Require ``end_time`` to be after ``start_time``."""
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class PricingRuleUpdate(PricingRuleCreate):
    """Full replacement of a pricing rule (same fields as create)."""


class PricingRuleRead(BaseModel):
    """Stored pricing rule."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    day_of_week: int | None
    start_time: HHMMTime
    end_time: HHMMTime
    price: int
    label: str

    @field_validator("label", mode="before")
    @classmethod
    def _label_default(cls, value: str | None) -> str:
        """Render a missing label as an empty string."""
        return value or ""


class TurfDetail(TurfRead):
    """Turf detail including its pricing rules."""

    pricing_rules: list[PricingRuleRead]
