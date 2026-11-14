"""Booking flow tests: create, list, detail, cancel, webhook, scheduler, owner views."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Booking, BookingStatus, Payment, PaymentStatus, Turf, User, UserRole
from app.services.availability import local_day_grid, to_local_date
from app.services.payment_gateway import FakePaymentGateway
from app.services.scheduler import run_maintenance

API = "/api/v1"


def slot_start(turf: Turf, days_ahead: int = 2, index: int = 4) -> datetime:
    """A future grid-aligned slot start on the turf."""
    local = to_local_date(turf, datetime.now(UTC)) + timedelta(days=days_ahead)
    return local_day_grid(turf, local)[index][0]


def book(client: TestClient, headers: dict[str, str], turf: Turf, **kw: object) -> dict:
    body = {
        "turf_id": turf.id,
        "start_at": slot_start(turf).isoformat(),
        "slot_count": 1,
    }
    body.update(kw)
    return client.post(f"{API}/bookings", json=body, headers=headers).json()


def webhook(client: TestClient, event_id: str, event_type: str, data: dict) -> dict:
    payload = {"business_id": "biz", "type": event_type, "timestamp": "2026-01-01T00:00:00Z"}
    payload["data"] = data
    resp = client.post(
        f"{API}/payments/webhooks/dodo",
        content=json.dumps(payload),
        headers={"webhook-id": event_id, "content-type": "application/json"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_create_booking_happy_path(
    client: TestClient,
    make_user: Callable[..., User],
    make_turf: Callable[..., Turf],
    auth_headers: Callable[[User], dict[str, str]],
    fake_gateway: FakePaymentGateway,
    db: Session,
) -> None:
    owner = make_user(UserRole.owner)
    player = make_user()
    turf = make_turf(owner)
    resp = client.post(
        f"{API}/bookings",
        json={"turf_id": turf.id, "start_at": slot_start(turf).isoformat(), "slot_count": 2},
        headers=auth_headers(player),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    booking = data["booking"]
    assert booking["status"] == "pending"
    assert booking["total_amount"] == 200000
    assert booking["turf"]["city"] == "Bengaluru"
    assert booking["start_at"].endswith("Z")
    assert len(booking["booking_ref"]) == 8
    assert "fake_checkout=1" in data["checkout_url"]
    assert fake_gateway.checkouts == [booking["id"]]
    payment = db.query(Payment).one()
    assert payment.checkout_session_id == f"fake_cs_{booking['id']}"

    # Same slot again -> 409
    again = client.post(
        f"{API}/bookings",
        json={"turf_id": turf.id, "start_at": slot_start(turf).isoformat(), "slot_count": 1},
        headers=auth_headers(make_user()),
    )
    assert again.status_code == 409
    assert again.json()["code"] == "SLOT_UNAVAILABLE"


def test_create_booking_validation_errors(
    client: TestClient,
    make_user: Callable[..., User],
    make_turf: Callable[..., Turf],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    owner = make_user(UserRole.owner)
    player = make_user()
    turf = make_turf(owner)
    start = slot_start(turf)

    def post(user: User, **kw: object) -> tuple[int, str | None]:
        body: dict[str, object] = {"turf_id": turf.id, "start_at": start.isoformat()}
        body["slot_count"] = 1
        body.update(kw)
        r = client.post(f"{API}/bookings", json=body, headers=auth_headers(user))
        return r.status_code, r.json().get("code")

    assert post(owner) == (400, "OWN_TURF")
    assert post(make_user(verified=False)) == (403, "EMAIL_NOT_VERIFIED")
    assert post(player, slot_count=99) == (400, "INVALID_SLOT_COUNT")
    misaligned = (start + timedelta(minutes=15)).isoformat()
    assert post(player, start_at=misaligned) == (400, "SLOT_NOT_ALIGNED")
    far = slot_start(turf, days_ahead=60).isoformat()
    assert post(player, start_at=far) == (400, "OUTSIDE_BOOKING_WINDOW")
    past = slot_start(turf, days_ahead=-2).isoformat()
    assert post(player, start_at=past) == (400, "SLOT_IN_PAST")
    last = local_day_grid(turf, to_local_date(turf, start))[-1][0].isoformat()
    assert post(player, start_at=last, slot_count=2) == (400, "OUTSIDE_OPENING_HOURS")


def test_list_detail_and_visibility(
    client: TestClient,
    make_user: Callable[..., User],
    make_turf: Callable[..., Turf],
    auth_headers: Callable[[User], dict[str, str]],
) -> None:
    owner = make_user(UserRole.owner)
    player = make_user()
    turf = make_turf(owner)
    booking_id = book(client, auth_headers(player), turf)["booking"]["id"]

    mine = client.get(f"{API}/bookings/me?scope=upcoming", headers=auth_headers(player)).json()
    assert mine["total"] == 1 and mine["items"][0]["id"] == booking_id
    past = client.get(f"{API}/bookings/me?scope=past", headers=auth_headers(player)).json()
    assert past["total"] == 0

    assert (
        client.get(f"{API}/bookings/{booking_id}", headers=auth_headers(owner)).status_code == 200
    )
    stranger = client.get(f"{API}/bookings/{booking_id}", headers=auth_headers(make_user()))
    assert stranger.status_code == 404

    owner_list = client.get(f"{API}/owner/bookings", headers=auth_headers(owner)).json()
    assert owner_list["total"] == 1
    assert client.get(f"{API}/owner/bookings", headers=auth_headers(player)).status_code == 403


def test_cancel_pending_booking(
    client: TestClient,
    make_user: Callable[..., User],
    make_turf: Callable[..., Turf],
    auth_headers: Callable[[User], dict[str, str]],
    fake_gateway: FakePaymentGateway,
) -> None:
    owner = make_user(UserRole.owner)
    player = make_user()
    turf = make_turf(owner)
    booking_id = book(client, auth_headers(player), turf)["booking"]["id"]
    resp = client.post(
        f"{API}/bookings/{booking_id}/cancel",
        json={"reason": "plans changed"},
        headers=auth_headers(player),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["cancelled_by"] == "player"
    assert body["refund_status"] == "none"
    assert fake_gateway.refunds == []
    # Cancelling twice is an invalid transition.
    again = client.post(f"{API}/bookings/{booking_id}/cancel", headers=auth_headers(player))
    assert again.json()["code"] == "INVALID_TRANSITION"


def test_webhook_confirms_idempotently_and_owner_cancel_refunds(
    client: TestClient,
    make_user: Callable[..., User],
    make_turf: Callable[..., Turf],
    auth_headers: Callable[[User], dict[str, str]],
    fake_gateway: FakePaymentGateway,
    db: Session,
) -> None:
    owner = make_user(UserRole.owner)
    player = make_user()
    turf = make_turf(owner)
    booking_id = book(client, auth_headers(player), turf)["booking"]["id"]
    data = {
        "payment_id": "pay_123",
        "checkout_session_id": f"fake_cs_{booking_id}",
        "metadata": {"booking_id": str(booking_id)},
        "total_amount": 100000,
    }
    assert webhook(client, "evt_1", "payment.succeeded", data)["status"] == "processed"
    assert webhook(client, "evt_1", "payment.succeeded", data)["status"] == "duplicate"

    detail = client.get(f"{API}/bookings/{booking_id}", headers=auth_headers(player)).json()
    assert detail["status"] == "confirmed"
    assert detail["refund_eligible"] is True
    payment = db.query(Payment).one()
    assert payment.status == PaymentStatus.succeeded
    assert payment.provider_payment_id == "pay_123"

    resp = client.post(f"{API}/bookings/{booking_id}/cancel", headers=auth_headers(owner))
    assert resp.json()["cancelled_by"] == "owner"
    assert resp.json()["refund_status"] == "pending"
    assert fake_gateway.refunds == [
        (payment.id, f"Booking {detail['booking_ref']} cancelled by owner")
    ]

    webhook(client, "evt_2", "refund.succeeded", {"refund_id": "rf_1", "payment_id": "pay_123"})
    detail = client.get(f"{API}/bookings/{booking_id}", headers=auth_headers(player)).json()
    assert detail["refund_status"] == "refunded"


def test_late_payment_auto_refunds_when_slot_taken(
    client: TestClient,
    make_user: Callable[..., User],
    make_turf: Callable[..., Turf],
    auth_headers: Callable[[User], dict[str, str]],
    fake_gateway: FakePaymentGateway,
    db: Session,
) -> None:
    owner = make_user(UserRole.owner)
    turf = make_turf(owner)
    first = book(client, auth_headers(make_user()), turf)["booking"]["id"]
    db.query(Booking).filter(Booking.id == first).update(
        {"status": BookingStatus.expired}, synchronize_session=False
    )
    db.commit()
    second = book(client, auth_headers(make_user()), turf)["booking"]["id"]
    assert second != first
    webhook(
        client,
        "evt_late",
        "payment.succeeded",
        {"payment_id": "pay_late", "metadata": {"booking_id": str(first)}},
    )
    db.expire_all()
    late = db.get(Booking, first)
    assert late is not None and late.status == BookingStatus.expired
    assert late.refund_status.value == "pending"
    assert len(fake_gateway.refunds) == 1


def test_scheduler_and_dashboard(
    client: TestClient,
    make_user: Callable[..., User],
    make_turf: Callable[..., Turf],
    auth_headers: Callable[[User], dict[str, str]],
    db: Session,
) -> None:
    owner = make_user(UserRole.owner)
    turf = make_turf(owner)
    now = datetime.now(UTC)
    player = make_user()
    today_slot = local_day_grid(turf, to_local_date(turf, now))[0]
    db.add_all(
        [
            Booking(
                booking_ref="AAAA1111",
                player_id=player.id,
                turf_id=turf.id,
                start_at=now - timedelta(hours=3),
                end_at=now - timedelta(hours=2),
                slot_count=1,
                total_amount=100000,
                currency="INR",
                status=BookingStatus.confirmed,
            ),
            Booking(
                booking_ref="BBBB2222",
                player_id=player.id,
                turf_id=turf.id,
                start_at=now + timedelta(days=3),
                end_at=now + timedelta(days=3, hours=1),
                slot_count=1,
                total_amount=100000,
                currency="INR",
                status=BookingStatus.pending,
                hold_expires_at=now - timedelta(minutes=1),
            ),
            Booking(
                booking_ref="CCCC3333",
                player_id=player.id,
                turf_id=turf.id,
                start_at=today_slot[0],
                end_at=today_slot[1],
                slot_count=1,
                total_amount=150000,
                currency="INR",
                status=BookingStatus.completed,
            ),
        ]
    )
    db.commit()
    assert run_maintenance(now) == (1, 1)
    assert run_maintenance(now) == (0, 0)

    day = to_local_date(turf, today_slot[0]).isoformat()
    summary = client.get(
        f"{API}/owner/dashboard/summary?from={day}&to={day}", headers=auth_headers(owner)
    ).json()
    assert summary["revenue"] >= 150000
    assert summary["occupancy_pct"] > 0
    assert summary["currency"] == "INR"
    foreign = client.get(
        f"{API}/owner/dashboard/summary?turf_id={turf.id}",
        headers=auth_headers(make_user(UserRole.owner)),
    )
    assert foreign.status_code == 404
    revenue = client.get(
        f"{API}/owner/dashboard/revenue?from={day}&to={day}", headers=auth_headers(owner)
    ).json()
    assert revenue[0]["revenue"] >= 150000
