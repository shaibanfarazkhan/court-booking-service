"""Unit tests for Phase 5 court management behavior."""

import asyncio
import uuid
from datetime import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from app.api.dependencies import get_current_user, require_admin
from app.api.v1.courts import _raise_http_error, router
from app.core.exceptions import (
    DuplicateAvailabilityError,
    ResourceNotFoundError,
)
from app.models.availability import Availability
from app.models.enums import SurfaceType
from app.schemas.courts import (
    AvailabilityCreate,
    AvailabilityPatch,
    CourtCreate,
    CourtPatch,
    VenueCreate,
    VenuePatch,
)
from app.services.court_service import CourtService


def run(coroutine):
    """Run a service coroutine from synchronous pytest tests."""
    return asyncio.run(coroutine)


def repository() -> AsyncMock:
    """Build a mock repository attached to a CourtService instance."""
    return AsyncMock()


def test_venue_create_update_delete_and_not_found() -> None:
    repo = repository()
    service = CourtService(AsyncMock())
    service.repository = repo
    venue = SimpleNamespace(opening_time=time(8), closing_time=time(22))
    repo.create_venue.return_value = venue
    repo.get_venue.return_value = venue
    payload = VenueCreate(
        name="Central Courts",
        address="1 Main Road",
        city="Hyderabad",
        state="Telangana",
        country="India",
        postal_code="500001",
    )

    created = run(service.create_venue(payload))
    assert created is venue
    assert repo.create_venue.await_args.args[0]["slug"] == "central-courts"

    patch = VenuePatch(name="Central Courts West")
    run(service.update_venue(uuid.uuid4(), patch))
    repo.update_venue.assert_awaited_once()
    run(service.delete_venue(uuid.uuid4()))
    repo.delete_venue.assert_awaited_once_with(venue)

    repo.get_venue.return_value = None
    with pytest.raises(ResourceNotFoundError):
        run(service.get_venue(uuid.uuid4()))


def test_venue_patch_rejects_invalid_operating_hours() -> None:
    repo = repository()
    service = CourtService(AsyncMock())
    service.repository = repo
    repo.get_venue.return_value = SimpleNamespace(
        opening_time=time(8), closing_time=time(22)
    )
    with pytest.raises(ValueError, match="closing_time"):
        run(service.update_venue(uuid.uuid4(), VenuePatch(closing_time=time(7))))


def test_court_create_update_delete_and_foreign_key_validation() -> None:
    repo = repository()
    service = CourtService(AsyncMock())
    service.repository = repo
    venue_id = uuid.uuid4()
    court = SimpleNamespace()
    sport = SimpleNamespace()
    repo.get_venue.return_value = object()
    repo.get_active_sport.return_value = sport
    repo.create_court.return_value = court
    payload = CourtCreate(
        venue_id=venue_id,
        name="Court 1",
        sport_type="Tennis",
        surface_type=SurfaceType.HARD,
        indoor=True,
    )
    assert run(service.create_court(payload)) is court
    repo.create_court.assert_awaited_once()

    repo.get_court.return_value = court
    repo.update_court.return_value = court
    run(service.update_court(uuid.uuid4(), CourtPatch(name="Court 2")))
    repo.update_court.assert_awaited_once()
    run(service.delete_court(uuid.uuid4()))
    repo.delete_court.assert_awaited_once_with(court)

    repo.get_venue.return_value = None
    with pytest.raises(ResourceNotFoundError, match="venue"):
        run(service.create_court(payload))

    repo.get_venue.return_value = object()
    repo.get_active_sport.return_value = None
    with pytest.raises(ResourceNotFoundError, match="sport"):
        run(service.create_court(payload))

    repo.get_court.return_value = None
    with pytest.raises(ResourceNotFoundError, match="Court"):
        run(service.get_court(uuid.uuid4()))


