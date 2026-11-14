"""User account and its auth token tables."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, false, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import CreatedAtMixin, TimestampMixin
from app.models.enums import UserRole, user_role_enum

if TYPE_CHECKING:
    from app.models.booking import Booking
    from app.models.turf import Turf


class User(TimestampMixin, Base):
    """A player, turf owner or admin. ``email`` is stored lowercased."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(20))
    role: Mapped[UserRole] = mapped_column(
        user_role_enum, default=UserRole.player, server_default=UserRole.player.value
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    turfs: Mapped[list[Turf]] = relationship(back_populates="owner")
    bookings: Mapped[list[Booking]] = relationship(back_populates="player")
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    password_reset_tokens: Mapped[list[PasswordResetToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    email_verification_tokens: Mapped[list[EmailVerificationToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role}>"


class RefreshToken(CreatedAtMixin, Base):
    """Hashed (sha256) refresh token; rotated on use."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())

    user: Mapped[User] = relationship(back_populates="refresh_tokens")


class PasswordResetToken(CreatedAtMixin, Base):
    """Hashed single-use password reset token (1h expiry)."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="password_reset_tokens")


class EmailVerificationToken(CreatedAtMixin, Base):
    """Hashed single-use email verification token (24h expiry)."""

    __tablename__ = "email_verification_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="email_verification_tokens")
