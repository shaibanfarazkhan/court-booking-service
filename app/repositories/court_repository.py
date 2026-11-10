"""Persistence operations for venues and courts."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSession
from app.models.court import Court
from app.models.sport import Sport
from app.models.venue import Venue


class CourtRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_venues(self, city: str | None, skip: int, limit: int) -> list[Venue]:
        stmt = select(Venue).where(Venue.is_active.is_(True)).order_by(Venue.name)
        if city:
            stmt = stmt.where(Venue.city.ilike(city.strip()))
        result = await self.session.execute(stmt.offset(skip).limit(limit))
        return list(result.scalars().all())

    async def get_venue(self, venue_id: uuid.UUID) -> Venue | None:
        stmt = (
            select(Venue)
            .options(selectinload(Venue.courts).selectinload(Court.images))
            .where(Venue.id == venue_id, Venue.is_active.is_(True))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_venue(self, **values: object) -> Venue:
        venue = Venue(**values)
        self.session.add(venue)
        await self.session.flush()
        await self.session.refresh(venue)
        return venue

    async def get_court(self, court_id: uuid.UUID) -> Court | None:
        stmt = (
            select(Court)
            .options(selectinload(Court.images))
            .where(Court.id == court_id, Court.is_active.is_(True))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_courts(
        self,
        venue_id: uuid.UUID | None,
        sport_id: uuid.UUID | None,
        court_type: str | None,
        skip: int,
        limit: int,
    ) -> list[Court]:
        stmt = (
            select(Court)
            .options(selectinload(Court.images))
            .where(Court.is_active.is_(True))
        )
        if venue_id:
            stmt = stmt.where(Court.venue_id == venue_id)
        if sport_id:
            stmt = stmt.where(Court.sport_id == sport_id)
        if court_type:
            stmt = stmt.where(Court.court_type == court_type)
        result = await self.session.execute(
            stmt.order_by(Court.name).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def create_court(self, **values: object) -> Court:
        court = Court(**values)
        self.session.add(court)
        await self.session.flush()
        await self.session.refresh(court)
        return court

    async def active_venue_exists(self, venue_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            select(Venue.id).where(Venue.id == venue_id, Venue.is_active.is_(True))
        )
        return result.scalar_one_or_none() is not None

    async def active_sport_exists(self, sport_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            select(Sport.id).where(Sport.id == sport_id, Sport.is_active.is_(True))
        )
        return result.scalar_one_or_none() is not None
