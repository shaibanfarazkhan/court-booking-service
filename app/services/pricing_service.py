"""Pricing rule validation and booking price calculation."""

import uuid
from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Decimal

from app.core.exceptions import PricingRuleOverlapError, ResourceNotFoundError
from app.db.session import AsyncSession
from app.models.enums import (
    PricingEffect,
    PricingRuleType,
    PricingValueType,
)
from app.models.pricing_rule import PricingRule
from app.repositories.pricing_repository import PricingRepository
from app.schemas.pricing import (
    PricingCalculationResponse,
    PricingRuleInput,
    PricingRuleListResponse,
    PricingRuleResponse,
)

CENT = Decimal("0.01")
HOUR_SECONDS = Decimal("3600")
DEFAULT_PRIORITIES = {
    PricingRuleType.MANUAL_OVERRIDE: 1000,
    PricingRuleType.HOLIDAY: 900,
    PricingRuleType.PEAK: 800,
    PricingRuleType.WEEKEND: 700,
    PricingRuleType.OFF_PEAK: 600,
    PricingRuleType.PROMOTION: 500,
}


class PricingService:
    """Coordinate rule CRUD and compute transparent price breakdowns."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = PricingRepository(session)

    async def calculate_price(
        self,
        court_id: uuid.UUID,
        booking_date: date,
        start_time: time,
        end_time: time,
    ) -> PricingCalculationResponse:
        """Calculate price from the highest-priority applicable rule and stackables."""
        if start_time.tzinfo is not None or end_time.tzinfo is not None:
            raise ValueError("start_time and end_time must be local wall times")
        if start_time >= end_time:
            raise ValueError("start_time must be before end_time")
        context = await self.repository.get_court_context(court_id)
        if context is None:
            raise ResourceNotFoundError("Active court not found.")

        duration_seconds = Decimal(
            str(
                (
                    datetime.combine(booking_date, end_time)
                    - datetime.combine(booking_date, start_time)
                ).total_seconds()
            )
        )
        duration_hours = duration_seconds / HOUR_SECONDS
        base_rate = Decimal(context["base_price_per_hour"])
        base_price = self._money(base_rate * duration_hours)
        rules = await self.repository.get_active_rules(court_id, booking_date)
        applicable = [
            rule
            for rule in rules
            if self._is_applicable(rule, booking_date, start_time, end_time)
        ]
        applicable.sort(key=lambda rule: (-rule.priority, rule.created_at))
        selected = self._select_rules(applicable)

        current_rate = base_rate
        surcharge = Decimal("0")
        discount = Decimal("0")
        for rule in selected:
            if rule.effect == PricingEffect.OVERRIDE:
                new_rate = Decimal(rule.value)
                change = (new_rate - current_rate) * duration_hours
                if change >= 0:
                    surcharge += change
                else:
                    discount += -change
                current_rate = new_rate
                continue

            if rule.value_type == PricingValueType.PERCENTAGE:
                change_per_hour = current_rate * Decimal(rule.value) / Decimal("100")
            else:
                change_per_hour = Decimal(rule.value)
            change = change_per_hour * duration_hours

            if rule.effect == PricingEffect.SURCHARGE:
                surcharge += change
                current_rate += change_per_hour
            else:
                applied_discount_per_hour = min(change_per_hour, current_rate)
                applied_discount = applied_discount_per_hour * duration_hours
                discount += applied_discount
                current_rate -= applied_discount_per_hour

        final_price = self._money(max(Decimal("0"), base_price + surcharge - discount))
        applied_names = [rule.name for rule in selected]
        return PricingCalculationResponse(
            base_price=base_price,
            applied_rule=applied_names[0] if applied_names else "Base price",
            applied_rules=applied_names,
            surcharge=self._money(surcharge),
            discount=self._money(discount),
            final_price=final_price,
            currency="USD",
        )

    async def create_rule(self, payload: PricingRuleInput) -> PricingRule:
        values = self._rule_values(payload)
        if payload.court_id is not None and not await self.repository.court_exists(
            payload.court_id
        ):
            raise ResourceNotFoundError("Court not found.")
        if payload.active and await self.repository.has_overlapping_rule(payload):
            raise PricingRuleOverlapError("An active pricing rule overlaps this scope.")
        return await self.repository.create_rule(values)

    async def update_rule(
        self, rule_id: uuid.UUID, payload: PricingRuleInput
    ) -> PricingRule:
        rule = await self.repository.get_rule(rule_id)
        if rule is None:
            raise ResourceNotFoundError("Pricing rule not found.")
        values = self._rule_values(payload)
        if payload.court_id is not None and not await self.repository.court_exists(
            payload.court_id
        ):
            raise ResourceNotFoundError("Court not found.")
        if payload.active and await self.repository.has_overlapping_rule(
            payload, exclude_id=rule_id
        ):
            raise PricingRuleOverlapError("An active pricing rule overlaps this scope.")
        return await self.repository.update_rule(rule, values)

    async def delete_rule(self, rule_id: uuid.UUID) -> None:
        rule = await self.repository.get_rule(rule_id)
        if rule is None:
            raise ResourceNotFoundError("Pricing rule not found.")
        await self.repository.delete_rule(rule)

    async def list_rules(
        self, page: int = 1, page_size: int = 20
    ) -> PricingRuleListResponse:
        if page < 1:
            raise ValueError("page must be at least 1")
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        rules, total = await self.repository.list_rules(page, page_size)
        return PricingRuleListResponse(
            items=[PricingRuleResponse.model_validate(rule) for rule in rules],
            page=page,
            page_size=page_size,
            total=total,
        )

    @staticmethod
    def _rule_values(payload: PricingRuleInput) -> dict[str, object]:
        values = payload.model_dump()
        if values["priority"] is None:
            values["priority"] = DEFAULT_PRIORITIES[payload.rule_type]
        return values

    @staticmethod
    def _is_applicable(
        rule: PricingRule,
        booking_date: date,
        start_time: time,
        end_time: time,
    ) -> bool:
        if rule.start_date is not None and booking_date < rule.start_date:
            return False
        if rule.end_date is not None and booking_date > rule.end_date:
            return False
        weekdays = rule.weekdays
        if weekdays is None and rule.rule_type == PricingRuleType.WEEKEND:
            weekdays = [5, 6]
        if weekdays is not None and booking_date.weekday() not in weekdays:
            return False
        if rule.start_time is not None and start_time < rule.start_time:
            return False
        return not (rule.end_time is not None and end_time > rule.end_time)

    @staticmethod
    def _select_rules(rules: list[PricingRule]) -> list[PricingRule]:
        if not rules:
            return []
        primary = rules[0]
        return [primary, *(rule for rule in rules[1:] if rule.stackable)]

    @staticmethod
    def _money(value: Decimal) -> Decimal:
        return value.quantize(CENT, rounding=ROUND_HALF_UP)