def test_availability_crud_duplicate_and_foreign_key_validation() -> None:
    repo = repository()
    service = CourtService(AsyncMock())
    service.repository = repo
    court_id = uuid.uuid4()
    window = SimpleNamespace(
        id=uuid.uuid4(),
        court_id=court_id,
        weekday=0,
        start_time=time(9),
        end_time=time(10),
    )
    payload = AvailabilityCreate(
        court_id=court_id,
        weekday=0,
        start_time=time(9),
        end_time=time(10),
    )
    repo.court_exists.return_value = True
    repo.availability_exists.return_value = False
    repo.create_availability.return_value = window
    assert run(service.create_availability(payload)) is window

    repo.availability_exists.return_value = True
    with pytest.raises(DuplicateAvailabilityError):
        run(service.create_availability(payload))

    repo.availability_exists.return_value = False
    repo.get_availability.return_value = window
    repo.update_availability.return_value = window
    run(service.update_availability(window.id, AvailabilityPatch(weekday=1)))
    repo.update_availability.assert_awaited_once()
    run(service.delete_availability(window.id))
    repo.delete_availability.assert_awaited_once_with(window)

    repo.get_availability.return_value = None
    with pytest.raises(ResourceNotFoundError, match="Availability"):
        run(service.get_availability(uuid.uuid4()))

    repo.court_exists.return_value = False
    with pytest.raises(ResourceNotFoundError, match="court"):
        run(service.create_availability(payload))


def test_availability_schema_validates_weekday_and_time_range() -> None:
    with pytest.raises(ValueError):
        AvailabilityCreate(
            court_id=uuid.uuid4(),
            weekday=7,
            start_time=time(9),
            end_time=time(10),
        )
    with pytest.raises(ValueError, match="end_time"):
        AvailabilityCreate(
            court_id=uuid.uuid4(),
            weekday=2,
            start_time=time(10),
            end_time=time(9),
        )


def test_availability_patch_rejects_invalid_time_range() -> None:
    repo = repository()
    service = CourtService(AsyncMock())
    service.repository = repo
    repo.get_availability.return_value = SimpleNamespace(
        id=uuid.uuid4(),
        court_id=uuid.uuid4(),
        weekday=2,
        start_time=time(9),
        end_time=time(10),
    )
    with pytest.raises(ValueError, match="end_time"):
        run(
            service.update_availability(
                uuid.uuid4(),
                AvailabilityPatch(start_time=time(11), end_time=time(10)),
            )
        )


def test_patch_schemas_reject_null_for_required_database_fields() -> None:
    with pytest.raises(ValueError, match="country"):
        VenuePatch(country=None)
    with pytest.raises(ValueError, match="Court fields"):
        CourtPatch(name=None)
    with pytest.raises(ValueError, match="Availability fields"):
        AvailabilityPatch(weekday=None)


def test_availability_model_has_duplicate_constraint_and_relationship() -> None:
    constraint_names = {
        constraint.name for constraint in Availability.__table__.constraints
    }
    assert "uq_availability_court_weekday_time" in constraint_names
    assert hasattr(Availability, "court")


def test_routes_apply_admin_write_and_authenticated_read_dependencies() -> None:
    protected_methods = {"POST", "PATCH", "DELETE"}
    read_methods = {"GET"}
    for route in router.routes:
        assert isinstance(route, APIRoute)
        dependency_calls = {
            dependency.call for dependency in route.dependant.dependencies
        }
        if route.methods & protected_methods:
            assert require_admin in dependency_calls
        if route.methods & read_methods:
            assert get_current_user in dependency_calls

    registered = {
        (method, route.path)
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    expected = {
        ("POST", "/venues"),
        ("GET", "/venues"),
        ("GET", "/venues/{venue_id}"),
        ("PATCH", "/venues/{venue_id}"),
        ("DELETE", "/venues/{venue_id}"),
        ("POST", "/courts"),
        ("GET", "/courts"),
        ("GET", "/courts/{court_id}"),
        ("PATCH", "/courts/{court_id}"),
        ("DELETE", "/courts/{court_id}"),
        ("POST", "/availability"),
        ("GET", "/availability/windows"),
        ("GET", "/availability/{availability_id}"),
        ("PATCH", "/availability/{availability_id}"),
        ("DELETE", "/availability/{availability_id}"),
    }
    assert expected <= registered


def test_domain_not_found_maps_to_404() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _raise_http_error(ResourceNotFoundError("Court not found."))
    assert exc_info.value.status_code == 404
