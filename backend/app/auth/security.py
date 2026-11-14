"""Password hashing, JWT access tokens and opaque random tokens."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.config import settings

ACCESS_TOKEN_TYPE = "access"  # noqa: S105 - token type label, not a secret
# bcrypt only uses the first 72 bytes; bcrypt>=5 raises on longer input, so truncate explicitly.
_BCRYPT_MAX_BYTES = 72


def _password_bytes(password: str) -> bytes:
    """Encode a password to bytes truncated to bcrypt's 72-byte limit."""
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Hash a plain password with bcrypt.

    Args:
        password: Plain-text password.

    Returns:
        The bcrypt hash as a UTF-8 string.
    """
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plain password against a bcrypt hash.

    Returns:
        True if it matches; False on mismatch or malformed hash.
    """
    try:
        return bcrypt.checkpw(_password_bytes(plain_password), hashed_password.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(
    subject: str | int,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token.

    Args:
        subject: The user id (stored as the ``sub`` claim, stringified).
        extra_claims: Optional additional claims (e.g. ``{"role": "owner"}``).
        expires_delta: Override for ``ACCESS_TOKEN_EXPIRE_MINUTES``.

    Returns:
        Encoded JWT string with ``sub``, ``exp``, ``iat`` and ``type="access"`` claims.
    """
    now = datetime.now(UTC)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload: dict[str, Any] = {
        **(extra_claims or {}),
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": ACCESS_TOKEN_TYPE,
    }
    return str(jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM))


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT access token.

    Returns:
        The claims dict, or None if the token is invalid, expired or not an access token.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        return None
    if payload.get("type") != ACCESS_TOKEN_TYPE or not payload.get("sub"):
        return None
    return payload


def generate_token() -> str:
    """Generate a random 32-byte URL-safe token (refresh / reset / verify tokens)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Return the hex sha256 digest of an opaque token, for storage/lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
