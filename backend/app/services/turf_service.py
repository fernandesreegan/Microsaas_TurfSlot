"""Turf CRUD, search, slug generation and pricing-rule management."""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError
from app.models import Booking, BookingStatus, SportType, Turf, TurfPricingRule, User, UserRole
from app.schemas.turf import PricingRuleCreate, PricingRuleUpdate, TurfCreate, TurfUpdate
from app.services.availability import turf_ids_with_availability

logger = logging.getLogger(__name__)

SLUG_MAX_LENGTH = 150
SLUG_INSERT_ATTEMPTS = 5
# Upper bound of candidate turfs examined when filtering search results by date.
DATE_FILTER_MAX_CANDIDATES = 1000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalize_city(city: str) -> str:
    """Return the normalized (trimmed, lowercased, single-spaced) search form of a city."""
    return " ".join(city.split()).lower()


def slugify(name: str) -> str:
    """Build an ASCII, lowercase, hyphen-separated slug from a turf name."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    slug = slug[:SLUG_MAX_LENGTH].rstrip("-")
    return slug or "turf"


def unique_slug(db: Session, name: str) -> str:
    """Return a slug for ``name`` not used by any turf, adding ``-2``, ``-3``... on collision."""
    base = slugify(name)
    pattern = re.compile(rf"^{re.escape(base)}(?:-(\d+))?$")
    existing = db.scalars(
        select(Turf.slug).where((Turf.slug == base) | Turf.slug.like(f"{base}-%"))
    ).all()
    taken = {slug for slug in existing if pattern.match(slug)}
    if base not in taken:
        return base
    suffix = 2
    while f"{base}-{suffix}" in taken:
        suffix += 1
    return f"{base}-{suffix}"


def can_manage(user: User | None, turf: Turf) -> bool:
    """Return True if ``user`` is the turf's owner or an admin."""
    return user is not None and (user.role == UserRole.admin or turf.owner_id == user.id)


def ensure_can_manage(user: User, turf: Turf) -> None:
    """Raise 403 ``NOT_OWNER`` unless ``user`` owns the turf or is an admin."""
    if not can_manage(user, turf):
        raise ForbiddenError("You do not own this turf", code="NOT_OWNER")


def get_turf(db: Session, turf_id: int) -> Turf:
    """Return a turf by id (active or not) or raise 404."""
    turf = db.get(Turf, turf_id)
    if turf is None:
        raise NotFoundError("Turf not found")
    return turf


def get_manageable_turf(db: Session, turf_id: int, user: User) -> Turf:
    """Return a turf the user may manage (owner/admin), raising 404/403 otherwise."""
    turf = get_turf(db, turf_id)
    ensure_can_manage(user, turf)
    return turf


def get_visible_turf(db: Session, id_or_slug: str | int, user: User | None) -> Turf:
    """Return a turf by numeric id or slug, hiding inactive turfs from the public.

    Inactive turfs are returned only to their owner or an admin; others get 404.
    """
    key = str(id_or_slug)
    stmt = select(Turf).options(selectinload(Turf.pricing_rules))
    stmt = stmt.where(Turf.id == int(key)) if key.isdigit() else stmt.where(Turf.slug == key)
    turf = db.scalars(stmt).first()
    if turf is None or (not turf.is_active and not can_manage(user, turf)):
        raise NotFoundError("Turf not found")
    return turf


# ---------------------------------------------------------------------------
# Turf CRUD
# ---------------------------------------------------------------------------


def create_turf(db: Session, owner: User, data: TurfCreate) -> Turf:
    """Create a turf for ``owner`` with a unique slug derived from its name."""
    values = data.model_dump()
    city = values.pop("city")
    for attempt in range(SLUG_INSERT_ATTEMPTS):
        turf = Turf(
            **values,
            owner_id=owner.id,
            slug=unique_slug(db, data.name),
            city=normalize_city(city),
            city_display=city,
            is_active=True,
        )
        db.add(turf)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            logger.info("Slug collision creating turf (attempt %d); retrying", attempt + 1)
            continue
        db.refresh(turf)
        logger.info("Turf %s created by user %s", turf.id, owner.id)
        return turf
    raise ConflictError("Could not allocate a unique slug; please retry", code="SLUG_CONFLICT")


def update_turf(db: Session, turf: Turf, data: TurfUpdate) -> Turf:
    """Apply a partial update to ``turf``. The slug is never changed."""
    changes = data.model_dump(exclude_unset=True)
    opening: time = changes.get("opening_time", turf.opening_time)
    closing: time = changes.get("closing_time", turf.closing_time)
    if closing <= opening:
        raise AppError(422, "closing_time must be after opening_time", code="VALIDATION_ERROR")
    if "city" in changes:
        city = changes.pop("city")
        turf.city = normalize_city(city)
        turf.city_display = city
    for field, value in changes.items():
        setattr(turf, field, value)
    db.commit()
    db.refresh(turf)
    return turf


