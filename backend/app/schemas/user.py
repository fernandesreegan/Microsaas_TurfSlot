"""User schemas shared by the auth and admin modules."""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from app.models.enums import UserRole


def ensure_utc(value: datetime) -> datetime:
    """Normalize a datetime to UTC (naive values are assumed to already be UTC).

    Pydantic serializes UTC-aware datetimes with a trailing ``Z`` as required by the
    shared API contract.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


UtcDatetime = Annotated[datetime, AfterValidator(ensure_utc)]


class UserRead(BaseModel):
    """Public representation of a user account."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    phone: str | None
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: UtcDatetime


class UserUpdate(BaseModel):
    """Self-service profile update (``PUT /auth/me``). Omitted fields are unchanged."""

    full_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)

    @field_validator("full_name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("full_name must not be blank")
        return value

    @field_validator("phone")
    @classmethod
    def _strip_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None
