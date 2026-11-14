"""Authentication business logic: accounts, token pairs, and email tokens.

Refresh, password-reset and email-verification tokens are random URL-safe strings
(``generate_token``); only their sha256 hash (``hash_token``) is stored.

Refresh tokens rotate on every use. Presenting a refresh token that has already been
revoked is treated as token theft: every refresh token of that user is revoked.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.security import (
    create_access_token,
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.config import settings
from app.exceptions import BadRequestError, ConflictError, ForbiddenError, UnauthorizedError
from app.models import EmailVerificationToken, PasswordResetToken, RefreshToken, User, UserRole
from app.schemas.auth import RegisterRequest, TokenPair
from app.schemas.user import UserUpdate

logger = logging.getLogger(__name__)

# Pre-computed hash used to equalize login timing when the email does not exist.
_DUMMY_PASSWORD_HASH = hash_password("timing-equalizer-0")


@dataclass(frozen=True)
class EmailLink:
    """An action link to email to a user (verification or password reset)."""

    user: User
    action_url: str
    expires_text: str


def _now() -> datetime:
    return datetime.now(UTC)


def _humanize_duration(delta: timedelta) -> str:
    """Render a duration such as ``1 hour`` / ``24 hours`` / ``30 minutes``."""
    minutes = int(delta.total_seconds() // 60)
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} hour" if hours == 1 else f"{hours} hours"
    return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"


def _frontend_link(path: str, token: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}{path}?token={token}"


def get_user_by_email(db: Session, email: str) -> User | None:
    """Return the user with this (case-insensitive) email, or None."""
    return db.scalar(select(User).where(User.email == email.strip().lower()))


# ---------------------------------------------------------------------------
# Registration / login
# ---------------------------------------------------------------------------


def register_user(db: Session, data: RegisterRequest) -> tuple[User, EmailLink]:
    """Create a player/owner account and an email-verification token.

    Returns:
        The new user and the verification link to email.

    Raises:
        ConflictError: 409 ``EMAIL_TAKEN`` if the email is already registered.
    """
    email = data.email.lower()
    if get_user_by_email(db, email) is not None:
        raise ConflictError("An account with this email already exists", code="EMAIL_TAKEN")
    user = User(
        email=email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        phone=data.phone,
        role=UserRole(data.role),
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:  # concurrent registration with the same email
        db.rollback()
        raise ConflictError(
            "An account with this email already exists", code="EMAIL_TAKEN"
        ) from exc
    link = _create_verification_link(db, user)
    db.commit()
    db.refresh(user)
    logger.info("Registered user id=%s role=%s", user.id, user.role.value)
    return user, link


def authenticate(db: Session, email: str, password: str) -> User:
    """Validate credentials.

    Raises:
        UnauthorizedError: 401 ``INVALID_CREDENTIALS`` on unknown email or wrong password.
        ForbiddenError: 403 ``ACCOUNT_INACTIVE`` if the (correctly authenticated) account
            is deactivated.
    """
    user = get_user_by_email(db, email)
    if user is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        raise UnauthorizedError("Invalid email or password", code="INVALID_CREDENTIALS")
    if not verify_password(password, user.hashed_password):
        raise UnauthorizedError("Invalid email or password", code="INVALID_CREDENTIALS")
    if not user.is_active:
        raise ForbiddenError("Account is deactivated", code="ACCOUNT_INACTIVE")
    return user


def _new_refresh_token(db: Session, user_id: int) -> str:
    raw = generate_token()
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=hash_token(raw),
            expires_at=_now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            revoked=False,
        )
    )
    return raw


def issue_token_pair(db: Session, user: User) -> TokenPair:
    """Create an access token and a stored refresh token for ``user`` (commits)."""
    refresh = _new_refresh_token(db, user.id)
    db.commit()
    access = create_access_token(user.id, extra_claims={"role": user.role.value})
    return TokenPair(access_token=access, refresh_token=refresh)


def revoke_all_refresh_tokens(db: Session, user_id: int, *, except_hash: str | None = None) -> int:
    """Revoke every non-revoked refresh token of a user (does not commit).

    Args:
        except_hash: Optional token hash to keep (the caller's current session).

    Returns:
        Number of tokens revoked.
    """
    stmt = (
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
    if except_hash is not None:
        stmt = stmt.where(RefreshToken.token_hash != except_hash)
    result = db.execute(stmt.execution_options(synchronize_session=False))
    return int(getattr(result, "rowcount", 0) or 0)


def rotate_refresh_token(db: Session, raw_token: str) -> TokenPair:
    """Exchange a valid refresh token for a new pair, revoking the old one.

    Raises:
        UnauthorizedError: 401 ``INVALID_REFRESH_TOKEN`` for unknown/expired tokens and
            ``REFRESH_TOKEN_REUSED`` for an already-revoked token (all of the user's
            refresh tokens are then revoked).
        ForbiddenError: 403 ``ACCOUNT_INACTIVE`` for deactivated accounts.
    """
    token = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(raw_token))
        .with_for_update()
    )
    if token is None:
        db.rollback()
        raise UnauthorizedError("Invalid refresh token", code="INVALID_REFRESH_TOKEN")
    if token.revoked:
        revoked = revoke_all_refresh_tokens(db, token.user_id)
        db.commit()
        logger.warning(
            "Refresh token reuse detected for user id=%s; revoked %s tokens",
            token.user_id,
            revoked,
        )
        raise UnauthorizedError("Refresh token has been revoked", code="REFRESH_TOKEN_REUSED")
    if token.expires_at <= _now():
        token.revoked = True
        db.commit()
        raise UnauthorizedError("Refresh token has expired", code="INVALID_REFRESH_TOKEN")
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        token.revoked = True
        db.commit()
        raise ForbiddenError("Account is deactivated", code="ACCOUNT_INACTIVE")
    token.revoked = True
    return issue_token_pair(db, user)


def logout(db: Session, user: User, raw_token: str) -> None:
    """Revoke one refresh token belonging to ``user``. Unknown tokens are ignored."""
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_token(raw_token),
            RefreshToken.user_id == user.id,
        )
        .values(revoked=True)
        .execution_options(synchronize_session=False)
    )
    db.commit()


# ---------------------------------------------------------------------------
# Profile / password
# ---------------------------------------------------------------------------


def update_profile(db: Session, user: User, data: UserUpdate) -> User:
    """Apply a partial profile update (``full_name``, ``phone``)."""
    changes = data.model_dump(exclude_unset=True)
    if "full_name" in changes and changes["full_name"] is not None:
        user.full_name = changes["full_name"]
    if "phone" in changes:
        user.phone = changes["phone"]
    db.commit()
    db.refresh(user)
    return user


def change_password(
    db: Session,
    user: User,
    current_password: str,
    new_password: str,
    keep_refresh_token: str | None = None,
) -> None:
    """Change the password after verifying the current one.

    Revokes every refresh token except ``keep_refresh_token`` (if given).

    Raises:
        BadRequestError: 400 ``INVALID_CURRENT_PASSWORD``.
    """
    if not verify_password(current_password, user.hashed_password):
        raise BadRequestError("Current password is incorrect", code="INVALID_CURRENT_PASSWORD")
    user.hashed_password = hash_password(new_password)
    keep_hash = hash_token(keep_refresh_token) if keep_refresh_token else None
    revoke_all_refresh_tokens(db, user.id, except_hash=keep_hash)
    db.commit()
    logger.info("Password changed for user id=%s", user.id)


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


def _create_verification_link(db: Session, user: User) -> EmailLink:
    raw = generate_token()
    ttl = timedelta(hours=settings.EMAIL_VERIFY_EXPIRE_HOURS)
    db.add(
        EmailVerificationToken(user_id=user.id, token_hash=hash_token(raw), expires_at=_now() + ttl)
    )
    return EmailLink(
        user=user,
        action_url=_frontend_link("/verify-email", raw),
        expires_text=_humanize_duration(ttl),
    )


def create_verification_link(db: Session, user: User) -> EmailLink:
    """Issue a new email-verification token for an unverified user (commits).

    Raises:
        BadRequestError: 400 ``ALREADY_VERIFIED``.
    """
    if user.is_verified:
        raise BadRequestError("Email is already verified", code="ALREADY_VERIFIED")
    link = _create_verification_link(db, user)
    db.commit()
    return link


def verify_email(db: Session, raw_token: str) -> User:
    """Consume a verification token and mark the user verified.

    Raises:
        BadRequestError: 400 ``INVALID_OR_EXPIRED_TOKEN`` for unknown, used or expired tokens.
    """
    token = db.scalar(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.token_hash == hash_token(raw_token))
        .with_for_update()
    )
    if token is None or token.used_at is not None or token.expires_at <= _now():
        db.rollback()
        raise BadRequestError(
            "Verification link is invalid or has expired", code="INVALID_OR_EXPIRED_TOKEN"
        )
    user = db.get(User, token.user_id)
    if user is None:  # pragma: no cover - FK cascade makes this impossible
        db.rollback()
        raise BadRequestError(
            "Verification link is invalid or has expired", code="INVALID_OR_EXPIRED_TOKEN"
        )
    token.used_at = _now()
    user.is_verified = True
    db.commit()
    db.refresh(user)
    logger.info("Email verified for user id=%s", user.id)
    return user


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


def create_password_reset_link(db: Session, email: str) -> EmailLink | None:
    """Issue a password-reset token if an account exists for ``email`` (commits).

    Returns None (silently) when no such user exists so callers cannot enumerate accounts.
    Inactive accounts are treated as non-existent.
    """
    user = get_user_by_email(db, email)
    if user is None or not user.is_active:
        return None
    raw = generate_token()
    ttl = timedelta(minutes=settings.PASSWORD_RESET_EXPIRE_MINUTES)
    db.add(PasswordResetToken(user_id=user.id, token_hash=hash_token(raw), expires_at=_now() + ttl))
    db.commit()
    return EmailLink(
        user=user,
        action_url=_frontend_link("/reset-password", raw),
        expires_text=_humanize_duration(ttl),
    )


def reset_password(db: Session, raw_token: str, new_password: str) -> User:
    """Consume a reset token, set the new password and revoke all refresh tokens.

    Raises:
        BadRequestError: 400 ``INVALID_OR_EXPIRED_TOKEN`` for unknown, used or expired tokens.
    """
    token = db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == hash_token(raw_token))
        .with_for_update()
    )
    if token is None or token.used_at is not None or token.expires_at <= _now():
        db.rollback()
        raise BadRequestError(
            "Reset link is invalid or has expired", code="INVALID_OR_EXPIRED_TOKEN"
        )
    user = db.get(User, token.user_id)
    if user is None:  # pragma: no cover - FK cascade makes this impossible
        db.rollback()
        raise BadRequestError(
            "Reset link is invalid or has expired", code="INVALID_OR_EXPIRED_TOKEN"
        )
    now = _now()
    token.used_at = now
    # Invalidate any other outstanding reset links for this user.
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    user.hashed_password = hash_password(new_password)
    revoke_all_refresh_tokens(db, user.id)
    db.commit()
    db.refresh(user)
    logger.info("Password reset for user id=%s", user.id)
    return user
