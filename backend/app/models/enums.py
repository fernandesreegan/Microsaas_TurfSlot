"""Domain enums and their native PostgreSQL enum column types."""

from __future__ import annotations

import enum

from sqlalchemy import Enum as SAEnum


class UserRole(enum.StrEnum):
    """Account role."""

    player = "player"
    owner = "owner"
    admin = "admin"


class SportType(enum.StrEnum):
    """Sport a turf supports."""

    football = "football"
    cricket = "cricket"
    badminton = "badminton"
    tennis = "tennis"
    basketball = "basketball"
    pickleball = "pickleball"
    other = "other"


class BookingStatus(enum.StrEnum):
    """Booking lifecycle state."""

    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"
    completed = "completed"
    expired = "expired"


class CancelledBy(enum.StrEnum):
    """Actor that cancelled a booking."""

    player = "player"
    owner = "owner"
    admin = "admin"
    system = "system"


class RefundStatus(enum.StrEnum):
    """Refund state of a booking."""

    none = "none"
    pending = "pending"
    refunded = "refunded"
    failed = "failed"


class PaymentStatus(enum.StrEnum):
    """Payment state."""

    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    refunded = "refunded"
    refund_failed = "refund_failed"


def _values(enum_cls: type[enum.Enum]) -> list[str]:
    return [str(member.value) for member in enum_cls]


def pg_enum(enum_cls: type[enum.Enum], name: str) -> SAEnum:
    """Native PG enum type storing the lowercase ``.value`` of each member.

    ``create_type=False``-style behaviour is handled by the migration; metadata
    ``create_all`` (e.g. in tests) still creates the type automatically.
    """
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=_values,
        validate_strings=True,
    )


# Shared type instances (PG type names used in the migration).
user_role_enum = pg_enum(UserRole, "user_role")
sport_type_enum = pg_enum(SportType, "sport_type")
booking_status_enum = pg_enum(BookingStatus, "booking_status")
cancelled_by_enum = pg_enum(CancelledBy, "cancelled_by")
refund_status_enum = pg_enum(RefundStatus, "refund_status")
payment_status_enum = pg_enum(PaymentStatus, "payment_status")
