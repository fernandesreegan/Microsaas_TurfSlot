"""Smoke tests for the health endpoint and test fixtures."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models import Turf, User, UserRole


def test_health_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "db": "ok"}


def test_factories(make_user: Callable[..., User], make_turf: Callable[..., Turf]) -> None:
    owner = make_user(UserRole.owner)
    turf = make_turf(owner)
    assert turf.id is not None
    assert turf.owner_id == owner.id
