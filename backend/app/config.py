"""Application settings loaded from environment variables and ``backend/.env``."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEV_SECRET_KEY = "dev-insecure-secret-key-change-me"  # noqa: S105 - dev fallback, warned at runtime


class Settings(BaseSettings):
    """Typed application configuration.

    Values come from process environment variables first, then ``backend/.env``.
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # App
    APP_NAME: str = "TurfSlot API"
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = "postgresql://turfslot:turfslot@localhost:5432/turfslot"
    TEST_DATABASE_URL: str | None = None

    # Auth
    SECRET_KEY: str = DEV_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_EXPIRE_MINUTES: int = 60
    EMAIL_VERIFY_EXPIRE_HOURS: int = 24
    # Google Sign-In (ID-token flow); empty disables it.
    GOOGLE_CLIENT_ID: str = ""

    # Booking rules
    BOOKING_HOLD_MINUTES: int = 10
    MAX_SLOTS_PER_BOOKING: int = 4
    BOOKING_WINDOW_DAYS: int = 30
    FREE_CANCELLATION_HOURS: int = 24
    DEFAULT_CURRENCY: str = "INR"
    SCHEDULER_ENABLED: bool = True

    # Dodo Payments
    DODO_PAYMENTS_API_KEY: str = ""
    DODO_PAYMENTS_WEBHOOK_SECRET: str = ""
    DODO_PAYMENTS_ENVIRONMENT: Literal["test_mode", "live_mode"] = "test_mode"
    DODO_BOOKING_PRODUCT_ID: str = ""

    # Email (SMTP; Mailpit in dev)
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "TurfSlot <no-reply@turfslot.local>"

    # URLs
    FRONTEND_URL: str = "http://localhost:5173"

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True

    @property
    def uses_dev_secret_key(self) -> bool:
        """Return True when the insecure built-in development SECRET_KEY is in use."""
        return self.SECRET_KEY == DEV_SECRET_KEY

    @property
    def uses_fake_payments(self) -> bool:
        """Return True when the fake payment gateway should be used."""
        return self.DODO_PAYMENTS_API_KEY.strip() in ("", "fake")


settings = Settings()
