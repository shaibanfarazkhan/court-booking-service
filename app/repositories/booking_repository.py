"""Async persistence operations for booking holds and lifecycle transitions."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BookingHoldExpiredError,
    BookingNotFoundError,
    BookingStateError,
    DuplicateActiveHoldError,
    ResourceNotFoundError,
    SlotUnavailableError,
)
from app.models.booking import Booking
from app.models.enums import BookingStatus, SlotStatus
from app.models.time_slot import TimeSlot


class BookingRepository:
    """Repository responsible for transactional booking persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_hold(
        self,
        user_id: uuid.UUID,
        time_slot_id: uuid.UUID,
        booking_reference: str,
        now: datetime,
        hold_expires_at: datetime,
    ) -> Booking:
        """Lock a slot, expire stale holds, and create a new hold atomically."""
        slot = await self._lock_slot(time_slot_id)
        if slot is None:
            raise ResourceNotFoundError("Time slot not found.")

        await self._expire_slot_holds(slot, now)
        existing = await self.find_active_hold(time_slot_id, now, user_id=user_id)
        if existing is not None:
            raise DuplicateActiveHoldError("You already hold this time slot.")
        other_active_hold = await self.find_active_hold(time_slot_id, now)
        if other_active_hold is not None:
            raise SlotUnavailableError("Time slot is already held.")
        if slot.status != SlotStatus.AVAILABLE:
            raise SlotUnavailableError("Time slot is not available.")

        booking = Booking(
            booking_reference=booking_reference,
            user_id=user_id,
            court_id=slot.court_id,
            time_slot_id=slot.id,
            status=BookingStatus.HELD,
            total_amount=slot.price,
            hold_expires_at=hold_expires_at,
        )
        slot.status = SlotStatus.HELD
        slot.hold_expires_at = hold_expires_at
        self.session.add(booking)
        await self.session.flush()
        await self.session.refresh(booking)
        return booking

    async def find_active_hold(
        self,
        time_slot_id: uuid.UUID,
        now: datetime,
        user_id: uuid.UUID | None = None,
    ) -> Booking | None:
        """Find a non-expired hold for a slot, optionally owned by one user."""
        stmt = select(Booking).where(
            Booking.time_slot_id == time_slot_id,
            Booking.status == BookingStatus.HELD,
            Booking.hold_expires_at > now,
        )
        if user_id is not None:
            stmt = stmt.where(Booking.user_id == user_id)
        result = await self.session.execute(stmt.limit(1))
        return result.scalar_one_or_none()

    async def expire_old_holds(
        self, now: datetime | None = None, limit: int = 500
    ) -> int:
        """Expire a bounded batch of elapsed holds using skip-locked row locks."""
        current_time = now or datetime.now(UTC)
        expired_slot_ids = select(Booking.time_slot_id).where(
            Booking.status == BookingStatus.HELD,
            Booking.hold_expires_at <= current_time,
        )
        result = await self.session.execute(
            select(TimeSlot)
            .where(TimeSlot.id.in_(expired_slot_ids))
            .order_by(TimeSlot.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        slots = list(result.scalars().all())
        expired_count = 0
        for slot in slots:
            expired_count += await self._expire_slot_holds(slot, current_time)
        await self.session.flush()
        return expired_count

    async def confirm_booking(
        self, booking_id: uuid.UUID, user_id: uuid.UUID, now: datetime
    ) -> Booking:
        """Confirm an owned, unexpired hold while locking its slot and booking."""
        booking = await self._get_owned_booking(booking_id, user_id)
        slot = await self._lock_slot(booking.time_slot_id)
        if slot is None:
            raise ResourceNotFoundError("Time slot not found.")
        booking = await self._lock_booking(booking_id, user_id)

        if booking.status != BookingStatus.HELD:
            raise BookingStateError("Only active holds can be confirmed.")
        if booking.hold_expires_at is None or booking.hold_expires_at <= now:
            booking.status = BookingStatus.EXPIRED
            slot.status = SlotStatus.AVAILABLE
            slot.hold_expires_at = None
            await self.session.flush()
            raise BookingHoldExpiredError("The booking hold has expired.")
        if slot.status != SlotStatus.HELD:
            raise BookingStateError("The held time slot is no longer held.")

        booking.status = BookingStatus.CONFIRMED
        booking.confirmed_at = now
        slot.status = SlotStatus.BOOKED
        slot.hold_expires_at = None
        await self.session.flush()
        await self.session.refresh(booking)
        return booking

    async def cancel_booking(
        self, booking_id: uuid.UUID, user_id: uuid.UUID, now: datetime
    ) -> Booking:
        """Cancel an owned confirmed booking and release its time slot."""
        booking = await self._get_owned_booking(booking_id, user_id)
        slot = await self._lock_slot(booking.time_slot_id)
        if slot is None:
            raise ResourceNotFoundError("Time slot not found.")
        booking = await self._lock_booking(booking_id, user_id)
        if booking.status != BookingStatus.CONFIRMED:
            raise BookingStateError("Only confirmed bookings can be cancelled.")

        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = now
        slot.status = SlotStatus.AVAILABLE
        slot.hold_expires_at = None
        await self.session.flush()
        await self.session.refresh(booking)
        return booking

    async def get_booking(
        self, booking_id: uuid.UUID, user_id: uuid.UUID
    ) -> Booking | None:
        """Fetch a booking owned by the specified user."""
        result = await self.session.execute(
            select(Booking).where(
                Booking.id == booking_id,
                Booking.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_user_bookings(
        self, user_id: uuid.UUID, skip: int, limit: int
    ) -> list[Booking]:
        """List a user's bookings in reverse creation order."""
        result = await self.session.execute(
            select(Booking)
            .where(Booking.user_id == user_id)
            .order_by(Booking.created_at.desc(), Booking.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _lock_slot(self, time_slot_id: uuid.UUID) -> TimeSlot | None:
        result = await self.session.execute(
            select(TimeSlot).where(TimeSlot.id == time_slot_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def _get_owned_booking(
        self, booking_id: uuid.UUID, user_id: uuid.UUID
    ) -> Booking:
        booking = await self.get_booking(booking_id, user_id)
        if booking is None:
            raise BookingNotFoundError("Booking not found.")
        return booking

    async def _lock_booking(self, booking_id: uuid.UUID, user_id: uuid.UUID) -> Booking:
        result = await self.session.execute(
            select(Booking)
            .where(Booking.id == booking_id, Booking.user_id == user_id)
            .with_for_update()
        )
        booking = result.scalar_one_or_none()
        if booking is None:
            raise BookingNotFoundError("Booking not found.")
        return booking

    async def _expire_slot_holds(self, slot: TimeSlot, now: datetime) -> int:
        result = await self.session.execute(
            select(Booking)
            .where(
                Booking.time_slot_id == slot.id,
                Booking.status == BookingStatus.HELD,
                Booking.hold_expires_at <= now,
            )
            .with_for_update()
        )
        bookings = list(result.scalars().all())
        for booking in bookings:
            booking.status = BookingStatus.EXPIRED
        if slot.hold_expires_at is not None and slot.hold_expires_at <= now:
            slot.status = SlotStatus.AVAILABLE
            slot.hold_expires_at = None
        return len(bookings)
