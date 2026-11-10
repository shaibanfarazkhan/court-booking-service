"""Business operations for venue, court, and availability management."""

import re
import uuid
from typing import Any

from app.core.exceptions import (
    DuplicateAvailabilityError,
    ResourceNotFoundError,
)
from app.db.session import AsyncSession
from app.models.availability import Availability
from app.models.court import Court
from app.models.venue import Venue
from app.repositories.court_repository import CourtRepository
from app.schemas.courts import (
    AvailabilityCreate,
    AvailabilityPatch,
    CourtCreate,
    CourtPatch,
    VenueCreate,
    VenuePatch,
)


class CourtService:
    """Coordinate validation and persistence for court management."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = CourtRepository(session)

    async def list_venues(self, skip: int, limit: int) -> list[Venue]:
        return await self.repository.list_venues(skip, limit)

    async def get_venue(self, venue_id: uuid.UUID) -> Venue:
        venue = await self.repository.get_venue(venue_id)
        if venue is None:
            raise ResourceNotFoundError("Venue not found.")
        return venue

    async def create_venue(self, payload: VenueCreate) -> Venue:
        values: dict[str, Any] = payload.model_dump()
        values["slug"] = values["slug"] or self._slugify(payload.name)
        return await self.repository.create_venue(values)

    async def update_venue(self, venue_id: uuid.UUID, payload: VenuePatch) -> Venue:
        venue = await self.get_venue(venue_id)
        values = payload.model_dump(exclude_unset=True)
        opening_time = values.get("opening_time", venue.opening_time)
        closing_time = values.get("closing_time", venue.closing_time)
        if closing_time <= opening_time:
            raise ValueError("closing_time must be after opening_time")
        if "name" in values and "slug" not in values:
            values["slug"] = self._slugify(str(values["name"]))
        return await self.repository.update_venue(venue, values)

    async def delete_venue(self, venue_id: uuid.UUID) -> None:
        venue = await self.get_venue(venue_id)
        await self.repository.delete_venue(venue)

    async def list_courts(
        self, skip: int, limit: int, venue_id: uuid.UUID | None = None
    ) -> list[Court]:
        return await self.repository.list_courts(skip, limit, venue_id)

    async def get_court(self, court_id: uuid.UUID) -> Court:
        court = await self.repository.get_court(court_id)
        if court is None:
            raise ResourceNotFoundError("Court not found.")
        return court

    async def create_court(self, payload: CourtCreate) -> Court:
        if await self.repository.get_venue(payload.venue_id) is None:
            raise ResourceNotFoundError("Active venue not found.")
        sport = await self.repository.get_active_sport(payload.sport_type)
        if sport is None:
            raise ResourceNotFoundError("Active sport not found.")
        return await self.repository.create_court(payload.model_dump(), sport)

    async def update_court(self, court_id: uuid.UUID, payload: CourtPatch) -> Court:
        court = await self.get_court(court_id)
        values = payload.model_dump(exclude_unset=True)
        if "venue_id" in values:
            if await self.repository.get_venue(values["venue_id"]) is None:
                raise ResourceNotFoundError("Active venue not found.")
        if "sport_type" in values:
            sport = await self.repository.get_active_sport(str(values["sport_type"]))
            if sport is None:
                raise ResourceNotFoundError("Active sport not found.")
        else:
            sport = None
        return await self.repository.update_court(court, values, sport)

    async def delete_court(self, court_id: uuid.UUID) -> None:
        court = await self.get_court(court_id)
        await self.repository.delete_court(court)

    async def list_availability(
        self,
        skip: int,
        limit: int,
        court_id: uuid.UUID | None = None,
        weekday: int | None = None,
    ) -> list[Availability]:
        return await self.repository.list_availability(skip, limit, court_id, weekday)

    async def get_availability(self, availability_id: uuid.UUID) -> Availability:
        availability = await self.repository.get_availability(availability_id)
        if availability is None:
            raise ResourceNotFoundError("Availability not found.")
        return availability

    async def create_availability(self, payload: AvailabilityCreate) -> Availability:
        if not await self.repository.court_exists(payload.court_id):
            raise ResourceNotFoundError("Active court not found.")
        if await self.repository.availability_exists(
            payload.court_id,
            payload.weekday,
            payload.start_time,
            payload.end_time,
        ):
            raise DuplicateAvailabilityError("Availability window already exists.")
        return await self.repository.create_availability(payload.model_dump())

    async def update_availability(
        self, availability_id: uuid.UUID, payload: AvailabilityPatch
    ) -> Availability:
        availability = await self.get_availability(availability_id)
        values = payload.model_dump(exclude_unset=True)
        court_id = values.get("court_id", availability.court_id)
        weekday = values.get("weekday", availability.weekday)
        start_time = values.get("start_time", availability.start_time)
        end_time = values.get("end_time", availability.end_time)
        if end_time <= start_time:
            raise ValueError("end_time must be after start_time")
        if not await self.repository.court_exists(court_id):
            raise ResourceNotFoundError("Active court not found.")
        if await self.repository.availability_exists(
            court_id,
            weekday,
            start_time,
            end_time,
            exclude_id=availability.id,
        ):
            raise DuplicateAvailabilityError("Availability window already exists.")
        return await self.repository.update_availability(availability, values)

    async def delete_availability(self, availability_id: uuid.UUID) -> None:
        availability = await self.get_availability(availability_id)
        await self.repository.delete_availability(availability)

    @staticmethod
    def _slugify(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug[:160] or "venue"