def deactivate_turf(db: Session, turf: Turf, now_utc: datetime | None = None) -> None:
    """Soft-deactivate a turf; 409 if it has confirmed bookings that have not ended."""
    now = now_utc or datetime.now(UTC)
    has_future = db.scalar(
        select(func.count())
        .select_from(Booking)
        .where(
            Booking.turf_id == turf.id,
            Booking.status == BookingStatus.confirmed,
            Booking.end_at > now,
        )
    )
    if has_future:
        raise ConflictError(
            "Turf has upcoming confirmed bookings; cancel them first",
            code="TURF_HAS_FUTURE_BOOKINGS",
        )
    turf.is_active = False
    db.commit()
    logger.info("Turf %s deactivated", turf.id)


def list_owner_turfs(db: Session, owner: User) -> Sequence[Turf]:
    """Return all turfs of ``owner`` (including inactive), newest first."""
    return db.scalars(
        select(Turf).where(Turf.owner_id == owner.id).order_by(Turf.created_at.desc(), Turf.id)
    ).all()


@dataclass(frozen=True)
class TurfSearch:
    """Search filters for the public turf listing."""

    city: str | None = None
    sport: SportType | None = None
    q: str | None = None
    local_date: date | None = None


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards so user input matches literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_turfs(
    db: Session,
    filters: TurfSearch,
    offset: int,
    limit: int,
    now_utc: datetime | None = None,
) -> tuple[Sequence[Turf], int]:
    """Search active turfs and return ``(page_items, total)``.

    With ``filters.local_date`` only turfs having at least one available slot on that
    turf-local date are returned (best-effort; at most
    ``DATE_FILTER_MAX_CANDIDATES`` candidates are examined).
    """
    stmt = select(Turf).where(Turf.is_active.is_(True))
    if filters.city and filters.city.strip():
        stmt = stmt.where(Turf.city == normalize_city(filters.city))
    if filters.sport is not None:
        stmt = stmt.where(Turf.sport_types.contains([filters.sport]))
    if filters.q and filters.q.strip():
        stmt = stmt.where(Turf.name.ilike(f"%{_escape_like(filters.q.strip())}%", escape="\\"))
    stmt = stmt.order_by(Turf.name, Turf.id)

    if filters.local_date is None:
        total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
        items = db.scalars(stmt.offset(offset).limit(limit)).all()
        return items, total

    candidates = db.scalars(stmt.limit(DATE_FILTER_MAX_CANDIDATES)).all()
    if len(candidates) == DATE_FILTER_MAX_CANDIDATES:
        logger.warning("Date-filtered search truncated at %d candidates", len(candidates))
    available_ids = turf_ids_with_availability(db, candidates, filters.local_date, now_utc)
    matching = [turf for turf in candidates if turf.id in available_ids]
    return matching[offset : offset + limit], len(matching)


# ---------------------------------------------------------------------------
# Pricing rules
# ---------------------------------------------------------------------------


def _rules_overlap(
    a_day: int | None, a_start: time, a_end: time, b_day: int | None, b_start: time, b_end: time
) -> bool:
    """Return True if two rules' days intersect (None = every day) and times intersect."""
    days_intersect = a_day is None or b_day is None or a_day == b_day
    return days_intersect and a_start < b_end and b_start < a_end


def _ensure_no_overlap(
    db: Session, turf: Turf, data: PricingRuleCreate, exclude_rule_id: int | None = None
) -> None:
    """Raise 409 ``OVERLAPPING_RULE`` if ``data`` overlaps another rule of the turf."""
    rules = db.scalars(select(TurfPricingRule).where(TurfPricingRule.turf_id == turf.id)).all()
    for rule in rules:
        if rule.id == exclude_rule_id:
            continue
        if _rules_overlap(
            data.day_of_week,
            data.start_time,
            data.end_time,
            rule.day_of_week,
            rule.start_time,
            rule.end_time,
        ):
            raise ConflictError(
                f"Overlaps existing pricing rule {rule.id}", code="OVERLAPPING_RULE"
            )


def list_pricing_rules(db: Session, turf: Turf) -> Sequence[TurfPricingRule]:
    """Return a turf's pricing rules ordered by day then start time."""
    return db.scalars(
        select(TurfPricingRule)
        .where(TurfPricingRule.turf_id == turf.id)
        .order_by(
            TurfPricingRule.day_of_week.asc().nulls_first(),
            TurfPricingRule.start_time,
            TurfPricingRule.id,
        )
    ).all()


def create_pricing_rule(db: Session, turf: Turf, data: PricingRuleCreate) -> TurfPricingRule:
    """Create a pricing rule after checking it does not overlap existing rules."""
    _ensure_no_overlap(db, turf, data)
    rule = TurfPricingRule(turf_id=turf.id, **data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def get_pricing_rule(db: Session, turf: Turf, rule_id: int) -> TurfPricingRule:
    """Return a rule of ``turf`` or raise 404."""
    rule = db.get(TurfPricingRule, rule_id)
    if rule is None or rule.turf_id != turf.id:
        raise NotFoundError("Pricing rule not found")
    return rule


def update_pricing_rule(
    db: Session, turf: Turf, rule: TurfPricingRule, data: PricingRuleUpdate
) -> TurfPricingRule:
    """Replace a pricing rule's fields after checking for overlaps with other rules."""
    _ensure_no_overlap(db, turf, data, exclude_rule_id=rule.id)
    for field, value in data.model_dump().items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


def delete_pricing_rule(db: Session, rule: TurfPricingRule) -> None:
    """Delete a pricing rule."""
    db.delete(rule)
    db.commit()
