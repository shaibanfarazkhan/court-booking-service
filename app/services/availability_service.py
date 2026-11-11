"""Public availability search rules and DTO mapping."""

import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from app.db.session import AsyncSession
from app.models.enums import SlotStatus
from app.repositories.availability_repository import AvailabilityRepository
from app.schemas.availability import (
    AvailabilitySearchResponse,
    AvailabilitySlotResponse,
    AvailabilitySort,
)


class AvailabilityService:
    """Validate search filters and map repository rows to public responses."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = AvailabilityRepository(session)

    async def search_availability(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        sort_by: AvailabilitySort = "time",
        venue_id: uuid.UUID | None = None,
        court_id: uuid.UUID | None = None,
        sport: str | None = None,
        slot_date: date | None = None,
        weekday: int | None = None,
        start_time: time | None = None,
        end_time: time | None = None,
        duration_minutes: int | None = None,
    ) -> AvailabilitySearchResponse:
        """Return only slots that pass all inventory and weekly availability rules."""
        self._validate_filters(
            page,
            page_size,
            weekday,
            start_time,
            end_time,
            duration_minutes,
            sort_by,
        )
        rows, total = await self.repository.search_availability(
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            venue_id=venue_id,
            court_id=court_id,
            sport=sport,
            slot_date=slot_date,
            weekday=weekday,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration_minutes,
        )
        return AvailabilitySearchResponse(
            items=[self._map_slot(row) for row in rows],
            page=page,
            page_size=page_size,
            total=total,
        )

    async def court_availability(
        self,
        court_id: uuid.UUID,
        **filters: Any,
    ) -> AvailabilitySearchResponse:
        """Return availability for one court using the same filtering rules."""
        page = filters.get("page", 1)
        page_size = filters.get("page_size", 20)
        sort_by = filters.get("sort_by", "time")
        self._validate_filters(
            page,
            page_size,
            filters.get("weekday"),
            filters.get("start_time"),
            filters.get("end_time"),
            filters.get("duration_minutes"),
            sort_by,
        )
        rows, total = await self.repository.court_availability(
            court_id,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            venue_id=filters.get("venue_id"),
            sport=filters.get("sport"),
            slot_date=filters.get("slot_date"),
            weekday=filters.get("weekday"),
            start_time=filters.get("start_time"),
            end_time=filters.get("end_time"),
            duration_minutes=filters.get("duration_minutes"),
        )
        return AvailabilitySearchResponse(
            items=[self._map_slot(row) for row in rows],
            page=page,
            page_size=page_size,
            total=total,
        )

    @staticmethod
    def _validate_filters(
        page: int,
        page_size: int,
        weekday: int | None,
        start_time: time | None,
        end_time: time | None,
        duration_minutes: int | None,
        sort_by: AvailabilitySort,
    ) -> None:
        if page < 1:
            raise ValueError("page must be at least 1")
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        if weekday is not None and not 0 <= weekday <= 6:
            raise ValueError("weekday must be between 0 and 6")
        if start_time is not None and end_time is not None and start_time >= end_time:
            raise ValueError("start_time must be before end_time")
        if duration_minutes is not None and not 1 <= duration_minutes <= 1440:
            raise ValueError("duration_minutes must be between 1 and 1440")
        if sort_by not in ("time", "venue", "court"):
            raise ValueError("sort_by must be time, venue, or court")

    @staticmethod
    def _map_slot(row: dict[str, Any]) -> AvailabilitySlotResponse:
        starts_at: datetime = row["starts_at"]
        ends_at: datetime = row["ends_at"]
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=ZoneInfo("UTC"))
        if ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=ZoneInfo("UTC"))
        venue_timezone = ZoneInfo(row["timezone"])
        starts_at = starts_at.astimezone(venue_timezone)
        ends_at = ends_at.astimezone(venue_timezone)
        return AvailabilitySlotResponse(
            slot_id=row["slot_id"],
            court_id=row["court_id"],
            court_name=row["court_name"],
            venue_id=row["venue_id"],
            venue_name=row["venue_name"],
            sport=row["sport"],
            date=starts_at.date(),
            weekday=starts_at.weekday(),
            start_time=starts_at.time().replace(tzinfo=None),
            end_time=ends_at.time().replace(tzinfo=None),
            status=SlotStatus(row["status"]),
            price=Decimal(row["price"]),
            available=True,
        )
