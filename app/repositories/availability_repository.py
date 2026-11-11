"""Efficient SQL queries for public bookable-slot search."""

import uuid
from datetime import date, time
from typing import Any

from sqlalchemy import Date, Time, cast, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability import Availability
from app.models.booking import Booking
from app.models.court import Court
from app.models.enums import BookingStatus, SlotStatus
from app.models.sport import Sport
from app.models.time_slot import TimeSlot
from app.models.venue import Venue
from app.schemas.availability import AvailabilitySort


class AvailabilityRepository:
    """Build one joined query for availability rows, filters, and page counts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search_availability(
        self,
        *,
        page: int,
        page_size: int,
        sort_by: AvailabilitySort,
        venue_id: uuid.UUID | None = None,
        court_id: uuid.UUID | None = None,
        sport: str | None = None,
        slot_date: date | None = None,
        weekday: int | None = None,
        start_time: time | None = None,
        end_time: time | None = None,
        duration_minutes: int | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Search slots matching active court, venue, weekly window, and filters."""
        local_start = func.timezone(Venue.timezone, TimeSlot.start_time)
        local_end = func.timezone(Venue.timezone, TimeSlot.end_time)
        local_start_time = cast(local_start, Time)
        local_end_time = cast(local_end, Time)
        slot_weekday = extract("isodow", local_start) - 1

        matching_availability = select(Availability.id).where(
            Availability.court_id == Court.id,
            Availability.weekday == slot_weekday,
            Availability.available.is_(True),
            Availability.start_time <= local_start_time,
            Availability.end_time >= local_end_time,
        )
        conflicting_booking = select(Booking.id).where(
            Booking.time_slot_id == TimeSlot.id,
            Booking.status.in_(
                (
                    BookingStatus.HELD,
                    BookingStatus.CONFIRMED,
                    BookingStatus.COMPLETED,
                )
            ),
        )

        statement = (
            select(
                TimeSlot.id.label("slot_id"),
                Court.id.label("court_id"),
                Court.name.label("court_name"),
                Venue.id.label("venue_id"),
                Venue.name.label("venue_name"),
                Venue.timezone.label("timezone"),
                Sport.name.label("sport"),
                TimeSlot.start_time.label("starts_at"),
                TimeSlot.end_time.label("ends_at"),
                TimeSlot.status.label("status"),
                TimeSlot.price.label("price"),
            )
            .select_from(TimeSlot)
            .join(Court, Court.id == TimeSlot.court_id)
            .join(Venue, Venue.id == Court.venue_id)
            .join(Sport, Sport.id == Court.sport_id)
            .where(
                TimeSlot.status == SlotStatus.AVAILABLE,
                Court.is_active.is_(True),
                Venue.is_active.is_(True),
                Sport.is_active.is_(True),
                matching_availability.exists(),
                ~conflicting_booking.exists(),
            )
        )

        if venue_id is not None:
            statement = statement.where(Venue.id == venue_id)
        if court_id is not None:
            statement = statement.where(Court.id == court_id)
        if sport is not None:
            statement = statement.where(func.lower(Sport.name) == sport.strip().lower())
        if slot_date is not None:
            statement = statement.where(cast(local_start, Date) == slot_date)
        if weekday is not None:
            statement = statement.where(slot_weekday == weekday)
        if start_time is not None:
            statement = statement.where(local_start_time >= start_time)
        if end_time is not None:
            statement = statement.where(local_end_time <= end_time)
        if duration_minutes is not None:
            slot_duration_seconds = extract(
                "epoch", TimeSlot.end_time - TimeSlot.start_time
            )
            statement = statement.where(slot_duration_seconds == duration_minutes * 60)

        count_result = await self.session.execute(
            select(func.count()).select_from(statement.order_by(None).subquery())
        )
        total = int(count_result.scalar_one())
        result = await self.session.execute(
            statement.order_by(*self._sort_order(sort_by))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [dict(row) for row in result.mappings().all()], total

    async def court_availability(
        self,
        court_id: uuid.UUID,
        **filters: Any,
    ) -> tuple[list[dict[str, Any]], int]:
        """Search bookable slots for one court using the shared filter query."""
        return await self.search_availability(court_id=court_id, **filters)

    @staticmethod
    def _sort_order(sort_by: AvailabilitySort) -> tuple[Any, ...]:
        if sort_by == "venue":
            return Venue.name.asc(), TimeSlot.start_time.asc(), Court.name.asc()
        if sort_by == "court":
            return Court.name.asc(), TimeSlot.start_time.asc(), Venue.name.asc()
        return TimeSlot.start_time.asc(), Venue.name.asc(), Court.name.asc()
