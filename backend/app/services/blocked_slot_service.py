"""Owner-managed blocked slots: listing, validated batch creation and deletion."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models import BlockedSlot, Booking, BookingStatus, Turf, User
from app.schemas.slot import BlockedSlotCreate
from app.services.availability import local_day_grid, to_local_date

logger = logging.getLogger(__name__)

EXCLUSION_VIOLATION = "23P01"


def list_blocks(
    db: Session, turf: Turf, range_start: datetime, range_end: datetime
) -> Sequence[BlockedSlot]:
    """Return the turf's blocks overlapping ``[range_start, range_end)``, oldest first."""
    return db.scalars(
        select(BlockedSlot)
        .where(
            BlockedSlot.turf_id == turf.id,
            BlockedSlot.start_at < range_end,
            BlockedSlot.end_at > range_start,
        )
        .order_by(BlockedSlot.start_at)
    ).all()


def _validate_alignment(turf: Turf, item: BlockedSlotCreate) -> tuple[datetime, datetime]:
    """Return the UTC bounds of ``item`` after checking they are grid boundaries of one day.

    Raises:
        BadRequestError: 400 ``NOT_GRID_ALIGNED`` otherwise.
    """
    start = item.start_at.astimezone(UTC)
    end = item.end_at.astimezone(UTC)
    grid = local_day_grid(turf, to_local_date(turf, start))
    starts = {slot_start for slot_start, _ in grid}
    ends = {slot_end for _, slot_end in grid}
    if start not in starts or end not in ends:
        raise BadRequestError(
            "Blocked range must start and end on slot boundaries of a single day",
            code="NOT_GRID_ALIGNED",
        )
    return start, end


def _is_integrity_exclusion(exc: IntegrityError) -> bool:
    """Return True if the IntegrityError is an exclusion-constraint violation."""
    return getattr(exc.orig, "sqlstate", None) == EXCLUSION_VIOLATION


def create_blocks(
    db: Session,
    turf: Turf,
    user: User,
    items: Sequence[BlockedSlotCreate],
    now_utc: datetime | None = None,
) -> list[BlockedSlot]:
    """Create several blocks atomically (all or nothing).

    Raises:
        BadRequestError: A range is misaligned (``NOT_GRID_ALIGNED``) or already over.
        ConflictError: ``BOOKING_CONFLICT_WITH_BLOCK`` if a range overlaps a confirmed
            booking or a pending booking with an unexpired hold; ``OVERLAPPING_BLOCK``
            if ranges overlap each other or existing blocks.
    """
    now = now_utc or datetime.now(UTC)
    ranges: list[tuple[datetime, datetime, str | None]] = []
    for item in items:
        start, end = _validate_alignment(turf, item)
        if end <= now:
            raise BadRequestError(
                "Cannot block a slot that has already ended", code="BLOCK_IN_PAST"
            )
        ranges.append((start, end, item.reason))

    conflict = db.scalars(
        select(Booking.booking_ref)
        .where(
            Booking.turf_id == turf.id,
            or_(
                Booking.status == BookingStatus.confirmed,
                and_(Booking.status == BookingStatus.pending, Booking.hold_expires_at > now),
            ),
            or_(
                *(and_(Booking.start_at < end, Booking.end_at > start) for start, end, _ in ranges)
            ),
        )
        .limit(1)
    ).first()
    if conflict is not None:
        raise ConflictError(
            "A blocked range overlaps an existing booking", code="BOOKING_CONFLICT_WITH_BLOCK"
        )

    blocks = [
        BlockedSlot(turf_id=turf.id, start_at=start, end_at=end, reason=reason, created_by=user.id)
        for start, end, reason in ranges
    ]
    db.add_all(blocks)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _is_integrity_exclusion(exc):
            raise ConflictError(
                "A blocked range overlaps an existing block", code="OVERLAPPING_BLOCK"
            ) from exc
        raise
    for block in blocks:
        db.refresh(block)
    logger.info("User %s blocked %d slot range(s) on turf %s", user.id, len(blocks), turf.id)
    return blocks


def delete_block(db: Session, turf: Turf, block_id: int) -> None:
    """Delete a block of ``turf`` or raise 404."""
    block = db.get(BlockedSlot, block_id)
    if block is None or block.turf_id != turf.id:
        raise NotFoundError("Blocked slot not found")
    db.delete(block)
    db.commit()
