"""Persistence operations for venues, courts, and availability windows."""

import uuid
from datetime import time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.availability import Availability
from app.models.court import Court
from app.models.enums import CourtType
from app.models.sport import Sport
from app.models.venue import Venue


class CourtRepository:
    """Async repository for the Phase 5 court management entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_venues(self, skip: int, limit: int) -> list[Venue]:
        result = await self.session.execute(
            select(Venue)
            .where(Venue.is_active.is_(True))
            .order_by(Venue.name)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_venue(self, venue_id: uuid.UUID) -> Venue | None:
        result = await self.session.execute(
            select(Venue).where(Venue.id == venue_id, Venue.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def create_venue(self, values: dict[str, object]) -> Venue:
        venue = Venue(**values)
        self.session.add(venue)
        await self.session.flush()
        await self.session.refresh(venue)
        return venue

    async def list_courts(
        self, skip: int, limit: int, venue_id: uuid.UUID | None = None
    ) -> list[Court]:
        stmt = (
            select(Court)
            .options(selectinload(Court.sport))
            .join(Venue)
            .where(Venue.is_active.is_(True))
            .where(Court.is_active.is_(True))
            .order_by(Court.name)
        )
        if venue_id is not None:
            stmt = stmt.where(Court.venue_id == venue_id)
        result = await self.session.execute(stmt.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def get_court(self, court_id: uuid.UUID) -> Court | None:
        result = await self.session.execute(
            select(Court)
            .options(selectinload(Court.sport), selectinload(Court.availability))
            .join(Venue)
            .where(Venue.is_active.is_(True))
            .where(Court.id == court_id, Court.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def create_court(self, values: dict[str, object], sport: Sport) -> Court:
        indoor = bool(values.pop("indoor"))
        values.pop("sport_type", None)
        values["sport_id"] = sport.id
        values["court_type"] = CourtType.INDOOR if indoor else CourtType.OUTDOOR
        values["is_active"] = values.pop("active", True)
        court = Court(**values)
        self.session.add(court)
        await self.session.flush()
        await self.session.refresh(court)
        court.sport = sport
        return court

    async def get_active_sport(self, sport_type: str) -> Sport | None:
        result = await self.session.execute(
            select(Sport).where(
                func.lower(Sport.name) == sport_type.strip().lower(),
                Sport.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def update_venue(self, venue: Venue, values: dict[str, object]) -> Venue:
        for key, value in values.items():
            setattr(venue, key, value)
        await self.session.flush()
        await self.session.refresh(venue)
        return venue

    async def delete_venue(self, venue: Venue) -> None:
        venue.is_active = False
        await self.session.flush()

    async def update_court(
        self, court: Court, values: dict[str, object], sport: Sport | None = None
    ) -> Court:
        sport_type = values.pop("sport_type", None)
        if sport_type is not None:
            assert sport is not None
            court.sport_id = sport.id
            court.sport = sport
        if "indoor" in values:
            court.indoor = bool(values.pop("indoor"))
        if "active" in values:
            court.is_active = bool(values.pop("active"))
        for key, value in values.items():
            setattr(court, key, value)
        await self.session.flush()
        await self.session.refresh(court)
        return court

    async def delete_court(self, court: Court) -> None:
        court.is_active = False
        await self.session.flush()

    async def list_availability(
        self,
        skip: int,
        limit: int,
        court_id: uuid.UUID | None = None,
        weekday: int | None = None,
    ) -> list[Availability]:
        stmt = select(Availability).order_by(
            Availability.court_id, Availability.weekday, Availability.start_time
        )
        if court_id is not None:
            stmt = stmt.where(Availability.court_id == court_id)
        if weekday is not None:
            stmt = stmt.where(Availability.weekday == weekday)
        result = await self.session.execute(stmt.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def get_availability(self, availability_id: uuid.UUID) -> Availability | None:
        result = await self.session.execute(
            select(Availability).where(Availability.id == availability_id)
        )
        return result.scalar_one_or_none()

    async def court_exists(self, court_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            select(Court.id).where(Court.id == court_id, Court.is_active.is_(True))
        )
        return result.scalar_one_or_none() is not None

    async def availability_exists(
        self,
        court_id: uuid.UUID,
        weekday: int,
        start_time: time,
        end_time: time,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        stmt = select(Availability.id).where(
            Availability.court_id == court_id,
            Availability.weekday == weekday,
            Availability.start_time == start_time,
            Availability.end_time == end_time,
        )
        if exclude_id is not None:
            stmt = stmt.where(Availability.id != exclude_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create_availability(self, values: dict[str, object]) -> Availability:
        availability = Availability(**values)
        self.session.add(availability)
        await self.session.flush()
        await self.session.refresh(availability)
        return availability

    async def update_availability(
        self, availability: Availability, values: dict[str, object]
    ) -> Availability:
        for key, value in values.items():
            setattr(availability, key, value)
        await self.session.flush()
        await self.session.refresh(availability)
        return availability

    async def delete_availability(self, availability: Availability) -> None:
        await self.session.delete(availability)
        await self.session.flush()
