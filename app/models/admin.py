import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class Admin(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Administrative profile for system operators and venue staff."""

    __tablename__ = "admins"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    permissions: Mapped[list[Any]] = mapped_column(
        JSONB,
        default=list,
        server_default="[]",
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationship
    user: Mapped["User"] = relationship(
        "User",
        back_populates="admin_profile",
    )
