"""Track whether a cancelled booking qualifies for a refund."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7c3a1b9e2d64"
down_revision: str | None = "2d8e6b51f4a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add refund eligibility metadata without initiating payment refunds."""
    op.add_column(
        "bookings",
        sa.Column(
            "refund_eligible",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove refund eligibility metadata."""
    op.drop_column("bookings", "refund_eligible")
