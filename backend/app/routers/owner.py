"""Owner dashboard, turfs and bookings endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import require_role
from app.database import get_db
from app.models import User, UserRole
from app.schemas.turf import TurfRead
from app.services import turf_service

router = APIRouter(prefix="/owner", tags=["owner"])


@router.get("/turfs", response_model=list[TurfRead])
async def list_my_turfs(
    user: User = Depends(require_role(UserRole.owner)),
    db: Session = Depends(get_db),
) -> list[TurfRead]:
    """Return the current owner's turfs, including inactive ones."""
    return [TurfRead.model_validate(turf) for turf in turf_service.list_owner_turfs(db, user)]
