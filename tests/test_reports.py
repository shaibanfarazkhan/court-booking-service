"""Tests for weekly utilization report calculations and access control."""

import asyncio
import uuid
from datetime import date, time
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from pydantic import ValidationError

from app.api.dependencies import require_staff
from app.api.v1.reports import router
from app.models.enums import UserRole
from app.schemas.report import ReportDateRange
from app.services.report_service import ReportService


def run(coroutine):
    return asyncio.run(coroutine)


def make_service(rows=None, prices=None):
    service = ReportService(None)
    service.repository = AsyncMock()
    service.repository.get_court_daily_aggregates.return_value = list(rows or [])
    service.repository.get_priced_booked_slots.return_value = list(prices or [])
    service.pricing_service = AsyncMock()
    service.pricing_service.calculate_price.return_value = SimpleNamespace(
        final_price=Decimal("50.00")
    )
    return service


def court_row(
    day,
    *,
    court_id=None,
    total=10,
    booked=4,
    available=6,
    cancelled=1,
    confirmed=4,
):
    return {
        "court_id": court_id or uuid.uuid4(),
        "court_name": "Court A",
        "venue_name": "Venue A",
        "sport": "Tennis",
        "report_date": day,
        "total_slots": total,
        "booked_slots": booked,
        "available_slots": available,
        "cancelled_bookings": cancelled,
        "confirmed_bookings": confirmed,
    }


def test_weekly_report_summary_daily_breakdown_and_per_court_revenue():
    day1, day2 = date(2026, 11, 9), date(2026, 11, 10)
    court_id = uuid.uuid4()
    row1 = court_row(day1, court_id=court_id)
    row2 = court_row(day2, court_id=court_id, total=5, booked=1, available=4)
    service = make_service(
        [row1, row2],
        [
            {
                "court_id": row1["court_id"],
                "booking_date": day1,
                "start_time": time(10),
                "end_time": time(11),
                "slot_count": 2,
            }
        ],
    )

    report = run(service.weekly_utilization(day1, day2))

    assert report.summary.total_courts == 1
    assert report.summary.total_slots == 15
    assert report.summary.booked_slots == 5
    assert report.summary.available_slots == 10
    assert report.summary.cancelled_bookings == 2
    assert report.summary.confirmed_bookings == 8
    assert report.summary.utilization_percent == Decimal("33.33")
    assert report.summary.estimated_revenue == Decimal("100.00")
    assert report.bookings_per_court[0].court_name == "Court A"
    assert report.bookings_per_court[0].venue_name == "Venue A"
    assert report.bookings_per_court[0].sport == "Tennis"
    assert report.bookings_per_court[0].estimated_revenue == Decimal("100.00")
    assert [item.booked_slots for item in report.daily_breakdown] == [4, 1]
    assert report.peak_booking_day == day1
    assert report.least_busy_day == day2
    service.pricing_service.calculate_price.assert_awaited_once_with(
        row1["court_id"], day1, time(10), time(11)
    )


def test_empty_report_returns_zero_totals_and_calendar_days():
    report = run(
        make_service().weekly_utilization(date(2026, 11, 9), date(2026, 11, 11))
    )
    assert report.summary.total_courts == 0
    assert report.summary.utilization_percent == Decimal("0.00")
    assert report.summary.estimated_revenue == Decimal("0.00")
    assert len(report.daily_breakdown) == 3
    assert all(day.utilization_percent == 0 for day in report.daily_breakdown)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2026, 11, 10), date(2026, 11, 9)),
        (date(2026, 11, 1), date(2026, 12, 2)),
    ],
)
def test_report_date_range_rejects_invalid_ranges(start, end):
    with pytest.raises(ValidationError):
        ReportDateRange(start_date=start, end_date=end)


def test_report_date_range_accepts_31_inclusive_days():
    assert ReportDateRange(start_date=date(2026, 11, 1), end_date=date(2026, 12, 1))


def test_report_endpoint_requires_staff_or_admin():
    endpoint = next(route for route in router.routes if isinstance(route, APIRoute))
    assert any(
        dependency.call is require_staff
        for dependency in endpoint.dependant.dependencies
    )


@pytest.mark.parametrize("role", [UserRole.STAFF, UserRole.ADMIN])
def test_staff_and_admin_pass_report_authorization(role):
    user = SimpleNamespace(role=role)
    assert asyncio.run(require_staff(user)) is user


def test_member_is_denied_report_authorization():
    with pytest.raises(HTTPException) as error:
        asyncio.run(require_staff(SimpleNamespace(role=UserRole.MEMBER)))
    assert error.value.status_code == 403
