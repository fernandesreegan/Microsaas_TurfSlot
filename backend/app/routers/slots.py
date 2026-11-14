"""Slot availability and owner blocked-slot endpoints."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Body, Depends, Query, Response, status
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_optional_user
from app.database import get_db
from app.exceptions import BadRequestError
from app.models import User
from app.schemas.slot import BlockedSlotCreate, BlockedSlotRead, DaySlots
from app.services import availability, blocked_slot_service, turf_service

router = APIRouter(prefix="/turfs", tags=["slots"])

DEFAULT_BLOCK_LIST_DAYS = 7
MAX_BLOCKS_PER_REQUEST = 200


@router.get("/{turf_id}/slots", response_model=DaySlots)
async def get_slots(
    turf_id: int,
    date_: date | None = Query(
        None, alias="date", description="Turf-local date (defaults to today at the turf)"
    ),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> DaySlots:
    """Return the turf's slots for a local date with status and price.

    Dates outside ``[today, today + BOOKING_WINDOW_DAYS]`` give 400
    ``OUTSIDE_BOOKING_WINDOW``; the turf's owner and admins may query past dates.
    """
    turf = turf_service.get_visible_turf(db, turf_id, user)
    now = datetime.now(UTC)
    window_start, window_end = availability.booking_window(turf, now)
    local_date = date_ or window_start
    past_allowed = local_date < window_start and turf_service.can_manage(user, turf)
    if local_date > window_end or (local_date < window_start and not past_allowed):
        raise BadRequestError(
            f"Date must be between {window_start.isoformat()} and {window_end.isoformat()}",
            code="OUTSIDE_BOOKING_WINDOW",
        )
    return availability.get_day_slots(db, turf, local_date, now)


@router.get("/{turf_id}/blocked-slots", response_model=list[BlockedSlotRead])
async def list_blocked_slots(
    turf_id: int,
    from_: AwareDatetime | None = Query(None, alias="from", description="Range start (UTC)"),
    to: AwareDatetime | None = Query(None, description="Range end (UTC)"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BlockedSlotRead]:
    """List blocks overlapping ``[from, to)`` (default: the next 7 days)."""
    turf = turf_service.get_manageable_turf(db, turf_id, user)
    range_start = from_ or datetime.now(UTC)
    range_end = to or range_start + timedelta(days=DEFAULT_BLOCK_LIST_DAYS)
    if range_end <= range_start:
        raise BadRequestError("'to' must be after 'from'", code="INVALID_RANGE")
    blocks = blocked_slot_service.list_blocks(db, turf, range_start, range_end)
    return [BlockedSlotRead.model_validate(block) for block in blocks]


@router.post(
    "/{turf_id}/blocked-slots",
    response_model=list[BlockedSlotRead],
    status_code=status.HTTP_201_CREATED,
)
async def create_blocked_slots(
    turf_id: int,
    items: list[BlockedSlotCreate] = Body(..., min_length=1, max_length=MAX_BLOCKS_PER_REQUEST),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BlockedSlotRead]:
    """Block one or more grid-aligned ranges atomically."""
    turf = turf_service.get_manageable_turf(db, turf_id, user)
    blocks = blocked_slot_service.create_blocks(db, turf, user, items)
    return [BlockedSlotRead.model_validate(block) for block in blocks]


@router.delete("/{turf_id}/blocked-slots/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_blocked_slot(
    turf_id: int,
    block_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Remove a block."""
    turf = turf_service.get_manageable_turf(db, turf_id, user)
    blocked_slot_service.delete_block(db, turf, block_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
