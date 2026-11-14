"""Authentication request/response schemas."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


def validate_password_policy(password: str) -> str:
    """Enforce the password policy: >= 8 chars with at least one letter and one digit.

    Raises:
        ValueError: If the password does not satisfy the policy.
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Password must be at most {PASSWORD_MAX_LENGTH} characters")
    if not any(ch.isalpha() for ch in password):
        raise ValueError("Password must contain at least one letter")
    if not any(ch.isdigit() for ch in password):
        raise ValueError("Password must contain at least one digit")
    return password


def normalize_email(value: str) -> str:
    """Trim and lowercase an email address."""
    return value.strip().lower()


class RegisterRequest(BaseModel):
    """``POST /auth/register`` body. Only ``player`` and ``owner`` may self-register."""

    email: EmailStr
    password: str
    full_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    role: Literal["player", "owner"] = "player"

    @field_validator("email")
    @classmethod
    def _lower_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("password")
    @classmethod
    def _check_password(cls, value: str) -> str:
        return validate_password_policy(value)

    @field_validator("full_name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("full_name must not be blank")
        return value

    @field_validator("phone")
    @classmethod
    def _strip_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class LoginRequest(BaseModel):
    """``POST /auth/login`` JSON body."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("email")
    @classmethod
    def _lower_email(cls, value: str) -> str:
        return normalize_email(value)


class TokenPair(BaseModel):
    """Access + refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - OAuth token type label


class RefreshRequest(BaseModel):
    """``POST /auth/refresh`` body."""

    refresh_token: str = Field(min_length=1, max_length=512)


class LogoutRequest(BaseModel):
    """``POST /auth/logout`` body."""

    refresh_token: str = Field(min_length=1, max_length=512)


class ChangePasswordRequest(BaseModel):
    """``POST /auth/change-password`` body.

    ``refresh_token`` (optional) identifies the caller's current session so it is kept;
    every *other* refresh token is revoked. If omitted, all refresh tokens are revoked.
    """

    current_password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    new_password: str
    refresh_token: str | None = Field(default=None, max_length=512)

    @field_validator("new_password")
    @classmethod
    def _check_password(cls, value: str) -> str:
        return validate_password_policy(value)


class ForgotPasswordRequest(BaseModel):
    """``POST /auth/forgot-password`` body."""

    email: EmailStr

    @field_validator("email")
    @classmethod
    def _lower_email(cls, value: str) -> str:
        return normalize_email(value)


class ResetPasswordRequest(BaseModel):
    """``POST /auth/reset-password`` body."""

    token: str = Field(min_length=1, max_length=512)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _check_password(cls, value: str) -> str:
        return validate_password_policy(value)


class VerifyEmailRequest(BaseModel):
    """``POST /auth/verify-email`` body."""

    token: str = Field(min_length=1, max_length=512)


class MessageResponse(BaseModel):
    """Simple acknowledgement body."""

    message: str


class GoogleLoginRequest(BaseModel):
    """``POST /auth/google`` body: a Google Identity Services ID token (``credential``)."""

    credential: str = Field(min_length=1, max_length=4096)
    role: Literal["player", "owner"] = "player"


class AuthConfig(BaseModel):
    """Public auth configuration discovered by the frontend at runtime."""

    google_client_id: str | None
