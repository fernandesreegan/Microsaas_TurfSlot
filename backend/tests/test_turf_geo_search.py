"""Location (lat/lng/radius) search on ``GET /turfs``."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.models import SportType, Turf, User, UserRole

BLR = (12.9716, 77.5946)  # Bengaluru centre
MYS = (12.2958, 76.6394)  # Mysuru, ~127 km from Bengaluru


@pytest.fixture()
def geo_turfs(make_user: Callable[..., User], make_turf: Callable[..., Turf]) -> None:
    owner = make_user(UserRole.owner)
    make_turf(owner, name="Centre Turf", latitude=BLR[0], longitude=BLR[1])
    # 0.05 degrees (~5.56 km) north of the centre
    make_turf(
        owner,
        name="North Turf",
        latitude=13.0216,
        longitude=BLR[1],
        sport_types=[SportType.cricket],
    )
    make_turf(
        owner,
        name="Mysuru Turf",
        city="mysuru",
        city_display="Mysuru",
        latitude=MYS[0],
        longitude=MYS[1],
    )
    make_turf(owner, name="No Coords Turf")


def _items(client: TestClient, **params: Any) -> list[dict[str, Any]]:
    r = client.get("/api/v1/turfs", params=params)
    assert r.status_code == 200, r.text
    items: list[dict[str, Any]] = r.json()["items"]
    return items


@pytest.mark.usefixtures("geo_turfs")
def test_radius_filter_and_order(client: TestClient) -> None:
    r = client.get("/api/v1/turfs", params={"lat": BLR[0], "lng": BLR[1], "radius_km": 10})
    body = r.json()
    assert [i["name"] for i in body["items"]] == ["Centre Turf", "North Turf"]
    assert body["total"] == 2
    assert body["items"][0]["distance_km"] == pytest.approx(0, abs=0.01)
    assert body["items"][1]["distance_km"] == pytest.approx(5.56, abs=0.05)


@pytest.mark.usefixtures("geo_turfs")
def test_far_turfs_excluded(client: TestClient) -> None:
    names = [i["name"] for i in _items(client, lat=BLR[0], lng=BLR[1], radius_km=100)]
    assert "Mysuru Turf" not in names  # ~127 km away
    assert "No Coords Turf" not in names
    assert [i["name"] for i in _items(client, lat=MYS[0], lng=MYS[1], radius_km=5)] == [
        "Mysuru Turf"
    ]


@pytest.mark.usefixtures("geo_turfs")
def test_distances_and_ordering_between_cities(client: TestClient) -> None:
    items = _items(client, lat=12.6, lng=77.1, radius_km=100)
    by_name = {i["name"]: i["distance_km"] for i in items}
    assert set(by_name) == {"Centre Turf", "North Turf", "Mysuru Turf"}
    # Haversine reference values from (12.6, 77.1).
    assert by_name["Mysuru Turf"] == pytest.approx(61.5, abs=1.5)
    assert by_name["Centre Turf"] == pytest.approx(67.4, abs=1.5)
    distances = [i["distance_km"] for i in items]
    assert distances == sorted(distances)
    assert items[0]["name"] == "Mysuru Turf"


@pytest.mark.usefixtures("geo_turfs")
def test_geo_combines_with_sport_and_name(client: TestClient) -> None:
    items = _items(client, lat=BLR[0], lng=BLR[1], radius_km=10, sport="cricket")
    assert [i["name"] for i in items] == ["North Turf"]
    items = _items(client, lat=BLR[0], lng=BLR[1], radius_km=10, q="centre")
    assert [i["name"] for i in items] == ["Centre Turf"]


@pytest.mark.usefixtures("geo_turfs")
def test_non_geo_search_has_null_distance(client: TestClient) -> None:
    items = _items(client)
    assert len(items) == 4
    assert all(i["distance_km"] is None for i in items)


def test_invalid_geo_params(client: TestClient) -> None:
    url = "/api/v1/turfs"
    assert client.get(url, params={"lat": 91, "lng": 0}).status_code == 422
    assert client.get(url, params={"lat": 0, "lng": 0, "radius_km": 0}).status_code == 422
    assert client.get(url, params={"lat": 0, "lng": 0, "radius_km": 101}).status_code == 422
    assert client.get(url, params={"lat": 10}).status_code == 400
