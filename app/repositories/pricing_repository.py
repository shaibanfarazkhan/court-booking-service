"""Persistence operations for pricing rules and calculation context."""

import uuid
from datetime import date
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.court import Court
from app.models.enums import PricingRuleType
from app.models.pricing_rule import PricingRule
from app.models.venue import Venue
from app.schemas.pricing import PricingRuleInput


class PricingRepository:
    """Query courts and pricing rules without embedding price calculations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_court_context(self, court_id: uuid.UUID) -> dict[str, Any] | None:
        result = await self.session.execute(
            select(
                Court.id.label("court_id"),
                Court.base_price_per_hour.label("base_price_per_hour"),
                Venue.timezone.label("timezone"),
            )
            .join(Venue, Venue.id == Court.venue_id)
            .where(
                Court.id == court_id,
                Court.is_active.is_(True),
                Venue.is_active.is_(True),
            )
        )
        row = result.mappings().one_or_none()
        return dict(row) if row is not None else None

    async def get_active_rules(
        self, court_id: uuid.UUID, booking_date: date
    ) -> list[PricingRule]:
        result = await self.session.execute(
            select(PricingRule)
            .where(
                PricingRule.active.is_(True),
                or_(PricingRule.court_id.is_(None), PricingRule.court_id == court_id),
                or_(
                    PricingRule.start_date.is_(None),
                    PricingRule.start_date <= booking_date,
                ),
                or_(
                    PricingRule.end_date.is_(None), PricingRule.end_date >= booking_date
                ),
            )
            .order_by(PricingRule.priority.desc(), PricingRule.created_at)
        )
        return list(result.scalars().all())

    async def court_exists(self, court_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            select(Court.id).where(Court.id == court_id)
        )
        return result.scalar_one_or_none() is not None

    async def has_overlapping_rule(
        self,
        payload: PricingRuleInput,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        """Detect same-type rules whose date, time, and weekday scopes overlap."""
        scope = [PricingRule.rule_type == payload.rule_type]
        if payload.court_id is not None:
            scope.append(
                or_(
                    PricingRule.court_id.is_(None),
                    PricingRule.court_id == payload.court_id,
                )
            )
        if payload.start_date is not None and payload.end_date is not None:
            scope.extend(
                (
                    or_(
                        PricingRule.end_date.is_(None),
                        PricingRule.end_date >= payload.start_date,
                    ),
                    or_(
                        PricingRule.start_date.is_(None),
                        PricingRule.start_date <= payload.end_date,
                    ),
                )
            )
        if payload.start_time is not None and payload.end_time is not None:
            scope.extend(
                (
                    or_(
                        PricingRule.end_time.is_(None),
                        PricingRule.end_time > payload.start_time,
                    ),
                    or_(
                        PricingRule.start_time.is_(None),
                        PricingRule.start_time < payload.end_time,
                    ),
                )
            )
        result = await self.session.execute(
            select(PricingRule).where(
                PricingRule.active.is_(True),
                *scope,
                PricingRule.id != exclude_id if exclude_id is not None else True,
            )
        )
        candidates = list(result.scalars().all())
        new_days = self._weekday_scope(payload.rule_type, payload.weekdays)
        return any(
            bool(new_days & self._weekday_scope(rule.rule_type, rule.weekdays))
            and not (payload.stackable and rule.stackable)
            for rule in candidates
        )

    async def create_rule(self, values: dict[str, Any]) -> PricingRule:
        rule = PricingRule(**values)
        self.session.add(rule)
        await self.session.flush()
        await self.session.refresh(rule)
        return rule

    async def get_rule(self, rule_id: uuid.UUID) -> PricingRule | None:
        result = await self.session.execute(
            select(PricingRule).where(PricingRule.id == rule_id)
        )
        return result.scalar_one_or_none()

    async def update_rule(
        self, rule: PricingRule, values: dict[str, Any]
    ) -> PricingRule:
        for field, value in values.items():
            setattr(rule, field, value)
        await self.session.flush()
        await self.session.refresh(rule)
        return rule

    async def delete_rule(self, rule: PricingRule) -> None:
        await self.session.delete(rule)
        await self.session.flush()

    async def list_rules(
        self, page: int, page_size: int
    ) -> tuple[list[PricingRule], int]:
        count_result = await self.session.execute(
            select(func.count()).select_from(PricingRule)
        )
        total = int(count_result.scalar_one())
        result = await self.session.execute(
            select(PricingRule)
            .order_by(PricingRule.priority.desc(), PricingRule.name, PricingRule.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    @staticmethod
    def _weekday_scope(
        rule_type: PricingRuleType, weekdays: list[int] | None
    ) -> set[int]:
        if weekdays is not None:
            return set(weekdays)
        if rule_type == PricingRuleType.WEEKEND:
            return {5, 6}
        return set(range(7))
