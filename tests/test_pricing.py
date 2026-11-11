"""Tests for pricing rule selection, calculations, and API authorization."""

import asyncio
import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from pydantic import ValidationError

from app.api.dependencies import require_staff
from app.api.v1.pricing import router as pricing_router
from app.core.exceptions import PricingRuleOverlapError
from app.models.enums import PricingEffect, PricingRuleType, PricingValueType, UserRole
from app.schemas.pricing import PricingRuleInput
from app.services.pricing_service import PricingService


class FakePricingRepository:
    def __init__(self, base_rate=Decimal("100.00"), rules=None):
        self.context = {
            "court_id": uuid.uuid4(),
            "base_price_per_hour": base_rate,
            "timezone": "UTC",
        }
        self.rules = list(rules or [])

    async def get_court_context(self, _court_id):
        return self.context

    async def get_active_rules(self, _court_id, _booking_date):
        return self.rules


def make_rule(
    rule_type,
    effect,
    value_type,
    value,
    *,
    priority,
    name=None,
    stackable=False,
    start_date=None,
    end_date=None,
    start_time=None,
    end_time=None,
    weekdays=None,
):
    return SimpleNamespace(
        id=uuid.uuid4(),
        rule_type=rule_type,
        effect=effect,
        value_type=value_type,
        value=Decimal(str(value)),
        priority=priority,
        name=name or rule_type.value,
        stackable=stackable,
        start_date=start_date,
        end_date=end_date,
        start_time=start_time,
        end_time=end_time,
        weekdays=weekdays,
        created_at=datetime.now(UTC),
    )


def price_with(*rules, booking_date=date(2026, 11, 10), start=time(10), end=time(11)):
    service = PricingService(None)
    service.repository = FakePricingRepository(rules=rules)
    return asyncio.run(service.calculate_price(uuid.uuid4(), booking_date, start, end))


def test_base_price_calculates_for_booking_duration() -> None:
    response = price_with(
        booking_date=date(2026, 11, 10), start=time(9), end=time(10, 30)
    )

    assert response.base_price == Decimal("150.00")
    assert response.applied_rule == "Base price"
    assert response.surcharge == Decimal("0.00")
    assert response.discount == Decimal("0.00")
    assert response.final_price == Decimal("150.00")
    assert response.currency == "USD"


def test_weekend_pricing_applies_percentage_surcharge() -> None:
    weekend = make_rule(
        PricingRuleType.WEEKEND,
        PricingEffect.SURCHARGE,
        PricingValueType.PERCENTAGE,
        20,
        priority=700,
    )

    response = price_with(weekend, booking_date=date(2026, 11, 14), end=time(12))

    assert response.base_price == Decimal("200.00")
    assert response.surcharge == Decimal("40.00")
    assert response.final_price == Decimal("240.00")


def test_holiday_rule_overrides_price_for_configured_date_range() -> None:
    holiday = make_rule(
        PricingRuleType.HOLIDAY,
        PricingEffect.OVERRIDE,
        PricingValueType.FIXED_PRICE,
        150,
        priority=900,
        name="Holiday rate",
        start_date=date(2026, 12, 24),
        end_date=date(2026, 12, 26),
    )

    response = price_with(holiday, booking_date=date(2026, 12, 25))

    assert response.applied_rule == "Holiday rate"
    assert response.surcharge == Decimal("50.00")
    assert response.final_price == Decimal("150.00")


def test_peak_rule_adds_hourly_surcharge_in_matching_window() -> None:
    peak = make_rule(
        PricingRuleType.PEAK,
        PricingEffect.SURCHARGE,
        PricingValueType.AMOUNT,
        15,
        priority=800,
        start_time=time(17),
        end_time=time(21),
    )

    response = price_with(peak, start=time(18), end=time(20))

    assert response.surcharge == Decimal("30.00")
    assert response.final_price == Decimal("230.00")


def test_off_peak_rule_discounts_base_price() -> None:
    off_peak = make_rule(
        PricingRuleType.OFF_PEAK,
        PricingEffect.DISCOUNT,
        PricingValueType.PERCENTAGE,
        25,
        priority=600,
        start_time=time(6),
        end_time=time(12),
    )

    response = price_with(off_peak, start=time(9), end=time(11))

    assert response.discount == Decimal("50.00")
    assert response.final_price == Decimal("150.00")


def test_manual_override_has_highest_default_priority() -> None:
    override = make_rule(
        PricingRuleType.MANUAL_OVERRIDE,
        PricingEffect.OVERRIDE,
        PricingValueType.FIXED_PRICE,
        80,
        priority=1000,
        name="Manual rate",
    )
    weekend = make_rule(
        PricingRuleType.WEEKEND,
        PricingEffect.SURCHARGE,
        PricingValueType.AMOUNT,
        50,
        priority=700,
    )

    response = price_with(weekend, override, booking_date=date(2026, 11, 14))

    assert response.applied_rule == "Manual rate"
    assert response.applied_rules == ["Manual rate"]
    assert response.discount == Decimal("20.00")
    assert response.final_price == Decimal("80.00")


