"""Tests for Google Sign-In (``POST /auth/google``) and ``GET /auth/config``."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User, UserRole
from app.services import auth_service

CLIENT_ID = "test-client.apps.googleusercontent.com"

ClaimsSetter = Callable[[dict[str, Any]], None]


def _claims(email: str, **overrides: Any) -> dict[str, Any]:
    claims: dict[str, Any] = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "email": email,
        "email_verified": True,
        "name": "Gina Google",
    }
    claims.update(overrides)
    return claims


@pytest.fixture()
def google_enabled(monkeypatch: pytest.MonkeyPatch) -> ClaimsSetter:
    """Enable Google sign-in and return a setter for the claims the verifier returns."""
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT_ID)
    state: dict[str, dict[str, Any]] = {"claims": {}}

    def _verify(credential: str, request: object, audience: str) -> dict[str, Any]:
        assert audience == CLIENT_ID
        if credential == "bad":
            raise ValueError("Wrong signature")
        return state["claims"]

    monkeypatch.setattr(auth_service.google_id_token, "verify_oauth2_token", _verify)

    def _set(claims: dict[str, Any]) -> None:
        state["claims"] = claims

    return _set


def test_config_reports_client_id(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    assert client.get("/api/v1/auth/config").json() == {"google_client_id": None}
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", CLIENT_ID)
    assert client.get("/api/v1/auth/config").json() == {"google_client_id": CLIENT_ID}


def test_disabled_without_client_id(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    r = client.post("/api/v1/auth/google", json={"credential": "x"})
    assert r.status_code == 503
    assert r.json()["code"] == "GOOGLE_AUTH_DISABLED"


def test_new_user_created_verified(
    client: TestClient, db: Session, google_enabled: ClaimsSetter
) -> None:
    google_enabled(_claims("New.Owner@Example.com"))
    r = client.post("/api/v1/auth/google", json={"credential": "tok", "role": "owner"})
    assert r.status_code == 200, r.text
    tokens = r.json()
    assert tokens["access_token"] and tokens["refresh_token"]
    user = db.scalar(select(User).where(User.email == "new.owner@example.com"))
    assert user is not None
    assert user.is_verified and user.role == UserRole.owner and user.full_name == "Gina Google"
    me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.json()["email"] == "new.owner@example.com"


def test_name_falls_back_to_email_prefix(
    client: TestClient, db: Session, google_enabled: ClaimsSetter
) -> None:
    google_enabled(_claims("noname@example.com", name=None))
    assert client.post("/api/v1/auth/google", json={"credential": "tok"}).status_code == 200
    user = db.scalar(select(User).where(User.email == "noname@example.com"))
    assert user is not None and user.full_name == "noname" and user.role == UserRole.player


def test_admin_role_rejected(client: TestClient, google_enabled: ClaimsSetter) -> None:
    google_enabled(_claims("x@example.com"))
    r = client.post("/api/v1/auth/google", json={"credential": "tok", "role": "admin"})
    assert r.status_code == 422


def test_existing_user_logs_in_and_is_verified(
    client: TestClient,
    db: Session,
    make_user: Callable[..., User],
    google_enabled: ClaimsSetter,
) -> None:
    user = make_user(UserRole.player, email="old@example.com", verified=False)
    google_enabled(_claims("OLD@example.com"))
    r = client.post("/api/v1/auth/google", json={"credential": "tok", "role": "owner"})
    assert r.status_code == 200, r.text
    db.refresh(user)
    assert user.is_verified and user.role == UserRole.player


def test_unverified_email_rejected(client: TestClient, google_enabled: ClaimsSetter) -> None:
    google_enabled(_claims("u@example.com", email_verified=False))
    r = client.post("/api/v1/auth/google", json={"credential": "tok"})
    assert r.status_code == 401
    assert r.json()["code"] == "INVALID_GOOGLE_TOKEN"


def test_bad_issuer_and_invalid_token_rejected(
    client: TestClient, google_enabled: ClaimsSetter
) -> None:
    google_enabled(_claims("u@example.com", iss="evil.example.com"))
    assert client.post("/api/v1/auth/google", json={"credential": "tok"}).status_code == 401
    r = client.post("/api/v1/auth/google", json={"credential": "bad"})
    assert r.status_code == 401
    assert r.json()["code"] == "INVALID_GOOGLE_TOKEN"


def test_inactive_user_forbidden(
    client: TestClient,
    make_user: Callable[..., User],
    google_enabled: ClaimsSetter,
) -> None:
    make_user(UserRole.player, email="gone@example.com", active=False)
    google_enabled(_claims("gone@example.com"))
    r = client.post("/api/v1/auth/google", json={"credential": "tok"})
    assert r.status_code == 403
    assert r.json()["code"] == "ACCOUNT_INACTIVE"
