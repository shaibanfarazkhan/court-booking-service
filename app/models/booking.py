import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import BookingStatus

if TYPE_CHECKING:
    from app.models.court import Court
    from app.models.payment import Payment
    from app.models.time_slot import TimeSlot
    from app.models.user import User


class Booking(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Court reservation record representing held, confirmed, or cancelled bookings."""

    __tablename__ = "bookings"

    booking_reference: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    court_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    time_slot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("time_slots.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
        index=True,
    )
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status_enum", native_enum=False),
        default=BookingStatus.HELD,
        nullable=False,
        index=True,
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    hold_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancellation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    is_recurring: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    recurring_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(64),
        unique=True,
        nullable=True,
        index=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="bookings",
    )
    court: Mapped["Court"] = relationship(
        "Court",
        back_populates="bookings",
    )
    time_slot: Mapped["TimeSlot"] = relationship(
        "TimeSlot",
        back_populates="booking",
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="booking",
        lazy="selectin",
    )

    __table_args__ = (Index("ix_bookings_user_status", "user_id", "status"),)
