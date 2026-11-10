"""Allow multiple historical bookings per time slot.

Revision ID: 2d8e6b51f4a7
Revises: 4f2a9c7d1b30
Create Date: 2026-11-10 00:01:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "2d8e6b51f4a7"
down_revision: str | None = "4f2a9c7d1b30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the one-booking-per-slot constraint for expired/cancelled history."""
    op.drop_constraint(
        "bookings_time_slot_id_key",
        "bookings",
        type_="unique",
    )


def downgrade() -> None:
    """Restore one-booking-per-slot uniqueness when history permits it."""
    op.create_unique_constraint(
        "bookings_time_slot_id_key",
        "bookings",
        ["time_slot_id"],
    )
