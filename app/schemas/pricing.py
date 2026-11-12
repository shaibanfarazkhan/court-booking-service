"""Request and response DTOs for pricing configuration and calculations."""

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import PricingEffect, PricingRuleType, PricingValueType


class PricingRuleInput(BaseModel):
    """Create or replace a date, time, or weekday-scoped pricing rule."""

    model_config = ConfigDict(
        title="Pricing Rule Request",
        json_schema_extra={
            "examples": [
                {
                    "name": "Weekend court rate",
                    "rule_type": "WEEKEND",
                    "effect": "SURCHARGE",
                    "value_type": "PERCENTAGE",
                    "value": "15.00",
                    "active": True,
                    "weekdays": [5, 6],
                }
            ]
        },
    )

    name: str = Field(
        min_length=1, max_length=120, description="Staff-facing rule name."
    )
    court_id: uuid.UUID | None = Field(
        default=None, description="Optional court scope; null applies globally."
    )
    rule_type: PricingRuleType = Field(
        description="Condition that activates this rule."
    )
    effect: PricingEffect = Field(
        description="Override, surcharge, or discount effect."
    )
    value_type: PricingValueType = Field(description="Unit used for the rule value.")
    value: Decimal = Field(
        gt=0,
        max_digits=10,
        decimal_places=2,
        description="Positive price or adjustment amount.",
    )
    priority: int | None = Field(default=None, ge=0, le=10000)
    stackable: bool = False
    active: bool = True
    start_date: date | None = None
    end_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    weekdays: list[int] | None = None

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_local_time(cls, value: time | None) -> time | None:
        if value is not None and value.tzinfo is not None:
            raise ValueError("pricing rule times must be local wall times")
        return value

    @model_validator(mode="after")
    def validate_rule(self) -> "PricingRuleInput":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if (self.start_time is None) != (self.end_time is None):
            raise ValueError("start_time and end_time must be provided together")
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
            raise ValueError("end_time must be after start_time")
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("start_date and end_date must be provided together")
        if self.rule_type == PricingRuleType.HOLIDAY and self.start_date is None:
            raise ValueError("holiday rules require a date range")
        if self.rule_type in (PricingRuleType.PEAK, PricingRuleType.OFF_PEAK):
            if self.start_time is None:
                raise ValueError("peak and off-peak rules require a time range")
        if self.rule_type == PricingRuleType.MANUAL_OVERRIDE and (
            self.effect != PricingEffect.OVERRIDE
            or self.value_type != PricingValueType.FIXED_PRICE
        ):
            raise ValueError("manual overrides require a fixed-price override")
        if self.effect == PricingEffect.OVERRIDE:
            if self.value_type != PricingValueType.FIXED_PRICE:
                raise ValueError("override effect requires FIXED_PRICE value_type")
        elif self.value_type == PricingValueType.FIXED_PRICE:
            raise ValueError("FIXED_PRICE value_type requires OVERRIDE effect")
        if (
            self.effect == PricingEffect.DISCOUNT
            and self.value_type == PricingValueType.PERCENTAGE
            and self.value > 100
        ):
            raise ValueError("percentage discounts cannot exceed 100")
        if self.weekdays is not None:
            if not self.weekdays:
                raise ValueError("weekdays cannot be empty")
            if any(not 0 <= weekday <= 6 for weekday in self.weekdays):
                raise ValueError("weekdays must be between 0 and 6")
            if len(set(self.weekdays)) != len(self.weekdays):
                raise ValueError("weekdays cannot contain duplicates")
        return self


class PricingRuleResponse(BaseModel):
    """Public representation of an active or inactive pricing rule."""

    model_config = ConfigDict(from_attributes=True, title="Pricing Rule")

    id: uuid.UUID
    name: str
    court_id: uuid.UUID | None
    rule_type: PricingRuleType
    effect: PricingEffect
    value_type: PricingValueType
    value: Decimal
    priority: int
    stackable: bool
    active: bool
    start_date: date | None
    end_date: date | None
    start_time: time | None
    end_time: time | None
    weekdays: list[int] | None
    created_at: datetime
    updated_at: datetime


class PricingRuleListResponse(BaseModel):
    """Paginated pricing-rule administration response."""

    model_config = ConfigDict(title="Pricing Rule List")

    items: list[PricingRuleResponse] = Field(description="Rules on this page.")
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)


class PricingCalculationResponse(BaseModel):
    """Breakdown of the hourly base price and applicable rule adjustments."""

    model_config = ConfigDict(
        title="Price Quote",
        json_schema_extra={
            "examples": [
                {
                    "base_price": "750.00",
                    "applied_rule": "Weekend court rate",
                    "applied_rules": ["Weekend court rate"],
                    "surcharge": "112.50",
                    "discount": "0.00",
                    "final_price": "862.50",
                    "currency": "USD",
                }
            ]
        },
    )

    base_price: Decimal = Field(description="Base rate multiplied by booking duration.")
    applied_rule: str = Field(description="Primary pricing rule or base-price label.")
    applied_rules: list[str] = Field(
        description="All pricing rules applied to the quote."
    )
    surcharge: Decimal = Field(description="Total surcharge amount.")
    discount: Decimal = Field(description="Total discount amount.")
    final_price: Decimal = Field(
        description="Final quoted amount in the response currency."
    )
    currency: str = Field(default="USD", description="Currency code for amounts.")
