import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import SlotStatus

if TYPE_CHECKING:
    from app.models.booking import Booking
    from app.models.court import Court


class TimeSlot(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Discrete inventory slot on a court for scheduling and reservations."""

    __tablename__ = "time_slots"

    court_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    is_peak: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    status: Mapped[SlotStatus] = mapped_column(
        Enum(SlotStatus, name="slot_status_enum", native_enum=False),
        default=SlotStatus.AVAILABLE,
        nullable=False,
        index=True,
    )
    hold_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    court: Mapped["Court"] = relationship(
        "Court",
        back_populates="time_slots",
    )
    booking: Mapped["Booking | None"] = relationship(
        "Booking",
        back_populates="time_slot",
        uselist=False,
    )

    __table_args__ = (
        UniqueConstraint("court_id", "start_time", name="uq_time_slots_court_start"),
        CheckConstraint(
            "end_time > start_time",
            name="ck_time_slots_valid_duration",
        ),
        CheckConstraint(
            "price >= 0",
            name="ck_time_slots_positive_price",
        ),
        Index(
            "ix_time_slots_court_start_end_status",
            "court_id",
            "start_time",
            "end_time",
            "status",
        ),
    )
