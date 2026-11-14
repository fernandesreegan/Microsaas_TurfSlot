"""Owner bookings list and dashboard endpoints."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import PaginationParams, get_db, require_role
from app.models import BookingStatus, User, UserRole
from app.schemas.booking import BookingRead
from app.schemas.common import Page
from app.schemas.dashboard import OwnerSummary, RevenuePoint
from app.services import dashboard_service

router = APIRouter(prefix="/owner", tags=["owner"])

_owner = require_role(UserRole.owner)


@router.get("/bookings", response_model=Page[BookingRead])
async def owner_bookings(
    turf_id: int | None = Query(None),
    local_date: date | None = Query(None, alias="date"),
    status: BookingStatus | None = Query(None),
    pagination: PaginationParams = Depends(),
    owner: User = Depends(_owner),
    db: Session = Depends(get_db),
) -> Page[BookingRead]:
    """Bookings on the owner's turfs (``date`` is the turf-local date)."""
    items, total = dashboard_service.list_owner_bookings(
        db, owner, pagination, turf_id, local_date, status
    )
    return Page[BookingRead].create([BookingRead.from_booking(b) for b in items], total, pagination)


@router.get("/dashboard/summary", response_model=OwnerSummary)
async def dashboard_summary(
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    turf_id: int | None = Query(None),
    owner: User = Depends(_owner),
    db: Session = Depends(get_db),
) -> OwnerSummary:
    """KPI summary (defaults to today in each turf's timezone)."""
    return dashboard_service.owner_summary(db, owner, date_from, date_to, turf_id)


@router.get("/dashboard/revenue", response_model=list[RevenuePoint])
async def dashboard_revenue(
    date_from: date | None = Query(None, alias="from"),
    date_to: date | None = Query(None, alias="to"),
    group_by: Literal["day", "week"] = Query("day"),
    turf_id: int | None = Query(None),
    owner: User = Depends(_owner),
    db: Session = Depends(get_db),
) -> list[RevenuePoint]:
    """Revenue per local day/week (defaults to the last 30 days)."""
    return dashboard_service.revenue_series(db, owner, date_from, date_to, group_by, turf_id)
