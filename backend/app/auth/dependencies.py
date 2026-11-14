"""FastAPI dependencies for authentication and authorization."""

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.database import get_db
from app.exceptions import ForbiddenError, UnauthorizedError
from app.models import User
from app.models.enums import UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def _user_from_token(db: Session, token: str | None) -> User:
    """Resolve and validate the user referenced by a bearer access token.

    Raises:
        UnauthorizedError: Missing/invalid/expired token or unknown user (401).
        ForbiddenError: The account is deactivated (403, code ``ACCOUNT_INACTIVE``).
    """
    if not token:
        raise UnauthorizedError("Not authenticated", code="NOT_AUTHENTICATED")
    payload = decode_access_token(token)
    if payload is None:
        raise UnauthorizedError("Invalid or expired token", code="INVALID_TOKEN")
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise UnauthorizedError("Invalid or expired token", code="INVALID_TOKEN") from exc
    user = db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("User not found", code="INVALID_TOKEN")
    if not user.is_active:
        raise ForbiddenError("Account is deactivated", code="ACCOUNT_INACTIVE")
    return user


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Return the authenticated, active user from the ``Authorization: Bearer`` header."""
    return _user_from_token(db, token)


async def get_optional_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Return the authenticated user, or None when no/invalid token is supplied.

    Useful on public endpoints whose behaviour differs for logged-in users
    (e.g. owners viewing past dates of their own turf).
    """
    if not token:
        return None
    try:
        return _user_from_token(db, token)
    except (UnauthorizedError, ForbiddenError):
        return None


def require_role(*roles: UserRole) -> Callable[..., Coroutine[Any, Any, User]]:
    """Build a dependency that only admits users whose role is in ``roles``.

    Example::

        @router.get("/owner/turfs")
        async def my_turfs(user: User = Depends(require_role(UserRole.owner))): ...

    Raises:
        ForbiddenError: 403 with code ``FORBIDDEN`` when the role is not allowed.
    """
    allowed = frozenset(roles)

    async def _dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise ForbiddenError("You do not have permission to perform this action")
        return user

    return _dependency


async def require_verified(user: User = Depends(get_current_user)) -> User:
    """Admit only users with a verified email.

    Raises:
        ForbiddenError: 403 with code ``EMAIL_NOT_VERIFIED``.
    """
    if not user.is_verified:
        raise ForbiddenError("Please verify your email address first", code="EMAIL_NOT_VERIFIED")
    return user
