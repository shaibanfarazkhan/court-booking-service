"""Database aggregations used by backend reports."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import Date, and_, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.court import Court
from app.models.enums import BookingStatus, SlotStatus
from app.models.sport import Sport
from app.models.time_slot import TimeSlot
from app.models.venue import Venue


class ReportRepository:
    """Perform report counts and sums in SQL instead of loading ORM collections."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_court_daily_aggregates(
        self, start_date: date, end_date: date
    ) -> list[Any]:
        """Return per-court, per-day slot and lifecycle totals in one query."""
        start = datetime.combine(start_date, time.min, tzinfo=UTC)
        end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC)
        booking_counts = (
            select(
                Booking.time_slot_id.label("time_slot_id"),
                func.count(
                    case((Booking.status == BookingStatus.CONFIRMED, Booking.id))
                ).label("confirmed_bookings"),
                func.count(
                    case((Booking.status == BookingStatus.CANCELLED, Booking.id))
                ).label("cancelled_bookings"),
            )
            .group_by(Booking.time_slot_id)
            .subquery()
        )
        stmt = (
            select(
                Court.id.label("court_id"),
                Court.name.label("court_name"),
                Venue.name.label("venue_name"),
                Sport.name.label("sport"),
                cast(TimeSlot.start_time, Date).label("report_date"),
                func.count(TimeSlot.id).label("total_slots"),
                func.count(
                    case((TimeSlot.status == SlotStatus.BOOKED, TimeSlot.id))
                ).label("booked_slots"),
                func.count(
                    case((TimeSlot.status == SlotStatus.AVAILABLE, TimeSlot.id))
                ).label("available_slots"),
                func.coalesce(func.sum(booking_counts.c.cancelled_bookings), 0).label(
                    "cancelled_bookings"
                ),
                func.coalesce(func.sum(booking_counts.c.confirmed_bookings), 0).label(
                    "confirmed_bookings"
                ),
            )
            .select_from(Court)
            .join(Venue, Venue.id == Court.venue_id)
            .join(Sport, Sport.id == Court.sport_id)
            .outerjoin(
                TimeSlot,
                and_(
                    TimeSlot.court_id == Court.id,
                    TimeSlot.start_time >= start,
                    TimeSlot.start_time < end,
                ),
            )
            .outerjoin(booking_counts, booking_counts.c.time_slot_id == TimeSlot.id)
            .where(Court.is_active.is_(True))
            .group_by(
                Court.id,
                Court.name,
                Venue.name,
                Sport.name,
                cast(TimeSlot.start_time, Date),
            )
            .order_by(Court.name, cast(TimeSlot.start_time, Date))
        )
        result = await self.session.execute(stmt)
        return list(result.mappings().all())

    async def get_priced_booked_slots(
        self, start_date: date, end_date: date
    ) -> list[Any]:
        """Return booked time groups and counts for pricing through PricingService."""
        start = datetime.combine(start_date, time.min, tzinfo=UTC)
        end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC)
        stmt = (
            select(
                Court.id.label("court_id"),
                cast(TimeSlot.start_time, Date).label("booking_date"),
                func.min(TimeSlot.start_time).label("start_time"),
                func.max(TimeSlot.end_time).label("end_time"),
                func.count(TimeSlot.id).label("slot_count"),
            )
            .join(TimeSlot, TimeSlot.court_id == Court.id)
            .where(
                Court.is_active.is_(True),
                TimeSlot.status == SlotStatus.BOOKED,
                TimeSlot.start_time >= start,
                TimeSlot.start_time < end,
            )
            .group_by(
                Court.id,
                cast(TimeSlot.start_time, Date),
                TimeSlot.start_time,
                TimeSlot.end_time,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.mappings().all())
