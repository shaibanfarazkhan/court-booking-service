"""Business operations for venue discovery and court management."""

import uuid

from app.core.exceptions import UserNotFoundError
from app.db.session import AsyncSession
from app.repositories.court_repository import CourtRepository
from app.schemas.courts import CourtCreate, VenueCreate


class CourtService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = CourtRepository(session)

    async def list_venues(self, city: str | None, skip: int, limit: int):
        return await self.repository.list_venues(city, skip, limit)

    async def get_venue(self, venue_id: uuid.UUID):
        venue = await self.repository.get_venue(venue_id)
        if venue is None:
            raise UserNotFoundError("Venue not found.")
        return venue

    async def create_venue(self, payload: VenueCreate):
        return await self.repository.create_venue(**payload.model_dump())

    async def list_courts(self, venue_id, sport_id, court_type, skip: int, limit: int):
        return await self.repository.list_courts(
            venue_id, sport_id, court_type, skip, limit
        )

    async def get_court(self, court_id: uuid.UUID):
        court = await self.repository.get_court(court_id)
        if court is None:
            raise UserNotFoundError("Court not found.")
        return court

    async def create_court(self, payload: CourtCreate):
        if not await self.repository.active_venue_exists(payload.venue_id):
            raise UserNotFoundError("Active venue not found.")
        if not await self.repository.active_sport_exists(payload.sport_id):
            raise UserNotFoundError("Active sport not found.")
        return await self.repository.create_court(**payload.model_dump())
