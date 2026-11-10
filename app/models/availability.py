"""Recurring weekly availability windows for a court."""

import uuid
from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Time, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.court import Court


class Availability(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A recurring weekly availability window for a court."""

    __tablename__ = "availabilities"

    court_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    weekday: Mapped[int] = mapped_column(nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    court: Mapped["Court"] = relationship("Court", back_populates="availability")

    __table_args__ = (
        CheckConstraint(
            "weekday BETWEEN 0 AND 6", name="ck_availability_valid_weekday"
        ),
        CheckConstraint("end_time > start_time", name="ck_availability_valid_time"),
        UniqueConstraint(
            "court_id",
            "weekday",
            "start_time",
            "end_time",
            name="uq_availability_court_weekday_time",
        ),
    )
