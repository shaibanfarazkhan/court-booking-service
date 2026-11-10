"""Add venue country and recurring court availability.

Revision ID: 4f2a9c7d1b30
Revises: None
Create Date: 2026-11-10 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "4f2a9c7d1b30"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add country to existing venues and create weekly availability."""
    op.add_column(
        "venues",
        sa.Column("country", sa.String(length=100), nullable=True),
    )
    op.execute("UPDATE venues SET country = 'India' WHERE country IS NULL")
    op.alter_column(
        "venues",
        "country",
        existing_type=sa.String(length=100),
        nullable=False,
        server_default="India",
    )
    op.create_table(
        "availabilities",
        sa.Column("court_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "weekday BETWEEN 0 AND 6", name="ck_availability_valid_weekday"
        ),
        sa.CheckConstraint("end_time > start_time", name="ck_availability_valid_time"),
        sa.ForeignKeyConstraint(["court_id"], ["courts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "court_id",
            "weekday",
            "start_time",
            "end_time",
            name="uq_availability_court_weekday_time",
        ),
    )
    op.create_index(
        op.f("ix_availabilities_court_id"),
        "availabilities",
        ["court_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove recurring availability and the venue country column."""
    op.drop_index(op.f("ix_availabilities_court_id"), table_name="availabilities")
    op.drop_table("availabilities")
    op.drop_column("venues", "country")
