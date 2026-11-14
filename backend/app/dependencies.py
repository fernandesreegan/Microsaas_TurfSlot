"""Shared FastAPI dependencies re-exported for convenient imports in routers."""

from app.auth.dependencies import (
    get_current_user,
    get_optional_user,
    require_role,
    require_verified,
)
from app.database import get_db
from app.schemas.common import PaginationParams
from app.services.payment_gateway import get_payment_gateway

__all__ = [
    "PaginationParams",
    "get_current_user",
    "get_db",
    "get_optional_user",
    "get_payment_gateway",
    "require_role",
    "require_verified",
]
