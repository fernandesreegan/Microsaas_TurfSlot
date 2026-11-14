"""Tests for the demo seed script."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Turf
from app.scripts.seed_demo import DEMO_TURFS, seed


def test_seed_is_idempotent_and_geolocated(db: Session) -> None:
    assert seed(db) == len(DEMO_TURFS)
    assert seed(db) == 0
    total = db.scalar(select(func.count()).select_from(Turf).where(Turf.latitude.is_not(None)))
    assert total == len(DEMO_TURFS)
