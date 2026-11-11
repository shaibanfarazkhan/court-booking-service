"""Tests for public bookable-slot availability search."""

import asyncio
import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal

import pytest
from sqlalchemy.dialects import postgresql

from app.api.dependencies import get_current_user
from app.api.v1.availability import router as availability_router
from app.main import app
from app.models.enums import BookingStatus, SlotStatus
from app.repositories.availability_repository import AvailabilityRepository
from app.services.availability_service import AvailabilityService


class FakeMappings:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeResult:
    def __init__(self, scalar=None, rows=None):
        self.scalar = scalar
        self.rows = rows or []

    def scalar_one(self):
        return self.scalar

    def mappings(self):
        return FakeMappings(self.rows)


class FakeSession:
    def __init__(self, results):
        self.results = list(results)
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return self.results.pop(0)


def sample_row(**overrides):
    row = {
        "slot_id": uuid.uuid4(),
        "court_id": uuid.uuid4(),
        "court_name": "Court A",
        "venue_id": uuid.uuid4(),
        "venue_name": "Venue A",
        "sport": "Tennis",
        "timezone": "UTC",
        "starts_at": datetime(2026, 12, 1, 10, tzinfo=UTC),
        "ends_at": datetime(2026, 12, 1, 11, tzinfo=UTC),
        "status": SlotStatus.AVAILABLE,
        "price": Decimal("75.00"),
    }
    row.update(overrides)
    return row


def test_search_maps_only_public_slot_fields_and_pagination() -> None:
    row = sample_row()
    service = AvailabilityService(None)
    service.repository = FakeSearchRepository([row], total=21)

    response = asyncio.run(
        service.search_availability(page=2, page_size=10, sort_by="time")
    )

    item = response.items[0]
    assert response.page == 2
    assert response.page_size == 10
    assert response.total == 21
    assert item.available is True
    assert item.status == SlotStatus.AVAILABLE
    assert set(item.model_dump()) == {
        "slot_id",
        "court_id",
        "court_name",
        "venue_id",
        "venue_name",
        "sport",
        "date",
        "weekday",
        "start_time",
        "end_time",
        "status",
        "price",
        "available",
    }


class FakeSearchRepository:
    def __init__(self, rows, total):
        self.rows = rows
        self.total = total
        self.kwargs = None

    async def search_availability(self, **kwargs):
        self.kwargs = kwargs
        return self.rows, self.total

    async def court_availability(self, court_id, **kwargs):
        self.kwargs = {"court_id": court_id, **kwargs}
        return self.rows, self.total


def test_search_passes_filters_sort_and_page_to_repository() -> None:
    filters = {
        "venue_id": uuid.uuid4(),
        "court_id": uuid.uuid4(),
        "sport": "Tennis",
        "slot_date": date(2026, 12, 1),
        "weekday": 1,
        "start_time": time(9),
        "end_time": time(12),
        "duration_minutes": 60,
        "page": 3,
        "page_size": 8,
        "sort_by": "venue",
    }
    service = AvailabilityService(None)
    service.repository = FakeSearchRepository([], total=0)

    asyncio.run(service.search_availability(**filters))

    assert service.repository.kwargs == filters


def test_court_search_uses_path_court_id() -> None:
    court_id = uuid.uuid4()
    service = AvailabilityService(None)
    service.repository = FakeSearchRepository([], total=0)

    asyncio.run(service.court_availability(court_id, page=2, page_size=5))

    assert service.repository.kwargs["court_id"] == court_id
    assert service.repository.kwargs["page"] == 2
    assert service.repository.kwargs["page_size"] == 5


def test_search_maps_utc_slot_datetime_to_venue_local_date_and_time() -> None:
    row = sample_row(
        timezone="Asia/Kolkata",
        starts_at=datetime(2026, 12, 1, 4, 30, tzinfo=UTC),
        ends_at=datetime(2026, 12, 1, 5, 30, tzinfo=UTC),
    )
    service = AvailabilityService(None)
    service.repository = FakeSearchRepository([row], total=1)

    item = asyncio.run(service.search_availability()).items[0]

    assert item.date == date(2026, 12, 1)
    assert item.weekday == 1
    assert item.start_time == time(10)
    assert item.end_time == time(11)


def test_invalid_service_filters_are_rejected_before_query() -> None:
    service = AvailabilityService(None)
    service.repository = FakeSearchRepository([], total=0)

    with pytest.raises(ValueError, match="page must"):
        asyncio.run(service.search_availability(page=0))
    with pytest.raises(ValueError, match="page_size"):
        asyncio.run(service.search_availability(page_size=101))
    with pytest.raises(ValueError, match="start_time"):
        asyncio.run(service.search_availability(start_time=time(12), end_time=time(10)))
    with pytest.raises(ValueError, match="weekday"):
        asyncio.run(service.search_availability(weekday=7))
    with pytest.raises(ValueError, match="duration_minutes"):
        asyncio.run(service.search_availability(duration_minutes=0))
    assert service.repository.kwargs is None


def test_repository_joins_metadata_and_hides_unavailable_or_booked_slots() -> None:
    session = FakeSession([FakeResult(scalar=1), FakeResult(rows=[])])
    repository = AvailabilityRepository(session)

    asyncio.run(
        repository.search_availability(
            page=1,
            page_size=20,
            sort_by="time",
            venue_id=uuid.uuid4(),
            court_id=uuid.uuid4(),
            sport="Tennis",
            slot_date=date(2026, 12, 1),
            weekday=1,
            start_time=time(9),
            end_time=time(12),
            duration_minutes=60,
        )
    )

    assert len(session.statements) == 2
    sql = str(session.statements[1].compile(dialect=postgresql.dialect())).lower()
    assert "join courts" in sql
    assert "join venues" in sql
    assert "join sports" in sql
    assert "availabilities" in sql
    assert "bookings" in sql
    assert "exists" in sql
    assert "limit" in sql and "offset" in sql
    filters = session.statements[1].compile(dialect=postgresql.dialect()).params
    assert filters["status_1"] == SlotStatus.AVAILABLE
    assert BookingStatus.HELD in filters["status_2"]
    assert BookingStatus.CONFIRMED in filters["status_2"]
    assert BookingStatus.COMPLETED in filters["status_2"]
    assert BookingStatus.CANCELLED not in filters["status_2"]


def test_repository_orders_by_venue_or_court() -> None:
    for sort_by, expected_column in (
        ("venue", "venues.name"),
        ("court", "courts.name"),
    ):
        session = FakeSession([FakeResult(scalar=0), FakeResult(rows=[])])
        asyncio.run(
            AvailabilityRepository(session).search_availability(
                page=1, page_size=10, sort_by=sort_by
            )
        )
        sql = str(session.statements[1].compile(dialect=postgresql.dialect())).lower()
        assert f"order by {expected_column}" in sql


def test_availability_endpoints_are_public_and_registered() -> None:
    paths = app.openapi()["paths"]
    assert "/api/v1/availability" in paths
    assert "/api/v1/courts/{court_id}/availability" in paths
    assert {route.path for route in availability_router.routes} == {
        "/availability",
        "/courts/{court_id}/availability",
    }
    assert all(
        all(
            dependency.call is not get_current_user
            for dependency in route.dependant.dependencies
        )
        for route in availability_router.routes
    )
