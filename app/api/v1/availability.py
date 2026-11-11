"""Public searchable endpoints for available court time slots."""

import uuid
from datetime import date, time

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.session import AsyncSession, get_db
from app.schemas.availability import (
    AvailabilitySearchResponse,
    AvailabilitySort,
)
from app.services.availability_service import AvailabilityService

router = APIRouter(tags=["Availability"])


def _raise_validation_error(error: ValueError) -> None:
    raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/availability", response_model=AvailabilitySearchResponse)
async def search_availability(
    venue_id: uuid.UUID | None = None,
    court_id: uuid.UUID | None = None,
    sport: str | None = Query(default=None, min_length=1, max_length=100),
    date_filter: date | None = Query(default=None, alias="date"),
    weekday: int | None = Query(default=None, ge=0, le=6),
    start_time: time | None = None,
    end_time: time | None = None,
    duration_minutes: int | None = Query(default=None, gt=0, le=1440),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: AvailabilitySort = "time",
    db: AsyncSession = Depends(get_db),
) -> AvailabilitySearchResponse:
    """Search public bookable slots across active courts and venues."""
    try:
        return await AvailabilityService(db).search_availability(
            venue_id=venue_id,
            court_id=court_id,
            sport=sport,
            slot_date=date_filter,
            weekday=weekday,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
        )
    except ValueError as exc:
        _raise_validation_error(exc)


@router.get(
    "/courts/{court_id}/availability", response_model=AvailabilitySearchResponse
)
async def get_court_availability(
    court_id: uuid.UUID,
    venue_id: uuid.UUID | None = None,
    sport: str | None = Query(default=None, min_length=1, max_length=100),
    date_filter: date | None = Query(default=None, alias="date"),
    weekday: int | None = Query(default=None, ge=0, le=6),
    start_time: time | None = None,
    end_time: time | None = None,
    duration_minutes: int | None = Query(default=None, gt=0, le=1440),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort_by: AvailabilitySort = "time",
    db: AsyncSession = Depends(get_db),
) -> AvailabilitySearchResponse:
    """Search bookable slots for one court."""
    try:
        return await AvailabilityService(db).court_availability(
            court_id,
            venue_id=venue_id,
            sport=sport,
            slot_date=date_filter,
            weekday=weekday,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
        )
    except ValueError as exc:
        _raise_validation_error(exc)
