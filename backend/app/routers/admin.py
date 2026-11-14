"""Admin endpoints (``/api/v1/admin``): user/turf moderation and platform stats.

``GET /admin/bookings`` is owned by the bookings module (separate router).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import require_role
from app.database import get_db
from app.models import User, UserRole
from app.schemas.admin import AdminStats, AdminTurfRead, AdminTurfUpdate, AdminUserUpdate
from app.schemas.common import ErrorResponse, Page, PaginationParams
from app.schemas.user import UserRead
from app.services import admin_service

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    responses={401: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)

require_admin = require_role(UserRole.admin)


@router.get("/users", response_model=Page[UserRead])
async def list_users(
    role: UserRole | None = Query(None, description="Filter by role"),
    q: str | None = Query(None, max_length=100, description="Email / full name contains"),
    is_active: bool | None = Query(None, description="Filter by active flag"),
    pagination: PaginationParams = Depends(),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Page[UserRead]:
    """List all users with optional filters."""
    users, total = admin_service.list_users(db, pagination, role=role, q=q, is_active=is_active)
    return Page[UserRead].create(
        [UserRead.model_validate(user) for user in users], total, pagination
    )


@router.put(
    "/users/{user_id}",
    response_model=UserRead,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def update_user(
    user_id: int,
    body: AdminUserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    """Change a user's role and/or active flag (not allowed on oneself)."""
    return admin_service.update_user(db, admin, user_id, body)


@router.get("/turfs", response_model=Page[AdminTurfRead])
async def list_turfs(
    q: str | None = Query(None, max_length=100, description="Name / slug contains"),
    city: str | None = Query(None, max_length=100, description="City (case-insensitive)"),
    is_active: bool | None = Query(None, description="Filter by active flag"),
    pagination: PaginationParams = Depends(),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Page[AdminTurfRead]:
    """List all turfs (active and inactive) with owner email."""
    turfs, total = admin_service.list_turfs(db, pagination, q=q, city=city, is_active=is_active)
    return Page[AdminTurfRead].create(turfs, total, pagination)


@router.put(
    "/turfs/{turf_id}",
    response_model=AdminTurfRead,
    responses={404: {"model": ErrorResponse}},
)
async def update_turf(
    turf_id: int,
    body: AdminTurfUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminTurfRead:
    """Activate or deactivate a turf."""
    return admin_service.update_turf(db, admin, turf_id, body)


@router.get("/stats", response_model=AdminStats)
async def stats(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminStats:
    """Platform-wide aggregate statistics."""
    return admin_service.get_stats(db)
