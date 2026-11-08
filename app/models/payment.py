import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import PaymentMethod, PaymentStatus

if TYPE_CHECKING:
    from app.models.booking import Booking
    from app.models.user import User


class Payment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Financial transaction ledger record for payments and refunds."""

    __tablename__ = "payments"

    payment_reference: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    booking_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bookings.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    refund_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        default="USD",
        nullable=False,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status_enum", native_enum=False),
        default=PaymentStatus.PENDING,
        nullable=False,
        index=True,
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method_enum", native_enum=False),
        default=PaymentMethod.CREDIT_CARD,
        nullable=False,
    )
    refunded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    booking: Mapped["Booking"] = relationship(
        "Booking",
        back_populates="payments",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="payments",
    )

    __table_args__ = (
        CheckConstraint(
            "amount >= 0",
            name="ck_payments_positive_amount",
        ),
        CheckConstraint(
            "refund_amount >= 0",
            name="ck_payments_positive_refund_amount",
        ),
        CheckConstraint(
            "refund_amount <= amount",
            name="ck_payments_refund_lte_amount",
        ),
        Index("ix_payments_booking_status", "booking_id", "status"),
        Index("ix_payments_user_created", "user_id", "created_at"),
    )
