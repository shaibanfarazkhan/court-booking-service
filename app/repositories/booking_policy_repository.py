"""Persistence for booking policies and member booking-limit queries."""

import uuid
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.booking_policy import BookingPolicy
from app.models.enums import BookingStatus
from app.models.time_slot import TimeSlot


class BookingPolicyRepository:
    """Load and update policy state and count active bookings in set queries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active_policy(self) -> BookingPolicy | None:
        result = await self.session.execute(
            select(BookingPolicy).where(BookingPolicy.active.is_(True)).limit(1)
        )
        return result.scalar_one_or_none()

    async def save_policy(self, values: dict[str, int]) -> BookingPolicy:
        policy = await self.get_active_policy()
        if policy is None:
            policy = BookingPolicy(**values, active=True)
            self.session.add(policy)
        else:
            for name, value in values.items():
                setattr(policy, name, value)
        await self.session.flush()
        await self.session.refresh(policy)
        return policy

    def _active_booking_query(self, user_id: uuid.UUID, now: datetime):
        return (
            select(func.count(Booking.id))
            .join(TimeSlot, TimeSlot.id == Booking.time_slot_id)
            .where(
                Booking.user_id == user_id,
                TimeSlot.start_time > now,
                or_(
                    Booking.status == BookingStatus.CONFIRMED,
                    and_(
                        Booking.status == BookingStatus.HELD,
                        Booking.hold_expires_at > now,
                    ),
                ),
            )
        )

    async def count_future_bookings(self, user_id: uuid.UUID, now: datetime) -> int:
        result = await self.session.execute(self._active_booking_query(user_id, now))
        return int(result.scalar_one())

    async def count_daily_bookings(
        self, user_id: uuid.UUID, start: datetime, end: datetime, now: datetime
    ) -> int:
        result = await self.session.execute(
            self._active_booking_query(user_id, now).where(
                TimeSlot.start_time >= start, TimeSlot.start_time < end
            )
        )
        return int(result.scalar_one())

    async def count_weekly_bookings(
        self, user_id: uuid.UUID, start: datetime, end: datetime, now: datetime
    ) -> int:
        result = await self.session.execute(
            self._active_booking_query(user_id, now).where(
                TimeSlot.start_time >= start, TimeSlot.start_time < end
            )
        )
        return int(result.scalar_one())

    async def has_overlap(
        self, user_id: uuid.UUID, start: datetime, end: datetime, now: datetime
    ) -> bool:
        result = await self.session.execute(
            select(Booking.id)
            .join(TimeSlot, TimeSlot.id == Booking.time_slot_id)
            .where(
                Booking.user_id == user_id,
                TimeSlot.start_time < end,
                TimeSlot.end_time > start,
                or_(
                    Booking.status == BookingStatus.CONFIRMED,
                    and_(
                        Booking.status == BookingStatus.HELD,
                        Booking.hold_expires_at > now,
                    ),
                ),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None
