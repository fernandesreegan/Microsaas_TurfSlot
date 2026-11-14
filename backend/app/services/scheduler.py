"""In-process background maintenance (APScheduler, every 60 seconds).

- ``pending`` bookings whose hold has lapsed -> ``expired``
- ``confirmed`` bookings that have ended -> ``completed``

Both are conditional bulk UPDATEs, so the job is idempotent and safe to run
concurrently with request handlers. ``app.main`` calls :func:`start_scheduler` /
:func:`shutdown_scheduler` from the lifespan when ``SCHEDULER_ENABLED`` is true.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import update

from app.database import SessionLocal
from app.models import Booking, BookingStatus

logger = logging.getLogger(__name__)

JOB_ID = "booking_maintenance"
INTERVAL_SECONDS = 60

_scheduler: BackgroundScheduler | None = None
_lock = threading.Lock()


def run_maintenance(now: datetime | None = None) -> tuple[int, int]:
    """Expire lapsed holds and complete finished bookings.

    Args:
        now: Reference time (defaults to the current UTC time).

    Returns:
        ``(expired_count, completed_count)``.
    """
    current = now or datetime.now(UTC)
    with SessionLocal() as db:
        expired = db.execute(
            update(Booking)
            .where(
                Booking.status == BookingStatus.pending,
                Booking.hold_expires_at < current,
            )
            .values(status=BookingStatus.expired)
            .execution_options(synchronize_session=False)
        ).rowcount  # type: ignore[attr-defined]
        completed = db.execute(
            update(Booking)
            .where(Booking.status == BookingStatus.confirmed, Booking.end_at < current)
            .values(status=BookingStatus.completed)
            .execution_options(synchronize_session=False)
        ).rowcount  # type: ignore[attr-defined]
        db.commit()
    if expired or completed:
        logger.info("Maintenance: %s holds expired, %s bookings completed", expired, completed)
    return int(expired or 0), int(completed or 0)


def _job() -> None:
    """Scheduler entrypoint; never lets an exception kill the scheduler thread."""
    try:
        run_maintenance()
    except Exception:
        logger.exception("Booking maintenance job failed")


def start_scheduler() -> None:
    """Start the background scheduler (no-op if already running)."""
    global _scheduler
    with _lock:
        if _scheduler is not None and _scheduler.running:
            return
        scheduler = BackgroundScheduler(timezone="UTC")
        scheduler.add_job(
            _job,
            "interval",
            seconds=INTERVAL_SECONDS,
            id=JOB_ID,
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        scheduler.start()
        _scheduler = scheduler


def shutdown_scheduler() -> None:
    """Stop the background scheduler if it is running."""
    global _scheduler
    with _lock:
        if _scheduler is not None and _scheduler.running:
            _scheduler.shutdown(wait=False)
        _scheduler = None