def test_only_stackable_rules_apply_beside_highest_priority_rule() -> None:
    holiday = make_rule(
        PricingRuleType.HOLIDAY,
        PricingEffect.SURCHARGE,
        PricingValueType.AMOUNT,
        10,
        priority=900,
        name="Holiday",
        start_date=date(2026, 12, 25),
        end_date=date(2026, 12, 25),
    )
    promotion = make_rule(
        PricingRuleType.PROMOTION,
        PricingEffect.DISCOUNT,
        PricingValueType.AMOUNT,
        5,
        priority=500,
        name="Promotion",
        stackable=True,
    )
    lower_priority = make_rule(
        PricingRuleType.WEEKEND,
        PricingEffect.SURCHARGE,
        PricingValueType.AMOUNT,
        20,
        priority=300,
        name="Weekend",
    )

    response = price_with(
        lower_priority,
        promotion,
        holiday,
        booking_date=date(2026, 12, 25),
    )

    assert response.applied_rules == ["Holiday", "Promotion"]
    assert response.surcharge == Decimal("10.00")
    assert response.discount == Decimal("5.00")
    assert response.final_price == Decimal("105.00")


def test_overlap_validation_rejects_active_rule_conflict() -> None:
    payload = PricingRuleInput(
        name="Peak",
        rule_type=PricingRuleType.PEAK,
        effect=PricingEffect.SURCHARGE,
        value_type=PricingValueType.AMOUNT,
        value=Decimal("10"),
        start_time=time(17),
        end_time=time(20),
    )
    service = PricingService(None)
    service.repository = AsyncMock()
    service.repository.has_overlapping_rule.return_value = True

    with pytest.raises(PricingRuleOverlapError):
        asyncio.run(service.create_rule(payload))


def test_rule_validation_rejects_invalid_ranges_weekdays_and_values() -> None:
    base = {
        "name": "Holiday",
        "rule_type": PricingRuleType.HOLIDAY,
        "effect": PricingEffect.SURCHARGE,
        "value_type": PricingValueType.AMOUNT,
        "value": Decimal("10"),
        "start_date": date(2026, 12, 26),
        "end_date": date(2026, 12, 24),
    }
    with pytest.raises(ValidationError, match="end_date"):
        PricingRuleInput(**base)
    with pytest.raises(ValidationError, match="weekdays"):
        PricingRuleInput(**{**base, "start_date": date(2026, 12, 24), "weekdays": [7]})
    with pytest.raises(ValidationError, match="greater than 0"):
        PricingRuleInput(**{**base, "start_date": date(2026, 12, 24), "value": 0})
    with pytest.raises(ValidationError, match="end_time"):
        PricingRuleInput(
            name="Peak",
            rule_type=PricingRuleType.PEAK,
            effect=PricingEffect.SURCHARGE,
            value_type=PricingValueType.AMOUNT,
            value=10,
            start_time=time(19),
            end_time=time(18),
        )


def test_calculation_rejects_invalid_time_range() -> None:
    service = PricingService(None)
    service.repository = FakePricingRepository()

    with pytest.raises(ValueError, match="start_time"):
        asyncio.run(
            service.calculate_price(
                uuid.uuid4(), date(2026, 11, 10), time(12), time(11)
            )
        )


def test_staff_or_admin_required_for_rule_administration() -> None:
    admin_routes = {
        "/pricing/rules",
        "/pricing/rules/{rule_id}",
    }
    for route in pricing_router.routes:
        assert isinstance(route, APIRoute)
        if route.path in admin_routes:
            assert require_staff in {
                dependency.call for dependency in route.dependant.dependencies
            }

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(require_staff(SimpleNamespace(role=UserRole.MEMBER)))
    assert exc_info.value.status_code == 403
    assert (
        asyncio.run(require_staff(SimpleNamespace(role=UserRole.ADMIN))).role
        == UserRole.ADMIN
    )


def test_calculate_endpoint_returns_pricing_breakdown() -> None:
    result = SimpleNamespace(
        base_price=Decimal("100"),
        applied_rule="Base price",
        applied_rules=[],
        surcharge=Decimal("0"),
        discount=Decimal("0"),
        final_price=Decimal("100"),
        currency="USD",
    )
    service = SimpleNamespace(calculate_price=AsyncMock(return_value=result))
    original = __import__(
        "app.api.v1.pricing", fromlist=["PricingService"]
    ).PricingService

    class ServiceFactory:
        def __new__(cls, _session):
            return service

    import app.api.v1.pricing as pricing_api

    pricing_api.PricingService = ServiceFactory
    try:
        from app.api.v1.pricing import calculate_price

        response = asyncio.run(
            calculate_price(
                uuid.uuid4(), date(2026, 11, 10), time(10), time(11), AsyncMock()
            )
        )
    finally:
        pricing_api.PricingService = original

    assert response.final_price == Decimal("100")
    assert response.currency == "USD"
