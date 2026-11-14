"""Turf search/CRUD and pricing-rule endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
    get_optional_user,
    require_role,
    require_verified,
)
from app.database import get_db
from app.models import SportType, User, UserRole
from app.schemas.common import Page, PaginationParams
from app.schemas.turf import (
    PricingRuleCreate,
    PricingRuleRead,
    PricingRuleUpdate,
    TurfCreate,
    TurfDetail,
    TurfRead,
    TurfUpdate,
)
from app.services import turf_service

router = APIRouter(prefix="/turfs", tags=["turfs"])


@router.get("", response_model=Page[TurfRead])
async def search_turfs(
    city: str | None = Query(None, max_length=100, description="City (case-insensitive)"),
    sport: SportType | None = Query(None, description="Sport the turf must support"),
    q: str | None = Query(None, max_length=120, description="Substring of the turf name"),
    date_: date | None = Query(
        None, alias="date", description="Turf-local date with at least one available slot"
    ),
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
) -> Page[TurfRead]:
    """Search active turfs by city, sport, name and (best-effort) availability date."""
    filters = turf_service.TurfSearch(city=city, sport=sport, q=q, local_date=date_)
    items, total = turf_service.search_turfs(db, filters, pagination.offset, pagination.limit)
    return Page[TurfRead].create(
        [TurfRead.model_validate(turf) for turf in items], total, pagination
    )


@router.post("", response_model=TurfRead, status_code=status.HTTP_201_CREATED)
async def create_turf(
    data: TurfCreate,
    user: User = Depends(require_role(UserRole.owner)),
    _verified: User = Depends(require_verified),
    db: Session = Depends(get_db),
) -> TurfRead:
    """Create a turf owned by the current (verified) owner."""
    turf = turf_service.create_turf(db, user, data)
    return TurfRead.model_validate(turf)


@router.get("/{id_or_slug}", response_model=TurfDetail)
async def get_turf(
    id_or_slug: str,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> TurfDetail:
    """Return a turf by id or slug, with its pricing rules.

    Inactive turfs are visible only to their owner and admins.
    """
    turf = turf_service.get_visible_turf(db, id_or_slug, user)
    return TurfDetail.model_validate(turf)


@router.put("/{turf_id}", response_model=TurfRead)
async def update_turf(
    turf_id: int,
    data: TurfUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TurfRead:
    """Partially update a turf (owner of the turf or admin)."""
    turf = turf_service.get_manageable_turf(db, turf_id, user)
    return TurfRead.model_validate(turf_service.update_turf(db, turf, data))


@router.delete("/{turf_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_turf(
    turf_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Soft-deactivate a turf; 409 if it has upcoming confirmed bookings."""
    turf = turf_service.get_manageable_turf(db, turf_id, user)
    turf_service.deactivate_turf(db, turf)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{turf_id}/pricing-rules", response_model=list[PricingRuleRead])
async def list_pricing_rules(
    turf_id: int,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> list[PricingRuleRead]:
    """List a turf's pricing rules (public for active turfs)."""
    turf = turf_service.get_visible_turf(db, turf_id, user)
    return [PricingRuleRead.model_validate(r) for r in turf_service.list_pricing_rules(db, turf)]


@router.post(
    "/{turf_id}/pricing-rules",
    response_model=PricingRuleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_pricing_rule(
    turf_id: int,
    data: PricingRuleCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PricingRuleRead:
    """Create a pricing rule; 409 ``OVERLAPPING_RULE`` on overlap."""
    turf = turf_service.get_manageable_turf(db, turf_id, user)
    return PricingRuleRead.model_validate(turf_service.create_pricing_rule(db, turf, data))


@router.put("/{turf_id}/pricing-rules/{rule_id}", response_model=PricingRuleRead)
async def update_pricing_rule(
    turf_id: int,
    rule_id: int,
    data: PricingRuleUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PricingRuleRead:
    """Replace a pricing rule; 409 ``OVERLAPPING_RULE`` on overlap."""
    turf = turf_service.get_manageable_turf(db, turf_id, user)
    rule = turf_service.get_pricing_rule(db, turf, rule_id)
    return PricingRuleRead.model_validate(turf_service.update_pricing_rule(db, turf, rule, data))


@router.delete("/{turf_id}/pricing-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pricing_rule(
    turf_id: int,
    rule_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Delete a pricing rule."""
    turf = turf_service.get_manageable_turf(db, turf_id, user)
    turf_service.delete_pricing_rule(db, turf_service.get_pricing_rule(db, turf, rule_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
