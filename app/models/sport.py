from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.court import Court


class Sport(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Athletic sport category (e.g. Tennis, Badminton, Squash)."""

    __tablename__ = "sports"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(
        String(110),
        unique=True,
        index=True,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    courts: Mapped[list["Court"]] = relationship(
        "Court",
        back_populates="sport",
        lazy="selectin",
    )
