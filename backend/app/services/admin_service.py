"""Admin panel business logic: user/turf moderation and platform statistics."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.exceptions import BadRequestError, NotFoundError
from app.models import Booking, BookingStatus, RefundStatus, Turf, User, UserRole
from app.schemas.admin import AdminStats, AdminTurfRead, AdminTurfUpdate, AdminUserUpdate
from app.schemas.common import PaginationParams
from app.services.auth_service import revoke_all_refresh_tokens

logger = logging.getLogger(__name__)

GMV_STATUSES: tuple[BookingStatus, ...] = (BookingStatus.confirmed, BookingStatus.completed)


def _like_pattern(term: str) -> str:
    """Build a ``%term%`` ILIKE pattern with ``%``, ``_`` and ``\\`` escaped."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _count(db: Session, stmt: Select) -> int:
    """Return ``COUNT(*)`` of a select statement (ordering removed)."""
    return int(db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def list_users(
    db: Session,
    pagination: PaginationParams,
    *,
    role: UserRole | None = None,
    q: str | None = None,
    is_active: bool | None = None,
) -> tuple[Sequence[User], int]:
    """List users (newest first) filtered by role, activity and email/name substring."""
    stmt = select(User)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    if q and q.strip():
        pattern = _like_pattern(q.strip())
        stmt = stmt.where(
            or_(User.email.ilike(pattern, escape="\\"), User.full_name.ilike(pattern, escape="\\"))
        )
    total = _count(db, stmt)
    users = db.scalars(
        stmt.order_by(User.created_at.desc(), User.id.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    ).all()
    return users, total


def update_user(db: Session, admin: User, user_id: int, data: AdminUserUpdate) -> User:
    """Activate/deactivate a user or change their role.

    Deactivation revokes all of the user's refresh tokens.

    Raises:
        NotFoundError: Unknown user.
        BadRequestError: 400 ``CANNOT_MODIFY_SELF`` when an admin deactivates or demotes
            themselves.
    """
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    if user.id == admin.id and (
        data.is_active is False or (data.role is not None and data.role != UserRole.admin)
    ):
        raise BadRequestError(
            "Admins cannot deactivate or demote themselves", code="CANNOT_MODIFY_SELF"
        )
    if data.role is not None and data.role != user.role:
        logger.info(
            "Admin id=%s changed role of user id=%s: %s -> %s",
            admin.id,
            user.id,
            user.role.value,
            data.role.value,
        )
        user.role = data.role
    if data.is_active is not None and data.is_active != user.is_active:
        user.is_active = data.is_active
        if not data.is_active:
            revoke_all_refresh_tokens(db, user.id)
        logger.info(
            "Admin id=%s set is_active=%s for user id=%s", admin.id, data.is_active, user.id
        )
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Turfs
# ---------------------------------------------------------------------------


def _turf_rows_stmt() -> Select:
    return select(
        Turf.id,
        Turf.name,
        Turf.slug,
        Turf.city_display.label("city"),
        Turf.owner_id,
        User.email.label("owner_email"),
        Turf.is_active,
        Turf.created_at,
    ).join(User, User.id == Turf.owner_id)


def list_turfs(
    db: Session,
    pagination: PaginationParams,
    *,
    q: str | None = None,
    city: str | None = None,
    is_active: bool | None = None,
) -> tuple[list[AdminTurfRead], int]:
    """List all turfs (newest first) with their owner's email, in a single joined query."""
    stmt = _turf_rows_stmt()
    if q and q.strip():
        pattern = _like_pattern(q.strip())
        stmt = stmt.where(
            or_(Turf.name.ilike(pattern, escape="\\"), Turf.slug.ilike(pattern, escape="\\"))
        )
    if city and city.strip():
        stmt = stmt.where(Turf.city == city.strip().lower())
    if is_active is not None:
        stmt = stmt.where(Turf.is_active.is_(is_active))
    total = _count(db, stmt)
    rows = db.execute(
        stmt.order_by(Turf.created_at.desc(), Turf.id.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    ).mappings()
    return [AdminTurfRead.model_validate(dict(row)) for row in rows], total


def update_turf(db: Session, admin: User, turf_id: int, data: AdminTurfUpdate) -> AdminTurfRead:
    """Activate or deactivate any turf.

    Raises:
        NotFoundError: Unknown turf.
    """
    turf = db.get(Turf, turf_id)
    if turf is None:
        raise NotFoundError("Turf not found")
    if turf.is_active != data.is_active:
        turf.is_active = data.is_active
        db.commit()
        logger.info(
            "Admin id=%s set is_active=%s for turf id=%s", admin.id, data.is_active, turf_id
        )
    row = db.execute(_turf_rows_stmt().where(Turf.id == turf_id)).mappings().one()
    return AdminTurfRead.model_validate(dict(row))


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def get_stats(db: Session) -> AdminStats:
    """Compute platform-wide statistics with aggregate SQL (four small queries)."""
    users_by_role: dict[UserRole, int] = dict.fromkeys(UserRole, 0)
    for role, count in db.execute(select(User.role, func.count()).group_by(User.role)).all():
        users_by_role[UserRole(role)] = int(count)

    bookings_by_status: dict[BookingStatus, int] = dict.fromkeys(BookingStatus, 0)
    for booking_status, count in db.execute(
        select(Booking.status, func.count()).group_by(Booking.status)
    ).all():
        bookings_by_status[BookingStatus(booking_status)] = int(count)

    turfs_active = int(
        db.scalar(select(func.count()).select_from(Turf).where(Turf.is_active.is_(True))) or 0
    )

    money = db.execute(
        select(
            func.coalesce(
                func.sum(Booking.total_amount).filter(Booking.status.in_(GMV_STATUSES)), 0
            ),
            func.coalesce(
                func.sum(Booking.total_amount).filter(
                    Booking.refund_status == RefundStatus.refunded
                ),
                0,
            ),
        )
    ).one()

    return AdminStats(
        users_by_role=users_by_role,
        turfs_active=turfs_active,
        bookings_by_status=bookings_by_status,
        gmv=int(money[0]),
        refunds=int(money[1]),
    )
