"""Tests for the authentication module (``/api/v1/auth``)."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth.security import hash_token, verify_password
from app.models import (
    EmailVerificationToken,
    PasswordResetToken,
    RefreshToken,
    User,
    UserRole,
)
from app.scripts.create_admin import create_or_promote_admin
from app.scripts.create_admin import main as create_admin_main
from tests.conftest import DEFAULT_PASSWORD

API = "/api/v1/auth"
NEW_PASSWORD = "NewPassw0rd"

UserFactory = Callable[..., User]
HeadersFactory = Callable[[User], dict[str, str]]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _text_body(msg: EmailMessage) -> str:
    part = msg.get_body(preferencelist=("plain",))
    assert part is not None
    return str(part.get_content())  # type: ignore[attr-defined]


def _token_from(msg: EmailMessage, path: str) -> str:
    match = re.search(rf"http://localhost:5173{path}\?token=([A-Za-z0-9_\-]+)", _text_body(msg))
    assert match, "action link not found in email"
    return match.group(1)


def _register(client: TestClient, **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "email": "New.User@Example.COM",
        "password": "Passw0rd1",
        "full_name": "  New User  ",
        "role": "player",
    }
    body.update(overrides)
    resp = client.post(f"{API}/register", json=body)
    return {"status": resp.status_code, "json": resp.json()}


def _login(client: TestClient, email: str, password: str = DEFAULT_PASSWORD) -> dict[str, str]:
    resp = client.post(f"{API}/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    data: dict[str, str] = resp.json()
    return data


def _active_refresh_count(db: Session, user_id: int) -> int:
    db.expire_all()
    return int(
        db.scalar(
            select(func.count())
            .select_from(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        )
        or 0
    )


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


def test_register_creates_user_and_sends_verification(
    client: TestClient, db: Session, email_outbox: list[EmailMessage]
) -> None:
    result = _register(client, phone=" +91 98765 43210 ")
    assert result["status"] == 201
    data = result["json"]
    assert isinstance(data, dict)
    assert data["email"] == "new.user@example.com"
    assert data["full_name"] == "New User"
    assert data["phone"] == "+91 98765 43210"
    assert data["role"] == "player"
    assert data["is_active"] is True
    assert data["is_verified"] is False
    assert data["created_at"].endswith("Z")
    assert set(data) == {
        "id",
        "email",
        "full_name",
        "phone",
        "role",
        "is_active",
        "is_verified",
        "created_at",
    }

    user = db.scalar(select(User).where(User.email == "new.user@example.com"))
    assert user is not None
    assert user.hashed_password != "Passw0rd1"
    assert verify_password("Passw0rd1", user.hashed_password)

    assert len(email_outbox) == 1
    msg = email_outbox[0]
    assert msg["To"] == "new.user@example.com"
    assert "Verify" in msg["Subject"]
    token = _token_from(msg, "/verify-email")
    stored = db.scalar(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    )
    assert stored is not None
    assert stored.token_hash == hash_token(token)
    assert stored.token_hash != token
    assert "24 hours" in _text_body(msg)


def test_register_owner(client: TestClient) -> None:
    result = _register(client, role="owner")
    assert result["status"] == 201
    assert result["json"]["role"] == "owner"  # type: ignore[index]


def test_register_defaults_to_player(client: TestClient) -> None:
    resp = client.post(
        f"{API}/register",
        json={"email": "d@example.com", "password": "Passw0rd1", "full_name": "D"},
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "player"
    assert resp.json()["phone"] is None


def test_register_admin_role_rejected(client: TestClient, db: Session) -> None:
    result = _register(client, role="admin")
    assert result["status"] == 422
    assert db.scalar(select(func.count()).select_from(User)) == 0


def test_register_duplicate_email_case_insensitive(
    client: TestClient, make_user: UserFactory
) -> None:
    make_user(email="taken@example.com")
    result = _register(client, email="TAKEN@example.com")
    assert result["status"] == 409
    assert result["json"]["code"] == "EMAIL_TAKEN"  # type: ignore[index]


@pytest.mark.parametrize(
    "password",
    ["short1", "allletters", "12345678", "", "a" * 200 + "1"],
)
def test_register_password_policy(client: TestClient, password: str) -> None:
    result = _register(client, password=password)
    assert result["status"] == 422
    assert result["json"]["code"] == "VALIDATION_ERROR"  # type: ignore[index]


@pytest.mark.parametrize(
    "override",
    [{"email": "not-an-email"}, {"full_name": "   "}, {"full_name": ""}, {"role": "superuser"}],
)
def test_register_invalid_fields(client: TestClient, override: dict[str, object]) -> None:
    assert _register(client, **override)["status"] == 422


# ---------------------------------------------------------------------------
# login
# ---------------------------------------------------------------------------


def test_login_returns_token_pair(client: TestClient, db: Session, make_user: UserFactory) -> None:
    user = make_user(email="login@example.com")
    data = _login(client, "LOGIN@Example.com")
    assert set(data) == {"access_token", "refresh_token", "token_type"}
    assert data["token_type"] == "bearer"
    me = client.get(f"{API}/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert me.status_code == 200
    assert me.json()["id"] == user.id
    stored = db.scalar(select(RefreshToken).where(RefreshToken.user_id == user.id))
    assert stored is not None
    assert stored.token_hash == hash_token(data["refresh_token"])
    assert stored.expires_at > datetime.now(UTC) + timedelta(days=6)


def test_login_unverified_user_allowed(client: TestClient, make_user: UserFactory) -> None:
    make_user(email="unverified@example.com", verified=False)
    _login(client, "unverified@example.com")


def test_login_wrong_password(client: TestClient, make_user: UserFactory) -> None:
    make_user(email="x@example.com")
    resp = client.post(f"{API}/login", json={"email": "x@example.com", "password": "wrong1234"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "INVALID_CREDENTIALS"


def test_login_unknown_email(client: TestClient) -> None:
    resp = client.post(
        f"{API}/login", json={"email": "nobody@example.com", "password": DEFAULT_PASSWORD}
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "INVALID_CREDENTIALS"


def test_login_inactive_user(client: TestClient, make_user: UserFactory) -> None:
    make_user(email="inactive@example.com", active=False)
    resp = client.post(
        f"{API}/login", json={"email": "inactive@example.com", "password": DEFAULT_PASSWORD}
    )
    assert resp.status_code == 403
    assert resp.json()["code"] == "ACCOUNT_INACTIVE"


def test_login_inactive_user_wrong_password_is_401(
    client: TestClient, make_user: UserFactory
) -> None:
    make_user(email="inactive@example.com", active=False)
    resp = client.post(
        f"{API}/login", json={"email": "inactive@example.com", "password": "wrong1234"}
    )
    assert resp.status_code == 401


def test_login_rejects_form_body(client: TestClient, make_user: UserFactory) -> None:
    make_user(email="form@example.com")
    resp = client.post(
        f"{API}/login", data={"username": "form@example.com", "password": DEFAULT_PASSWORD}
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# refresh / logout
# ---------------------------------------------------------------------------


def test_refresh_rotates_token(client: TestClient, db: Session, make_user: UserFactory) -> None:
    user = make_user(email="r@example.com")
    first = _login(client, "r@example.com")
    resp = client.post(f"{API}/refresh", json={"refresh_token": first["refresh_token"]})
    assert resp.status_code == 200
    second = resp.json()
    assert second["token_type"] == "bearer"
    assert second["refresh_token"] != first["refresh_token"]

    db.expire_all()
    old = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(first["refresh_token"]))
    )
    assert old is not None and old.revoked is True
    assert _active_refresh_count(db, user.id) == 1

    # The new refresh token works.
    third = client.post(f"{API}/refresh", json={"refresh_token": second["refresh_token"]})
    assert third.status_code == 200


def test_refresh_reuse_revokes_all_tokens(
    client: TestClient, db: Session, make_user: UserFactory
) -> None:
    user = make_user(email="reuse@example.com")
    other_session = _login(client, "reuse@example.com")
    first = _login(client, "reuse@example.com")
    rotated = client.post(f"{API}/refresh", json={"refresh_token": first["refresh_token"]}).json()
    assert _active_refresh_count(db, user.id) == 2

    # Replaying the already-rotated token is detected as reuse.
    replay = client.post(f"{API}/refresh", json={"refresh_token": first["refresh_token"]})
    assert replay.status_code == 401
    assert replay.json()["code"] == "REFRESH_TOKEN_REUSED"
    assert _active_refresh_count(db, user.id) == 0

    for token in (rotated["refresh_token"], other_session["refresh_token"]):
        resp = client.post(f"{API}/refresh", json={"refresh_token": token})
        assert resp.status_code == 401


def test_refresh_unknown_token(client: TestClient) -> None:
    resp = client.post(f"{API}/refresh", json={"refresh_token": "garbage"})
    assert resp.status_code == 401
    assert resp.json()["code"] == "INVALID_REFRESH_TOKEN"


def test_refresh_expired_token(client: TestClient, db: Session, make_user: UserFactory) -> None:
    make_user(email="exp@example.com")
    pair = _login(client, "exp@example.com")
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(pair["refresh_token"]))
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    db.commit()
    resp = client.post(f"{API}/refresh", json={"refresh_token": pair["refresh_token"]})
    assert resp.status_code == 401
    assert resp.json()["code"] == "INVALID_REFRESH_TOKEN"


def test_refresh_inactive_user(client: TestClient, db: Session, make_user: UserFactory) -> None:
    user = make_user(email="deact@example.com")
    pair = _login(client, "deact@example.com")
    db.execute(update(User).where(User.id == user.id).values(is_active=False))
    db.commit()
    resp = client.post(f"{API}/refresh", json={"refresh_token": pair["refresh_token"]})
    assert resp.status_code == 403
    assert resp.json()["code"] == "ACCOUNT_INACTIVE"


def test_refresh_missing_body(client: TestClient) -> None:
    assert client.post(f"{API}/refresh", json={}).status_code == 422


def test_logout_revokes_refresh_token(
    client: TestClient, db: Session, make_user: UserFactory
) -> None:
    user = make_user(email="out@example.com")
    pair = _login(client, "out@example.com")
    headers = {"Authorization": f"Bearer {pair['access_token']}"}
    resp = client.post(
        f"{API}/logout", json={"refresh_token": pair["refresh_token"]}, headers=headers
    )
    assert resp.status_code == 204
    assert resp.content == b""
    assert _active_refresh_count(db, user.id) == 0
    again = client.post(f"{API}/refresh", json={"refresh_token": pair["refresh_token"]})
    assert again.status_code == 401


def test_logout_requires_auth(client: TestClient) -> None:
    resp = client.post(f"{API}/logout", json={"refresh_token": "x"})
    assert resp.status_code == 401


def test_logout_cannot_revoke_other_users_token(
    client: TestClient,
    db: Session,
    make_user: UserFactory,
    auth_headers: HeadersFactory,
) -> None:
    victim = make_user(email="victim@example.com")
    attacker = make_user(email="attacker@example.com")
    pair = _login(client, "victim@example.com")
    resp = client.post(
        f"{API}/logout",
        json={"refresh_token": pair["refresh_token"]},
        headers=auth_headers(attacker),
    )
    assert resp.status_code == 204
    assert _active_refresh_count(db, victim.id) == 1


# ---------------------------------------------------------------------------
# me
# ---------------------------------------------------------------------------


def test_me_requires_auth(client: TestClient) -> None:
    resp = client.get(f"{API}/me")
    assert resp.status_code == 401
    assert resp.json()["code"] == "NOT_AUTHENTICATED"


def test_me_invalid_token(client: TestClient) -> None:
    resp = client.get(f"{API}/me", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401


def test_me_inactive_user_forbidden(
    client: TestClient, make_user: UserFactory, auth_headers: HeadersFactory
) -> None:
    user = make_user(active=False)
    resp = client.get(f"{API}/me", headers=auth_headers(user))
    assert resp.status_code == 403
    assert resp.json()["code"] == "ACCOUNT_INACTIVE"


def test_update_me(
    client: TestClient, make_user: UserFactory, auth_headers: HeadersFactory
) -> None:
    user = make_user(full_name="Old Name")
    headers = auth_headers(user)
    resp = client.put(
        f"{API}/me", json={"full_name": " New Name ", "phone": "12345"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "New Name"
    assert resp.json()["phone"] == "12345"

    # Partial update keeps other fields; explicit null clears phone.
    resp = client.put(f"{API}/me", json={"phone": None}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "New Name"
    assert resp.json()["phone"] is None

    resp = client.put(f"{API}/me", json={}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "New Name"


def test_update_me_ignores_privileged_fields(
    client: TestClient, make_user: UserFactory, auth_headers: HeadersFactory
) -> None:
    user = make_user()
    resp = client.put(
        f"{API}/me",
        json={"role": "admin", "is_verified": True, "email": "h@x.com"},
        headers=auth_headers(user),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "player"
    assert resp.json()["email"] == user.email


@pytest.mark.parametrize(
    "body", [{"full_name": "  "}, {"phone": "1" * 21}, {"full_name": "x" * 101}]
)
def test_update_me_validation(
    client: TestClient, make_user: UserFactory, auth_headers: HeadersFactory, body: dict[str, str]
) -> None:
    user = make_user()
    assert client.put(f"{API}/me", json=body, headers=auth_headers(user)).status_code == 422


# ---------------------------------------------------------------------------
# change password
# ---------------------------------------------------------------------------


def test_change_password_keeps_current_session(
    client: TestClient, db: Session, make_user: UserFactory
) -> None:
    user = make_user(email="cp@example.com")
    other = _login(client, "cp@example.com")
    current = _login(client, "cp@example.com")
    headers = {"Authorization": f"Bearer {current['access_token']}"}
    resp = client.post(
        f"{API}/change-password",
        json={
            "current_password": DEFAULT_PASSWORD,
            "new_password": NEW_PASSWORD,
            "refresh_token": current["refresh_token"],
        },
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"message": "Password changed"}
    assert _active_refresh_count(db, user.id) == 1
    assert (
        client.post(f"{API}/refresh", json={"refresh_token": current["refresh_token"]}).status_code
        == 200
    )
    assert (
        client.post(f"{API}/refresh", json={"refresh_token": other["refresh_token"]}).status_code
        == 401
    )

    # Old password no longer works; new one does.
    bad = client.post(
        f"{API}/login", json={"email": "cp@example.com", "password": DEFAULT_PASSWORD}
    )
    assert bad.status_code == 401
    _login(client, "cp@example.com", NEW_PASSWORD)


def test_change_password_without_refresh_token_revokes_all(
    client: TestClient, db: Session, make_user: UserFactory, auth_headers: HeadersFactory
) -> None:
    user = make_user(email="cp2@example.com")
    _login(client, "cp2@example.com")
    resp = client.post(
        f"{API}/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": NEW_PASSWORD},
        headers=auth_headers(user),
    )
    assert resp.status_code == 200
    assert _active_refresh_count(db, user.id) == 0


def test_change_password_wrong_current(
    client: TestClient, make_user: UserFactory, auth_headers: HeadersFactory
) -> None:
    user = make_user()
    resp = client.post(
        f"{API}/change-password",
        json={"current_password": "Wrong1234", "new_password": NEW_PASSWORD},
        headers=auth_headers(user),
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_CURRENT_PASSWORD"


def test_change_password_policy_and_auth(
    client: TestClient, make_user: UserFactory, auth_headers: HeadersFactory
) -> None:
    user = make_user()
    weak = client.post(
        f"{API}/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "weak"},
        headers=auth_headers(user),
    )
    assert weak.status_code == 422
    anon = client.post(
        f"{API}/change-password",
        json={"current_password": DEFAULT_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert anon.status_code == 401


# ---------------------------------------------------------------------------
# forgot / reset password
# ---------------------------------------------------------------------------


def test_forgot_password_unknown_email_is_200_without_email(
    client: TestClient, email_outbox: list[EmailMessage]
) -> None:
    resp = client.post(f"{API}/forgot-password", json={"email": "ghost@example.com"})
    assert resp.status_code == 200
    assert "message" in resp.json()
    assert email_outbox == []


def test_forgot_password_inactive_user_no_email(
    client: TestClient, make_user: UserFactory, email_outbox: list[EmailMessage]
) -> None:
    make_user(email="gone@example.com", active=False)
    resp = client.post(f"{API}/forgot-password", json={"email": "gone@example.com"})
    assert resp.status_code == 200
    assert email_outbox == []


def test_forgot_and_reset_password_flow(
    client: TestClient,
    db: Session,
    make_user: UserFactory,
    email_outbox: list[EmailMessage],
) -> None:
    user = make_user(email="reset@example.com", full_name="Rita")
    _login(client, "reset@example.com")
    known = client.post(f"{API}/forgot-password", json={"email": "RESET@example.com"})
    unknown = client.post(f"{API}/forgot-password", json={"email": "other@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()

    assert len(email_outbox) == 1
    msg = email_outbox[0]
    assert msg["To"] == "reset@example.com"
    assert "Reset" in msg["Subject"]
    body = _text_body(msg)
    assert "Hi Rita" in body
    assert "1 hour" in body
    token = _token_from(msg, "/reset-password")

    resp = client.post(f"{API}/reset-password", json={"token": token, "new_password": NEW_PASSWORD})
    assert resp.status_code == 200
    _login(client, "reset@example.com", NEW_PASSWORD)
    # All sessions from before the reset were revoked (only the new login is active).
    assert _active_refresh_count(db, user.id) == 1

    # Single use.
    again = client.post(f"{API}/reset-password", json={"token": token, "new_password": "Another1x"})
    assert again.status_code == 400
    assert again.json()["code"] == "INVALID_OR_EXPIRED_TOKEN"


def test_reset_password_invalidates_older_links(
    client: TestClient, make_user: UserFactory, email_outbox: list[EmailMessage]
) -> None:
    make_user(email="two@example.com")
    client.post(f"{API}/forgot-password", json={"email": "two@example.com"})
    client.post(f"{API}/forgot-password", json={"email": "two@example.com"})
    first, second = (_token_from(m, "/reset-password") for m in email_outbox)
    assert first != second
    assert (
        client.post(
            f"{API}/reset-password", json={"token": second, "new_password": NEW_PASSWORD}
        ).status_code
        == 200
    )
    stale = client.post(
        f"{API}/reset-password", json={"token": first, "new_password": NEW_PASSWORD}
    )
    assert stale.status_code == 400


def test_reset_password_expired_token(
    client: TestClient, db: Session, make_user: UserFactory, email_outbox: list[EmailMessage]
) -> None:
    make_user(email="late@example.com")
    client.post(f"{API}/forgot-password", json={"email": "late@example.com"})
    token = _token_from(email_outbox[0], "/reset-password")
    db.execute(
        update(PasswordResetToken).values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    db.commit()
    resp = client.post(f"{API}/reset-password", json={"token": token, "new_password": NEW_PASSWORD})
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_OR_EXPIRED_TOKEN"


def test_reset_password_invalid_token_and_policy(client: TestClient) -> None:
    bad = client.post(f"{API}/reset-password", json={"token": "nope", "new_password": NEW_PASSWORD})
    assert bad.status_code == 400
    weak = client.post(f"{API}/reset-password", json={"token": "nope", "new_password": "weakpass"})
    assert weak.status_code == 422


# ---------------------------------------------------------------------------
# verify email / resend
# ---------------------------------------------------------------------------


def test_verify_email_flow(
    client: TestClient, db: Session, email_outbox: list[EmailMessage]
) -> None:
    _register(client, email="verify@example.com")
    token = _token_from(email_outbox[0], "/verify-email")
    resp = client.post(f"{API}/verify-email", json={"token": token})
    assert resp.status_code == 200
    assert resp.json() == {"message": "Email verified"}
    db.expire_all()
    user = db.scalar(select(User).where(User.email == "verify@example.com"))
    assert user is not None and user.is_verified is True

    again = client.post(f"{API}/verify-email", json={"token": token})
    assert again.status_code == 400
    assert again.json()["code"] == "INVALID_OR_EXPIRED_TOKEN"


def test_verify_email_expired(
    client: TestClient, db: Session, email_outbox: list[EmailMessage]
) -> None:
    _register(client, email="vexp@example.com")
    token = _token_from(email_outbox[0], "/verify-email")
    db.execute(
        update(EmailVerificationToken).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    db.commit()
    resp = client.post(f"{API}/verify-email", json={"token": token})
    assert resp.status_code == 400
    db.expire_all()
    user = db.scalar(select(User).where(User.email == "vexp@example.com"))
    assert user is not None and user.is_verified is False


def test_verify_email_unknown_token(client: TestClient) -> None:
    resp = client.post(f"{API}/verify-email", json={"token": "unknown"})
    assert resp.status_code == 400
    assert client.post(f"{API}/verify-email", json={}).status_code == 422


def test_resend_verification(
    client: TestClient,
    make_user: UserFactory,
    auth_headers: HeadersFactory,
    email_outbox: list[EmailMessage],
) -> None:
    user = make_user(email="resend@example.com", verified=False)
    resp = client.post(f"{API}/resend-verification", headers=auth_headers(user))
    assert resp.status_code == 200
    assert len(email_outbox) == 1
    assert email_outbox[0]["To"] == "resend@example.com"
    token = _token_from(email_outbox[0], "/verify-email")
    assert client.post(f"{API}/verify-email", json={"token": token}).status_code == 200


def test_resend_verification_already_verified(
    client: TestClient,
    make_user: UserFactory,
    auth_headers: HeadersFactory,
    email_outbox: list[EmailMessage],
) -> None:
    user = make_user(verified=True)
    resp = client.post(f"{API}/resend-verification", headers=auth_headers(user))
    assert resp.status_code == 400
    assert resp.json()["code"] == "ALREADY_VERIFIED"
    assert email_outbox == []


def test_resend_verification_requires_auth(client: TestClient) -> None:
    assert client.post(f"{API}/resend-verification").status_code == 401


# ---------------------------------------------------------------------------
# create_admin script
# ---------------------------------------------------------------------------


def test_create_admin_creates_and_promotes(db: Session, make_user: UserFactory) -> None:
    admin = create_or_promote_admin(db, "Boss@Example.com", "Adm1nPass", "Boss")
    assert admin.email == "boss@example.com"
    assert admin.role == UserRole.admin
    assert admin.is_verified and admin.is_active

    player = make_user(email="promote@example.com", verified=False, active=False)
    promoted = create_or_promote_admin(db, "promote@example.com", "Adm1nPass2", "Promoted")
    assert promoted.id == player.id
    assert promoted.role == UserRole.admin
    assert promoted.is_verified and promoted.is_active
    assert promoted.full_name == "Promoted"
    assert verify_password("Adm1nPass2", promoted.hashed_password)


def test_create_admin_cli(db: Session) -> None:
    code = create_admin_main(
        ["--email", "cli@example.com", "--password", "Cl1Password", "--full-name", "CLI"]
    )
    assert code == 0
    user = db.scalar(select(User).where(User.email == "cli@example.com"))
    assert user is not None and user.role == UserRole.admin

    assert create_admin_main(["--email", "weak@example.com", "--password", "weak"]) == 2
    assert db.scalar(select(User).where(User.email == "weak@example.com")) is None
