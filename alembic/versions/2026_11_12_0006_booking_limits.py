"""Add configurable global booking limits."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c8e42d1f7a90"
down_revision: str | None = "b7d91e40ac53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create booking policies and enforce one active row."""
    op.create_table(
        "booking_policies",
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("daily_limit", sa.Integer(), nullable=False),
        sa.Column("weekly_limit", sa.Integer(), nullable=False),
        sa.Column("future_booking_limit", sa.Integer(), nullable=False),
        sa.Column("min_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("max_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
            "daily_limit > 0", name="ck_booking_policies_daily_positive"
        ),
        sa.CheckConstraint(
            "weekly_limit > 0", name="ck_booking_policies_weekly_positive"
        ),
        sa.CheckConstraint(
            "future_booking_limit > 0", name="ck_booking_policies_future_positive"
        ),
        sa.CheckConstraint(
            "min_duration_minutes > 0", name="ck_booking_policies_min_duration_positive"
        ),
        sa.CheckConstraint(
            "max_duration_minutes >= min_duration_minutes",
            name="ck_booking_policies_duration_range",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_booking_policies_one_active",
        "booking_policies",
        ["active"],
        unique=True,
        postgresql_where=sa.text("active IS TRUE"),
        sqlite_where=sa.text("active IS 1"),
    )


def downgrade() -> None:
    """Drop booking policy configuration."""
    op.drop_index("uq_booking_policies_one_active", table_name="booking_policies")
    op.drop_table("booking_policies")
