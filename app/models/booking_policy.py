"""Global configurable limits applied when a member creates a booking."""

from sqlalchemy import Boolean, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BookingPolicy(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Booking limits; a partial unique index permits one active policy."""

    __tablename__ = "booking_policies"

    active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    daily_limit: Mapped[int] = mapped_column(nullable=False)
    weekly_limit: Mapped[int] = mapped_column(nullable=False)
    future_booking_limit: Mapped[int] = mapped_column(nullable=False)
    min_duration_minutes: Mapped[int] = mapped_column(nullable=False)
    max_duration_minutes: Mapped[int] = mapped_column(nullable=False)

    __table_args__ = (
        CheckConstraint("daily_limit > 0", name="ck_booking_policies_daily_positive"),
        CheckConstraint("weekly_limit > 0", name="ck_booking_policies_weekly_positive"),
        CheckConstraint(
            "future_booking_limit > 0", name="ck_booking_policies_future_positive"
        ),
        CheckConstraint(
            "min_duration_minutes > 0", name="ck_booking_policies_min_duration_positive"
        ),
        CheckConstraint(
            "max_duration_minutes >= min_duration_minutes",
            name="ck_booking_policies_duration_range",
        ),
        Index(
            "uq_booking_policies_one_active",
            "active",
            unique=True,
            postgresql_where=active.is_(True),
            sqlite_where=active.is_(True),
        ),
    )
