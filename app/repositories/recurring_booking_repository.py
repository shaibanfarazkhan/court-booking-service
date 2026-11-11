"""Persistence operations for recurring booking generation."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccountInactiveError, ResourceNotFoundError
from app.models.availability import Availability
from app.models.booking import Booking
from app.models.court import Court
from app.models.enums import BookingStatus, SlotStatus
from app.models.recurring_booking_request import RecurringBookingRequest
from app.models.time_slot import TimeSlot
from app.models.user import User


class RecurringBookingRepository:
    """Lock inventory and persist recurring bookings in one session transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_active_user(self, user_id: uuid.UUID) -> None:
        """Serialize requests by member and recheck the account's active state."""
        result = await self.session.execute(
            select(User).where(User.id == user_id).with_for_update()
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise ResourceNotFoundError("User not found.")
        if not user.is_active:
            raise AccountInactiveError("Inactive users cannot create bookings.")

    async def get_idempotent_request(
        self, user_id: uuid.UUID, idempotency_key: str
    ) -> RecurringBookingRequest | None:
        result = await self.session.execute(
            select(RecurringBookingRequest).where(
                RecurringBookingRequest.user_id == user_id,
                RecurringBookingRequest.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def lock_active_court(self, court_id: uuid.UUID) -> None:
        """Serialize recurring requests for the court and reject inactive courts."""
        result = await self.session.execute(
            select(Court)
            .where(Court.id == court_id, Court.is_active.is_(True))
            .with_for_update()
        )
        if result.scalar_one_or_none() is None:
            raise ResourceNotFoundError("Active court not found.")

    async def get_availability(
        self, court_id: uuid.UUID, weekdays: set[int]
    ) -> list[Availability]:
        result = await self.session.execute(
            select(Availability).where(
                Availability.court_id == court_id,
                Availability.weekday.in_(weekdays),
            )
        )
        return list(result.scalars().all())

    async def lock_occurrence_slots(
        self, court_id: uuid.UUID, start_times: list[datetime]
    ) -> list[TimeSlot]:
        result = await self.session.execute(
            select(TimeSlot)
            .where(
                TimeSlot.court_id == court_id,
                TimeSlot.start_time.in_(start_times),
            )
            .order_by(TimeSlot.start_time, TimeSlot.id)
            .with_for_update()
        )
        return list(result.scalars().all())

    async def get_conflicting_slot_ids(
        self, slot_ids: set[uuid.UUID]
    ) -> set[uuid.UUID]:
        if not slot_ids:
            return set()
        result = await self.session.execute(
            select(Booking.time_slot_id).where(
                Booking.time_slot_id.in_(slot_ids),
                Booking.status.in_(
                    (
                        BookingStatus.HELD,
                        BookingStatus.CONFIRMED,
                        BookingStatus.COMPLETED,
                    )
                ),
            )
        )
        return set(result.scalars().all())

    async def persist_generated_bookings(
        self,
        bookings: list[Booking],
        idempotent_request: RecurringBookingRequest | None,
    ) -> None:
        """Flush a batch of bookings and its idempotency receipt atomically."""
        self.session.add_all(bookings)
        await self.session.flush()
        if idempotent_request is not None:
            self.session.add(idempotent_request)
            await self.session.flush()

    async def get_bookings_for_group(
        self, recurring_group_id: uuid.UUID
    ) -> list[Booking]:
        result = await self.session.execute(
            select(Booking)
            .where(Booking.recurring_group_id == recurring_group_id)
            .order_by(Booking.created_at, Booking.id)
        )
        return list(result.scalars().all())

    @staticmethod
    def create_booking(
        *,
        user_id: uuid.UUID,
        court_id: uuid.UUID,
        slot: TimeSlot,
        group_id: uuid.UUID,
        now: datetime,
    ) -> Booking:
        """Build a confirmed booking for an already-locked available slot."""
        slot.status = SlotStatus.BOOKED
        slot.hold_expires_at = None
        return Booking(
            booking_reference=uuid.uuid4().hex[:20].upper(),
            user_id=user_id,
            court_id=court_id,
            time_slot_id=slot.id,
            status=BookingStatus.CONFIRMED,
            total_amount=slot.price,
            confirmed_at=now,
            is_recurring=True,
            recurring_group_id=group_id,
        )

    @staticmethod
    def serialize_skips(
        skipped: list[tuple[date, str]],
    ) -> list[dict[str, Any]]:
        return [
            {"date": skipped_date.isoformat(), "reason": reason}
            for skipped_date, reason in skipped
        ]
