import uuid
from datetime import date, time
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Time,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import PricingEffect, PricingRuleType, PricingValueType


class PricingRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Scoped pricing rule with explicit priority and optional stacking."""

    __tablename__ = "pricing_rules"

    court_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("courts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    rule_type: Mapped[PricingRuleType] = mapped_column(
        Enum(
            PricingRuleType,
            name="pricing_rule_type_enum",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
        index=True,
    )
    effect: Mapped[PricingEffect] = mapped_column(
        Enum(
            PricingEffect,
            name="pricing_effect_enum",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
    )
    value_type: Mapped[PricingValueType] = mapped_column(
        Enum(
            PricingValueType,
            name="pricing_value_type_enum",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
    )
    value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    priority: Mapped[int] = mapped_column(default=0, nullable=False)
    stackable: Mapped[bool] = mapped_column(default=False, nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False, index=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    weekdays: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        CheckConstraint("value > 0", name="ck_pricing_rules_positive_value"),
        CheckConstraint("priority >= 0", name="ck_pricing_rules_nonnegative_priority"),
        CheckConstraint(
            "start_date IS NULL OR end_date IS NULL OR end_date >= start_date",
            name="ck_pricing_rules_valid_dates",
        ),
        CheckConstraint(
            "start_time IS NULL OR end_time IS NULL OR end_time > start_time",
            name="ck_pricing_rules_valid_times",
        ),
        Index("ix_pricing_rules_active_priority", "active", "priority"),
    )
