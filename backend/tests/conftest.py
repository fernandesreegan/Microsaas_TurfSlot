"""Shared pytest fixtures for the TurfSlot backend.

Tests run against a real PostgreSQL database (``TEST_DATABASE_URL``) because the
schema relies on Postgres-only features (exclusion constraints, tstzrange, arrays).

Isolation strategy: the schema is migrated once per session with Alembic, and every
table is truncated after each test. Tests may therefore commit freely (needed for
concurrency tests that use several sessions/threads).
"""

from __future__ import annotations

import os

# --- Configure the environment BEFORE any ``app`` import -------------------------
os.environ.setdefault(
    "TEST_DATABASE_URL", "postgresql://turfslot:turfslot@localhost:5433/turfslot_test"
)
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["DODO_PAYMENTS_API_KEY"] = "fake"
os.environ["DODO_PAYMENTS_WEBHOOK_SECRET"] = ""
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ["FRONTEND_URL"] = "http://localhost:5173"

import importlib
from collections.abc import Callable, Generator, Iterator
from datetime import time
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from alembic import command
from app.auth.security import create_access_token, hash_password
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import SportType, Turf, User, UserRole
from app.services.payment_gateway import FakePaymentGateway, get_payment_gateway

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PASSWORD = "Passw0rd!"


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema() -> Iterator[None]:
    """Reset the test database and apply all Alembic migrations once per session."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["configure_logger"] = False
    os.environ["ALEMBIC_DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _truncate_tables() -> Iterator[None]:
    """Remove all rows after each test so tests are independent."""
    yield
    tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    """A database session bound to the test database."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def fake_gateway() -> FakePaymentGateway:
    """A fresh fake payment gateway; inspect ``.checkouts`` / ``.refunds`` in tests."""
    return FakePaymentGateway(webhook_secret="")


@pytest.fixture()
def email_outbox(monkeypatch: pytest.MonkeyPatch) -> list[EmailMessage]:
    """Capture outgoing emails instead of sending them over SMTP.

    ``app.services.email`` routes every message through ``async _deliver(msg)``;
    this fixture replaces it with an in-memory recorder.
    """
    outbox: list[EmailMessage] = []
    try:
        email_module = importlib.import_module("app.services.email")
    except ModuleNotFoundError:
        return outbox

    async def _fake_deliver(msg: EmailMessage) -> None:
        outbox.append(msg)

    monkeypatch.setattr(email_module, "_deliver", _fake_deliver)
    return outbox


@pytest.fixture()
def client(
    fake_gateway: FakePaymentGateway, email_outbox: list[EmailMessage]
) -> Generator[TestClient, None, None]:
    """HTTP test client with the fake payment gateway and captured email."""
    app.dependency_overrides[get_payment_gateway] = lambda: fake_gateway
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def make_user(db: Session) -> Callable[..., User]:
    """Factory creating a committed user. Password is ``DEFAULT_PASSWORD``."""
    counter = {"n": 0}

    def _make(
        role: UserRole = UserRole.player,
        *,
        email: str | None = None,
        verified: bool = True,
        active: bool = True,
        full_name: str = "Test User",
        password: str = DEFAULT_PASSWORD,
    ) -> User:
        counter["n"] += 1
        user = User(
            email=(email or f"{role.value}{counter['n']}@example.com").lower(),
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role,
            is_verified=verified,
            is_active=active,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make


@pytest.fixture()
def auth_headers() -> Callable[[User], dict[str, str]]:
    """Return a factory producing ``Authorization`` headers for a user."""

    def _headers(user: User) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}

    return _headers


@pytest.fixture()
def make_turf(db: Session) -> Callable[..., Turf]:
    """Factory creating a committed active turf (Asia/Kolkata, 06:00-23:00, 60-min slots)."""
    counter = {"n": 0}

    def _make(owner: User, **overrides: Any) -> Turf:
        counter["n"] += 1
        values: dict[str, Any] = {
            "owner_id": owner.id,
            "name": f"Test Turf {counter['n']}",
            "slug": f"test-turf-{counter['n']}",
            "description": "A test turf",
            "address": "1 Test Street",
            "city": "bengaluru",
            "city_display": "Bengaluru",
            "timezone": "Asia/Kolkata",
            "sport_types": [SportType.football],
            "amenities": ["Parking"],
            "image_urls": [],
            "slot_duration_minutes": 60,
            "opening_time": time(6, 0),
            "closing_time": time(23, 0),
            "base_price": 100000,
            "currency": "INR",
            "is_active": True,
        }
        values.update(overrides)
        turf = Turf(**values)
        db.add(turf)
        db.commit()
        db.refresh(turf)
        return turf

    return _make
