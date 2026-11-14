"""Admin panel schemas."""

from pydantic import BaseModel, ConfigDict

from app.models.enums import BookingStatus, UserRole
from app.schemas.user import UtcDatetime


class AdminUserUpdate(BaseModel):
    """``PUT /admin/users/{id}`` body. Omitted fields are unchanged."""

    is_active: bool | None = None
    role: UserRole | None = None


class AdminTurfRead(BaseModel):
    """Minimal turf row for the admin turfs table."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    city: str
    owner_id: int
    owner_email: str
    is_active: bool
    created_at: UtcDatetime


class AdminTurfUpdate(BaseModel):
    """``PUT /admin/turfs/{id}`` body."""

    is_active: bool


class AdminStats(BaseModel):
    """Platform-wide aggregate statistics (money in minor units)."""

    users_by_role: dict[UserRole, int]
    turfs_active: int
    bookings_by_status: dict[BookingStatus, int]
    gmv: int
    refunds: int
