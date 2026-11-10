import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import CourtType, SurfaceType

if TYPE_CHECKING:
    from app.models.availability import Availability
    from app.models.booking import Booking
    from app.models.court_image import CourtImage
    from app.models.sport import Sport
    from app.models.time_slot import TimeSlot
    from app.models.venue import Venue


class Court(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Playable court surface within a venue."""

    __tablename__ = "courts"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sport_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sports.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    court_type: Mapped[CourtType] = mapped_column(
        Enum(CourtType, name="court_type_enum", native_enum=False),
        default=CourtType.INDOOR,
        nullable=False,
    )
    surface_type: Mapped[SurfaceType] = mapped_column(
        Enum(SurfaceType, name="surface_type_enum", native_enum=False),
        default=SurfaceType.HARD,
        nullable=False,
    )
    base_price_per_hour: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    active = synonym("is_active")

    @property
    def indoor(self) -> bool:
        """Expose the enclosure as a boolean for court management clients."""
        return self.court_type == CourtType.INDOOR

    @indoor.setter
    def indoor(self, value: bool) -> None:
        self.court_type = CourtType.INDOOR if value else CourtType.OUTDOOR

    @property
    def sport_type(self) -> str:
        """Expose the normalized sport's display name."""
        return self.sport.name

    # Relationships
    venue: Mapped["Venue"] = relationship(
        "Venue",
        back_populates="courts",
    )
    sport: Mapped["Sport"] = relationship(
        "Sport",
        back_populates="courts",
    )
    images: Mapped[list["CourtImage"]] = relationship(
        "CourtImage",
        back_populates="court",
        cascade="all, delete-orphan",
        order_by="CourtImage.display_order",
        lazy="selectin",
    )
    time_slots: Mapped[list["TimeSlot"]] = relationship(
        "TimeSlot",
        back_populates="court",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    bookings: Mapped[list["Booking"]] = relationship(
        "Booking",
        back_populates="court",
        lazy="selectin",
    )
    availability: Mapped[list["Availability"]] = relationship(
        "Availability",
        back_populates="court",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("venue_id", "name", name="uq_courts_venue_id_name"),
        CheckConstraint(
            "base_price_per_hour >= 0",
            name="ck_courts_positive_base_price",
        ),
        Index("ix_courts_venue_is_active", "venue_id", "is_active"),
        Index("ix_courts_sport_is_active", "sport_id", "is_active"),
    )
