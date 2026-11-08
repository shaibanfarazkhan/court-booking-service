from datetime import time
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Numeric, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.court import Court


class Venue(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Physical facility or complex containing sports courts."""

    __tablename__ = "venues"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(160),
        unique=True,
        index=True,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    latitude: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 6),
        nullable=True,
    )
    longitude: Mapped[Decimal | None] = mapped_column(
        Numeric(9, 6),
        nullable=True,
    )
    opening_time: Mapped[time] = mapped_column(Time, nullable=False)
    closing_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    courts: Mapped[list["Court"]] = relationship(
        "Court",
        back_populates="venue",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
