"""Owner-blocked time ranges on a turf."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func, literal_column
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.turf import Turf
    from app.models.user import User


class BlockedSlot(CreatedAtMixin, Base):
    """A ``[start_at, end_at)`` UTC range during which a turf cannot be booked.

    Overlapping blocks on the same turf are rejected by the
    ``blocked_slots_no_overlap`` exclusion constraint (requires ``btree_gist``),
    SQLSTATE 23P01 -> map to 409 ``OVERLAPPING_BLOCK``.
    """

    __tablename__ = "blocked_slots"
    __table_args__ = (CheckConstraint("end_at > start_at", name="time_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    turf_id: Mapped[int] = mapped_column(ForeignKey("turfs.id", ondelete="CASCADE"), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    turf: Mapped[Turf] = relationship(back_populates="blocked_slots")
    creator: Mapped[User | None] = relationship(foreign_keys=[created_by])


BlockedSlot.__table__.append_constraint(  # type: ignore[attr-defined]
    ExcludeConstraint(
        (BlockedSlot.__table__.c.turf_id, "="),  # type: ignore[attr-defined]
        (
            func.tstzrange(
                BlockedSlot.__table__.c.start_at,  # type: ignore[attr-defined]
                BlockedSlot.__table__.c.end_at,  # type: ignore[attr-defined]
                literal_column("'[)'"),
            ),
            "&&",
        ),
        name="blocked_slots_no_overlap",
        using="gist",
    )
)
