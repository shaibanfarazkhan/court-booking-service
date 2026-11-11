"""Store venue timezone for local availability windows."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9a6d31f0c2b8"
down_revision: str | None = "8e4c2a7d9f13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add timezone metadata, defaulting existing venues to UTC."""
    op.add_column(
        "venues",
        sa.Column(
            "timezone",
            sa.String(length=64),
            server_default="UTC",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove venue timezone metadata."""
    op.drop_column("venues", "timezone")
