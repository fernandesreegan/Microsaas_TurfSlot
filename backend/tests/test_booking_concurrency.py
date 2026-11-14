"""Two threads booking the same slot at the same time: exactly one wins."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from app.database import SessionLocal
from app.exceptions import AppError
from app.models import Turf, User, UserRole
from app.schemas.booking import BookingCreate
from app.services.availability import local_day_grid, to_local_date
from app.services.booking_service import create_booking
from app.services.payment_gateway import FakePaymentGateway


def test_concurrent_booking_same_slot(
    make_user: Callable[..., User], make_turf: Callable[..., Turf]
) -> None:
    owner = make_user(UserRole.owner)
    players = [make_user(), make_user()]
    turf = make_turf(owner)
    local = to_local_date(turf, datetime.now(UTC)) + timedelta(days=2)
    start = local_day_grid(turf, local)[5][0]
    barrier = threading.Barrier(2)
    results: list[str] = []
    lock = threading.Lock()

    def worker(player_id: int) -> None:
        with SessionLocal() as session:
            player = session.get(User, player_id)
            assert player is not None
            data = BookingCreate(turf_id=turf.id, start_at=start, slot_count=1)
            barrier.wait()
            try:
                create_booking(session, player, data, FakePaymentGateway())
                outcome = "ok"
            except AppError as exc:
                outcome = exc.code or "error"
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=worker, args=(p.id,)) for p in players]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert sorted(results) == ["SLOT_UNAVAILABLE", "ok"]
