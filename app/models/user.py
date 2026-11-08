from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Enum, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.admin import Admin
    from app.models.booking import Booking
    from app.models.payment import Payment


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Registered user entity (Members, Staff, and Admins)."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum", native_enum=False),
        default=UserRole.MEMBER,
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # Relationships
    admin_profile: Mapped[Optional["Admin"]] = relationship(
        "Admin",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    bookings: Mapped[list["Booking"]] = relationship(
        "Booking",
        back_populates="user",
        lazy="selectin",
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="user",
        lazy="selectin",
    )

    __table_args__ = (Index("ix_users_role_is_active", "role", "is_active"),)
