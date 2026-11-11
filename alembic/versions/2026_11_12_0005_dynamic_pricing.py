"""Add scoped dynamic pricing rules."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b7d91e40ac53"
down_revision: str | None = "9a6d31f0c2b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create pricing rules with scoped conditions, effect, and priority."""
    op.create_table(
        "pricing_rules",
        sa.Column("court_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "rule_type",
            sa.Enum(
                "MANUAL_OVERRIDE",
                "HOLIDAY",
                "PEAK",
                "WEEKEND",
                "OFF_PEAK",
                "PROMOTION",
                name="pricing_rule_type_enum",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "effect",
            sa.Enum(
                "OVERRIDE",
                "SURCHARGE",
                "DISCOUNT",
                name="pricing_effect_enum",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "value_type",
            sa.Enum(
                "FIXED_PRICE",
                "AMOUNT",
                "PERCENTAGE",
                name="pricing_value_type_enum",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("value", sa.Numeric(10, 2), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("stackable", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("weekdays", sa.JSON(), nullable=True),
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
        sa.CheckConstraint("value > 0", name="ck_pricing_rules_positive_value"),
        sa.CheckConstraint(
            "priority >= 0", name="ck_pricing_rules_nonnegative_priority"
        ),
        sa.CheckConstraint(
            "start_date IS NULL OR end_date IS NULL OR end_date >= start_date",
            name="ck_pricing_rules_valid_dates",
        ),
        sa.CheckConstraint(
            "start_time IS NULL OR end_time IS NULL OR end_time > start_time",
            name="ck_pricing_rules_valid_times",
        ),
        sa.ForeignKeyConstraint(["court_id"], ["courts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pricing_rules_court_id"), "pricing_rules", ["court_id"])
    op.create_index(op.f("ix_pricing_rules_rule_type"), "pricing_rules", ["rule_type"])
    op.create_index(op.f("ix_pricing_rules_active"), "pricing_rules", ["active"])
    op.create_index(
        "ix_pricing_rules_active_priority",
        "pricing_rules",
        ["active", "priority"],
    )


def downgrade() -> None:
    """Drop pricing rules and their indexes."""
    op.drop_index("ix_pricing_rules_active_priority", table_name="pricing_rules")
    op.drop_index(op.f("ix_pricing_rules_active"), table_name="pricing_rules")
    op.drop_index(op.f("ix_pricing_rules_rule_type"), table_name="pricing_rules")
    op.drop_index(op.f("ix_pricing_rules_court_id"), table_name="pricing_rules")
    op.drop_table("pricing_rules")
