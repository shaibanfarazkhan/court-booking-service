"""Booking policy administration and validation orchestration."""

import uuid
from datetime import datetime, timedelta

from app.core.exceptions import BookingPolicyError, ResourceNotFoundError
from app.db.session import AsyncSession
from app.models.booking_policy import BookingPolicy
from app.repositories.booking_policy_repository import BookingPolicyRepository
from app.schemas.booking_policy import BookingPolicyInput


class BookingPolicyService:
    """Validate member limits and expose staff policy configuration operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = BookingPolicyRepository(session)

    async def get_policy(self) -> BookingPolicy:
        policy = await self.repository.get_active_policy()
        if policy is None:
            raise ResourceNotFoundError("No active booking policy is configured.")
        return policy

    async def update_policy(self, payload: BookingPolicyInput) -> BookingPolicy:
        return await self.repository.save_policy(payload.model_dump())

    async def validate_booking(
        self, user_id: uuid.UUID, start: datetime, end: datetime, now: datetime
    ) -> None:
        policy = await self.repository.get_active_policy()
        if policy is None:
            raise ResourceNotFoundError("No active booking policy is configured.")
        duration = (end - start).total_seconds() / 60
        if duration < policy.min_duration_minutes:
            raise BookingPolicyError("Booking duration is below the minimum allowed.")
        if duration > policy.max_duration_minutes:
            raise BookingPolicyError("Booking duration exceeds the maximum allowed.")
        if await self.repository.has_overlap(user_id, start, end, now):
            raise BookingPolicyError("Booking overlaps another active booking.")
        day_start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = day_start - timedelta(days=day_start.weekday())
        day_end = day_start + timedelta(days=1)
        week_end = week_start + timedelta(days=7)
        daily = await self.repository.count_daily_bookings(
            user_id, day_start, day_end, now
        )
        weekly = await self.repository.count_weekly_bookings(
            user_id, week_start, week_end, now
        )
        future = await self.repository.count_future_bookings(user_id, now)
        if daily >= policy.daily_limit:
            raise BookingPolicyError("Daily booking limit exceeded.")
        if weekly >= policy.weekly_limit:
            raise BookingPolicyError("Weekly booking limit exceeded.")
        if future >= policy.future_booking_limit:
            raise BookingPolicyError("Future active booking limit exceeded.")
