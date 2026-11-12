"""Focused tests for booking policy validation and admin authorization metadata."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import BookingPolicyError, ResourceNotFoundError
from app.schemas.booking_policy import BookingPolicyInput
from app.services.booking_policy_service import BookingPolicyService


def run(coroutine):
    return asyncio.run(coroutine)


def configured_service(*, daily=3, weekly=10, future=20, minimum=30, maximum=180):
    service = BookingPolicyService(AsyncMock())
    service.repository = AsyncMock()
    service.repository.get_active_policy.return_value = SimpleNamespace(
        daily_limit=daily,
        weekly_limit=weekly,
        future_booking_limit=future,
        min_duration_minutes=minimum,
        max_duration_minutes=maximum,
    )
    service.repository.count_daily_bookings.return_value = 0
    service.repository.count_weekly_bookings.return_value = 0
    service.repository.count_future_bookings.return_value = 0
    service.repository.has_overlap.return_value = False
    return service


def validate(service, start=None, end=None):
    start = start or datetime.now(UTC) + timedelta(days=2)
    end = end or start + timedelta(minutes=60)
    run(service.validate_booking(uuid.uuid4(), start, end, datetime.now(UTC)))


@pytest.mark.parametrize(
    ("counter", "limit", "message"),
    [
        ("count_daily_bookings", "daily_limit", "Daily"),
        ("count_weekly_bookings", "weekly_limit", "Weekly"),
        ("count_future_bookings", "future_booking_limit", "Future"),
    ],
)
def test_booking_limits_reject_at_configured_threshold(counter, limit, message):
    parameter = {
        "daily_limit": "daily",
        "weekly_limit": "weekly",
        "future_booking_limit": "future",
    }[limit]
    service = configured_service(**{parameter: 1})
    getattr(service.repository, counter).return_value = 1
    with pytest.raises(BookingPolicyError, match=message):
        validate(service)


def test_overlap_is_rejected():
    service = configured_service()
    service.repository.has_overlap.return_value = True
    with pytest.raises(BookingPolicyError, match="overlaps"):
        validate(service)


@pytest.mark.parametrize("minutes", [15, 181])
def test_minimum_and_maximum_duration_are_rejected(minutes):
    service = configured_service()
    start = datetime.now(UTC) + timedelta(days=2)
    with pytest.raises(BookingPolicyError, match="duration"):
        validate(service, start, start + timedelta(minutes=minutes))


def test_missing_policy_is_rejected():
    service = configured_service()
    service.repository.get_active_policy.return_value = None
    with pytest.raises(ResourceNotFoundError, match="policy"):
        validate(service)


def test_policy_input_validates_duration_order():
    with pytest.raises(ValueError, match="max_duration_minutes"):
        BookingPolicyInput(
            daily_limit=2,
            weekly_limit=5,
            future_booking_limit=5,
            min_duration_minutes=90,
            max_duration_minutes=60,
        )


def test_policy_update_creates_or_replaces_active_policy():
    service = configured_service()
    policy = BookingPolicyInput(
        daily_limit=2,
        weekly_limit=5,
        future_booking_limit=6,
        min_duration_minutes=30,
        max_duration_minutes=120,
    )
    service.repository.save_policy.return_value = "saved"
    assert run(service.update_policy(policy)) == "saved"
    service.repository.save_policy.assert_awaited_once_with(policy.model_dump())
