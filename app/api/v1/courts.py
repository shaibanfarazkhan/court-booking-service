"""Public venue and court discovery and administrative creation endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import require_admin
from app.core.exceptions import UserNotFoundError
from app.db.session import AsyncSession, get_db
from app.models.enums import CourtType
from app.models.user import User
from app.schemas.courts import CourtCreate, CourtResponse, VenueCreate, VenueResponse
from app.services.court_service import CourtService

router = APIRouter(tags=["Courts and Venues"])


@router.get("/venues", response_model=list[VenueResponse])
async def list_venues(
    city: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[VenueResponse]:
    return await CourtService(db).list_venues(city, skip, limit)


@router.get("/venues/{venue_id}", response_model=VenueResponse)
async def get_venue(
    venue_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> VenueResponse:
    try:
        return await CourtService(db).get_venue(venue_id)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


@router.get("/courts", response_model=list[CourtResponse])
async def list_courts(
    venue_id: uuid.UUID | None = None,
    sport_id: uuid.UUID | None = None,
    court_type: CourtType | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[CourtResponse]:
    return await CourtService(db).list_courts(
        venue_id, sport_id, court_type, skip, limit
    )


@router.get("/courts/{court_id}", response_model=CourtResponse)
async def get_court(
    court_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> CourtResponse:
    try:
        return await CourtService(db).get_court(court_id)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


@router.post(
    "/admin/venues", response_model=VenueResponse, status_code=status.HTTP_201_CREATED
)
async def create_venue(
    payload: VenueCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> VenueResponse:
    return await CourtService(db).create_venue(payload)


@router.post(
    "/admin/courts", response_model=CourtResponse, status_code=status.HTTP_201_CREATED
)
async def create_court(
    payload: CourtCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> CourtResponse:
    try:
        return await CourtService(db).create_court(payload)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc
