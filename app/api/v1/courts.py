"""Authenticated court management endpoints."""

import uuid
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import get_current_user, require_admin
from app.core.exceptions import (
    DuplicateAvailabilityError,
    ResourceConflictError,
    ResourceNotFoundError,
)
from app.db.session import AsyncSession, get_db
from app.models.user import User
from app.schemas.courts import (
    AvailabilityCreate,
    AvailabilityPatch,
    AvailabilityResponse,
    CourtCreate,
    CourtPatch,
    CourtResponse,
    VenueCreate,
    VenuePatch,
    VenueResponse,
)
from app.services.court_service import CourtService

router = APIRouter(tags=["Court Management"])


def _raise_http_error(error: Exception) -> None:
    if isinstance(error, ResourceNotFoundError):
        raise HTTPException(status_code=404, detail=error.message) from error
    if isinstance(error, (DuplicateAvailabilityError, ResourceConflictError)):
        raise HTTPException(status_code=409, detail=error.message) from error
    if isinstance(error, ValueError):
        raise HTTPException(status_code=422, detail=str(error)) from error
    raise error


async def _raise_conflict(db: AsyncSession, detail: str, error: Exception) -> NoReturn:
    """Roll back a failed flush before returning a conflict response."""
    await db.rollback()
    raise HTTPException(status_code=409, detail=detail) from error


@router.post(
    "/venues", response_model=VenueResponse, status_code=status.HTTP_201_CREATED
)
async def create_venue(
    payload: VenueCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> VenueResponse:
    try:
        return await CourtService(db).create_venue(payload)
    except (IntegrityError, ResourceConflictError) as exc:
        await _raise_conflict(db, "Venue conflicts with an existing record.", exc)


@router.get("/venues", response_model=list[VenueResponse])
async def list_venues(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[VenueResponse]:
    return await CourtService(db).list_venues(skip, limit)


@router.get("/venues/{venue_id}", response_model=VenueResponse)
async def get_venue(
    venue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> VenueResponse:
    try:
        return await CourtService(db).get_venue(venue_id)
    except ResourceNotFoundError as exc:
        _raise_http_error(exc)


@router.patch("/venues/{venue_id}", response_model=VenueResponse)
async def update_venue(
    venue_id: uuid.UUID,
    payload: VenuePatch,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> VenueResponse:
    try:
        return await CourtService(db).update_venue(venue_id, payload)
    except (ResourceNotFoundError, ValueError) as exc:
        _raise_http_error(exc)
    except IntegrityError as exc:
        await _raise_conflict(db, "Venue conflicts with an existing record.", exc)


@router.delete("/venues/{venue_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_venue(
    venue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> Response:
    try:
        await CourtService(db).delete_venue(venue_id)
    except ResourceNotFoundError as exc:
        _raise_http_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/courts", response_model=CourtResponse, status_code=status.HTTP_201_CREATED
)
async def create_court(
    payload: CourtCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> CourtResponse:
    try:
        return await CourtService(db).create_court(payload)
    except ResourceNotFoundError as exc:
        _raise_http_error(exc)
    except IntegrityError as exc:
        await _raise_conflict(db, "Court conflicts with an existing record.", exc)


@router.get("/courts", response_model=list[CourtResponse])
async def list_courts(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    venue_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[CourtResponse]:
    return await CourtService(db).list_courts(skip, limit, venue_id)


@router.get("/courts/{court_id}", response_model=CourtResponse)
async def get_court(
    court_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> CourtResponse:
    try:
        return await CourtService(db).get_court(court_id)
    except ResourceNotFoundError as exc:
        _raise_http_error(exc)


@router.patch("/courts/{court_id}", response_model=CourtResponse)
async def update_court(
    court_id: uuid.UUID,
    payload: CourtPatch,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> CourtResponse:
    try:
        return await CourtService(db).update_court(court_id, payload)
    except ResourceNotFoundError as exc:
        _raise_http_error(exc)
    except IntegrityError as exc:
        await _raise_conflict(db, "Court conflicts with an existing record.", exc)


@router.delete("/courts/{court_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_court(
    court_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> Response:
    try:
        await CourtService(db).delete_court(court_id)
    except ResourceNotFoundError as exc:
        _raise_http_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/availability",
    response_model=AvailabilityResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_availability(
    payload: AvailabilityCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AvailabilityResponse:
    try:
        return await CourtService(db).create_availability(payload)
    except (ResourceNotFoundError, DuplicateAvailabilityError) as exc:
        _raise_http_error(exc)
    except IntegrityError as exc:
        await _raise_conflict(db, "Availability window already exists.", exc)


@router.get("/availability/windows", response_model=list[AvailabilityResponse])
async def list_availability(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    court_id: uuid.UUID | None = None,
    weekday: int | None = Query(default=None, ge=0, le=6),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[AvailabilityResponse]:
    return await CourtService(db).list_availability(skip, limit, court_id, weekday)


@router.get("/availability/{availability_id}", response_model=AvailabilityResponse)
async def get_availability(
    availability_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> AvailabilityResponse:
    try:
        return await CourtService(db).get_availability(availability_id)
    except ResourceNotFoundError as exc:
        _raise_http_error(exc)


@router.patch("/availability/{availability_id}", response_model=AvailabilityResponse)
async def update_availability(
    availability_id: uuid.UUID,
    payload: AvailabilityPatch,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AvailabilityResponse:
    try:
        return await CourtService(db).update_availability(availability_id, payload)
    except (ResourceNotFoundError, DuplicateAvailabilityError, ValueError) as exc:
        _raise_http_error(exc)
    except IntegrityError as exc:
        await _raise_conflict(db, "Availability window already exists.", exc)


@router.delete(
    "/availability/{availability_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_availability(
    availability_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> Response:
    try:
        await CourtService(db).delete_availability(availability_id)
    except ResourceNotFoundError as exc:
        _raise_http_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
