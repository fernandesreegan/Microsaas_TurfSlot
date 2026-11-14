"""Seed demo turfs (with map coordinates) owned by a demo owner account.

Idempotent: turfs are matched by slug, so re-running only adds missing ones.

Usage::

    python -m app.scripts.seed_demo
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import generate_token, hash_password
from app.database import SessionLocal
from app.models import SportType, Turf, User, UserRole

logger = logging.getLogger(__name__)

DEMO_OWNER_EMAIL = "demo-owner@turfslot.local"


@dataclass(frozen=True)
class DemoTurf:
    """Static description of one demo turf."""

    name: str
    city: str
    address: str
    lat: float
    lng: float
    sports: tuple[SportType, ...]
    price_rupees: int


DEMO_TURFS: tuple[DemoTurf, ...] = (
    DemoTurf(
        "Koramangala Kick Arena",
        "Bengaluru",
        "80 Feet Rd, Koramangala",
        12.9352,
        77.6245,
        (SportType.football, SportType.cricket),
        1200,
    ),
    DemoTurf(
        "Indiranagar Turf Hub",
        "Bengaluru",
        "100 Feet Rd, Indiranagar",
        12.9719,
        77.6412,
        (SportType.football,),
        1400,
    ),
    DemoTurf(
        "Whitefield Sports Park",
        "Bengaluru",
        "ITPL Main Rd, Whitefield",
        12.9698,
        77.7500,
        (SportType.football, SportType.badminton),
        1000,
    ),
    DemoTurf(
        "Anna Nagar Goal Zone",
        "Chennai",
        "2nd Ave, Anna Nagar",
        13.0850,
        80.2101,
        (SportType.football, SportType.cricket),
        1100,
    ),
    DemoTurf(
        "Velachery Box Cricket",
        "Chennai",
        "Velachery Main Rd",
        12.9815,
        80.2180,
        (SportType.cricket,),
        900,
    ),
    DemoTurf(
        "OMR Sports Arena",
        "Chennai",
        "Rajiv Gandhi Salai, Thoraipakkam",
        12.9407,
        80.2340,
        (SportType.football,),
        1300,
    ),
    DemoTurf(
        "Gachibowli Turf Club",
        "Hyderabad",
        "Gachibowli Main Rd",
        17.4401,
        78.3489,
        (SportType.football, SportType.cricket),
        1200,
    ),
    DemoTurf(
        "Banjara Hills Kickoff",
        "Hyderabad",
        "Road No. 12, Banjara Hills",
        17.4156,
        78.4347,
        (SportType.football,),
        1500,
    ),
    DemoTurf(
        "Andheri Sports Dome",
        "Mumbai",
        "Link Rd, Andheri West",
        19.1364,
        72.8296,
        (SportType.football, SportType.cricket),
        1800,
    ),
    DemoTurf(
        "Powai Lakeside Turf",
        "Mumbai",
        "Hiranandani Gardens, Powai",
        19.1176,
        72.9060,
        (SportType.football,),
        2000,
    ),
    DemoTurf(
        "Baner Turf Arena",
        "Pune",
        "Baner Rd, Baner",
        18.5590,
        73.7868,
        (SportType.football, SportType.cricket),
        1100,
    ),
    DemoTurf(
        "Koregaon Park Sports",
        "Pune",
        "North Main Rd, Koregaon Park",
        18.5362,
        73.8940,
        (SportType.football,),
        1300,
    ),
    DemoTurf(
        "Saket Turf Ground",
        "Delhi",
        "Press Enclave Marg, Saket",
        28.5245,
        77.2066,
        (SportType.football, SportType.cricket),
        1600,
    ),
    DemoTurf(
        "Dwarka Sports Hub",
        "Delhi",
        "Sector 10, Dwarka",
        28.5823,
        77.0500,
        (SportType.football,),
        1200,
    ),
    DemoTurf(
        "Kakkanad Turf Park",
        "Kochi",
        "Infopark Rd, Kakkanad",
        10.0159,
        76.3419,
        (SportType.football,),
        1000,
    ),
    DemoTurf(
        "RS Puram Arena",
        "Coimbatore",
        "DB Rd, RS Puram",
        11.0089,
        76.9500,
        (SportType.football, SportType.cricket),
        900,
    ),
)


def _slugify(name: str) -> str:
    return "-".join(name.lower().replace(".", "").split())


def _get_or_create_owner(db: Session) -> User:
    owner = db.scalar(select(User).where(User.email == DEMO_OWNER_EMAIL))
    if owner is None:
        owner = User(
            email=DEMO_OWNER_EMAIL,
            hashed_password=hash_password(generate_token()),
            full_name="TurfSlot Demo Owner",
            role=UserRole.owner,
            is_verified=True,
            is_active=True,
        )
        db.add(owner)
        db.flush()
    return owner


def seed(db: Session) -> int:
    """Insert missing demo turfs; return how many were created."""
    owner = _get_or_create_owner(db)
    existing = set(db.scalars(select(Turf.slug)))
    created = 0
    for t in DEMO_TURFS:
        slug = _slugify(t.name)
        if slug in existing:
            continue
        db.add(
            Turf(
                owner_id=owner.id,
                name=t.name,
                slug=slug,
                description=(
                    f"Floodlit {', '.join(s.value for s in t.sports)} turf in {t.city}. "
                    "Demo listing."
                ),
                address=t.address,
                city=t.city.lower(),
                city_display=t.city,
                latitude=Decimal(str(t.lat)),
                longitude=Decimal(str(t.lng)),
                timezone="Asia/Kolkata",
                sport_types=list(t.sports),
                amenities=["Floodlights", "Parking", "Changing room", "Drinking water"],
                image_urls=[],
                slot_duration_minutes=60,
                opening_time=time(6, 0),
                closing_time=time(23, 0),
                base_price=t.price_rupees * 100,
                currency="INR",
                is_active=True,
            )
        )
        created += 1
    db.commit()
    return created


def main() -> None:
    """CLI entry point."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with SessionLocal() as db:
        created = seed(db)
    logger.info("Demo seed complete: %d turf(s) created, %d defined.", created, len(DEMO_TURFS))


if __name__ == "__main__":
    main()
