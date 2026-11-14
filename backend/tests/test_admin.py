"""Basic tests for the admin module."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models import Turf, User, UserRole

API = "/api/v1/admin"


def test_admin_endpoints(
    client: TestClient,
    make_user: Callable[..., User],
    make_turf: Callable[..., Turf],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    admin = make_user(UserRole.admin)
    owner = make_user(UserRole.owner, email="owner@example.com")
    turf = make_turf(owner)
    h = auth_headers(admin)

    users = client.get(f"{API}/users", params={"q": "owner@"}, headers=h).json()
    assert users["total"] == 1 and users["items"][0]["id"] == owner.id

    resp = client.put(f"{API}/users/{owner.id}", json={"is_active": False}, headers=h)
    assert resp.status_code == 200 and resp.json()["is_active"] is False
    assert (
        client.put(f"{API}/users/{admin.id}", json={"role": "player"}, headers=h).status_code == 400
    )

    turfs = client.get(f"{API}/turfs", params={"city": "Bengaluru"}, headers=h).json()
    assert turfs["items"][0]["owner_email"] == "owner@example.com"
    resp = client.put(f"{API}/turfs/{turf.id}", json={"is_active": False}, headers=h)
    assert resp.json()["is_active"] is False

    stats = client.get(f"{API}/stats", headers=h).json()
    assert stats["users_by_role"] == {"player": 0, "owner": 1, "admin": 1}
    assert stats["turfs_active"] == 0 and stats["gmv"] == 0

    assert client.get(f"{API}/stats", headers=auth_headers(owner)).status_code in (403,)
