"""Happy-path API tests for turfs, pricing rules, slots and blocked slots."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.models import User, UserRole

TURF = {
    "name": "Green Arena",
    "address": "1 Main Rd",
    "city": " Bengaluru ",
    "timezone": "Asia/Kolkata",
    "sport_types": ["football"],
    "image_urls": ["https://example.com/a.jpg"],
    "slot_duration_minutes": 60,
    "opening_time": "06:00",
    "closing_time": "23:00",
    "base_price": 100000,
    "currency": "INR",
}


def test_turf_flow(
    client: TestClient,
    make_user: Callable[..., User],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    owner = make_user(UserRole.owner)
    h = auth_headers(owner)

    r = client.post("/api/v1/turfs", json=TURF, headers=h)
    assert r.status_code == 201, r.text
    turf = r.json()
    assert turf["slug"] == "green-arena" and turf["city"] == "Bengaluru"
    assert turf["opening_time"] == "06:00"
    assert client.post("/api/v1/turfs", json=TURF, headers=h).json()["slug"] == "green-arena-2"

    r = client.get("/api/v1/turfs", params={"city": "BENGALURU", "sport": "football", "q": "green"})
    assert r.status_code == 200 and r.json()["total"] == 2
    tomorrow = (datetime.now(UTC) + timedelta(days=1)).date().isoformat()
    assert client.get("/api/v1/turfs", params={"date": tomorrow}).json()["total"] == 2

    r = client.put(f"/api/v1/turfs/{turf['id']}", json={"base_price": 5}, headers=h)
    assert r.status_code == 200 and r.json()["base_price"] == 5

    rule = {"day_of_week": None, "start_time": "18:00", "end_time": "21:00", "price": 9}
    r = client.post(f"/api/v1/turfs/{turf['id']}/pricing-rules", json=rule, headers=h)
    assert r.status_code == 201
    r = client.post(f"/api/v1/turfs/{turf['id']}/pricing-rules", json=rule, headers=h)
    assert r.status_code == 409 and r.json()["code"] == "OVERLAPPING_RULE"

    detail = client.get("/api/v1/turfs/green-arena").json()
    assert detail["id"] == turf["id"] and len(detail["pricing_rules"]) == 1

    r = client.get(f"/api/v1/turfs/{turf['id']}/slots", params={"date": tomorrow})
    assert r.status_code == 200
    slots = r.json()["slots"]
    assert len(slots) == 17 and slots[0]["start_at"].endswith("Z")
    far = (datetime.now(UTC) + timedelta(days=60)).date().isoformat()
    r = client.get(f"/api/v1/turfs/{turf['id']}/slots", params={"date": far})
    assert r.status_code == 400 and r.json()["code"] == "OUTSIDE_BOOKING_WINDOW"

    block = [{"start_at": slots[2]["start_at"], "end_at": slots[3]["end_at"]}]
    r = client.post(f"/api/v1/turfs/{turf['id']}/blocked-slots", json=block, headers=h)
    assert r.status_code == 201, r.text
    r = client.post(f"/api/v1/turfs/{turf['id']}/blocked-slots", json=block, headers=h)
    assert r.status_code == 409 and r.json()["code"] == "OVERLAPPING_BLOCK"

    assert len(client.get("/api/v1/owner/turfs", headers=h).json()) == 2
    assert client.delete(f"/api/v1/turfs/{turf['id']}", headers=h).status_code == 204
    assert client.get(f"/api/v1/turfs/{turf['id']}").status_code == 404


def test_turf_permissions(
    client: TestClient,
    make_user: Callable[..., User],
    make_turf: Callable[..., object],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    owner = make_user(UserRole.owner)
    other = make_user(UserRole.owner)
    turf = make_turf(owner)
    assert client.post("/api/v1/turfs", json=TURF).status_code == 401
    player = auth_headers(make_user(UserRole.player))
    assert client.post("/api/v1/turfs", json=TURF, headers=player).status_code == 403
    unverified = auth_headers(make_user(UserRole.owner, verified=False))
    r = client.post("/api/v1/turfs", json=TURF, headers=unverified)
    assert r.json()["code"] == "EMAIL_NOT_VERIFIED"
    r = client.put(f"/api/v1/turfs/{turf.id}", json={"name": "X Y"}, headers=auth_headers(other))
    assert r.status_code == 403 and r.json()["code"] == "NOT_OWNER"
    bad = {**TURF, "timezone": "Mars/Base"}
    assert client.post("/api/v1/turfs", json=bad, headers=auth_headers(owner)).status_code == 422
