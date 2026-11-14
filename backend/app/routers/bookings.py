"""Booking endpoints: create, checkout, list, detail, cancel."""

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import (
    PaginationParams,
    get_current_user,
    get_db,
    get_payment_gateway,
    require_verified,
)
from app.models import BookingStatus, User
from app.schemas.booking import BookingCheckout, BookingCreate, BookingRead, CancelRequest
from app.schemas.common import Page
from app.services import booking_service
from app.services.booking_notifications import dispatch
from app.services.payment_gateway import PaymentGateway

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=BookingCheckout, status_code=201)
async def create_booking(
    data: BookingCreate,
    user: User = Depends(require_verified),
    db: Session = Depends(get_db),
    gateway: PaymentGateway = Depends(get_payment_gateway),
) -> BookingCheckout:
    """Create a pending booking (hold) and return the checkout URL."""
    outcome = booking_service.create_booking(db, user, data, gateway)
    return BookingCheckout(
        booking=BookingRead.from_booking(outcome.booking), checkout_url=outcome.checkout_url
    )


@router.get("/me", response_model=Page[BookingRead])
async def my_bookings(
    scope: Literal["upcoming", "past"] | None = Query(None),
    status: BookingStatus | None = Query(None),
    pagination: PaginationParams = Depends(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Page[BookingRead]:
    """List the current user's bookings."""
    items, total = booking_service.list_player_bookings(db, user, pagination, scope, status)
    return Page[BookingRead].create([BookingRead.from_booking(b) for b in items], total, pagination)


@router.get("/{booking_id}", response_model=BookingRead)
async def get_booking(
    booking_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BookingRead:
    """Booking detail for its player, the turf owner or an admin (404 otherwise)."""
    return BookingRead.from_booking(booking_service.get_visible_booking(db, booking_id, user))


@router.post("/{booking_id}/checkout", response_model=BookingCheckout)
async def renew_checkout(
    booking_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gateway: PaymentGateway = Depends(get_payment_gateway),
) -> BookingCheckout:
    """New checkout URL while the hold is valid (409 ``HOLD_EXPIRED`` otherwise)."""
    outcome = booking_service.renew_checkout(db, booking_id, user, gateway)
    return BookingCheckout(
        booking=BookingRead.from_booking(outcome.booking), checkout_url=outcome.checkout_url
    )


@router.post("/{booking_id}/cancel", response_model=BookingRead)
async def cancel_booking(
    booking_id: int,
    background_tasks: BackgroundTasks,
    body: CancelRequest | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    gateway: PaymentGateway = Depends(get_payment_gateway),
) -> BookingRead:
    """Cancel a booking applying the refund policy; emails player and owner."""
    reason = body.reason if body else None
    booking, jobs = booking_service.cancel_booking(db, booking_id, user, gateway, reason)
    dispatch(background_tasks, jobs)
    return BookingRead.from_booking(booking)
