"""Business logic for acquiring and managing temporary booking holds."""

import uuid
from datetime import UTC, datetime, timedelta

from app.core.exceptions import ResourceNotFoundError
from app.db.session import AsyncSession
from app.models.booking import Booking
from app.models.enums import UserRole
from app.repositories.booking_repository import BookingRepository
from app.schemas.bookings import BookingHoldRequest
from app.services.booking_policy_service import BookingPolicyService

HOLD_DURATION = timedelta(minutes=15)
CANCELLATION_NOTICE = timedelta(hours=24)


class BookingService:
    """Coordinate booking operations and enforce hold duration rules."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = BookingRepository(session)

    async def create_hold(
        self, user_id: uuid.UUID, request: BookingHoldRequest
    ) -> Booking:
        """Expire old holds and atomically acquire the requested time slot."""
        now = datetime.now(UTC)
        await self.repository.lock_member(user_id)
        policy = BookingPolicyService(self.repository.session)
        slot = await self.repository.get_slot(request.time_slot_id)
        if slot is None:
            raise ResourceNotFoundError("Time slot not found.")
        await policy.validate_booking(user_id, slot.start_time, slot.end_time, now)
        await self.repository.expire_old_holds(now)
        return await self.repository.create_hold(
            user_id=user_id,
            time_slot_id=request.time_slot_id,
            booking_reference=uuid.uuid4().hex[:20].upper(),
            now=now,
            hold_expires_at=now + HOLD_DURATION,
        )

    async def expire_old_holds(self) -> int:
        """Expire elapsed holds in a bounded batch."""
        return await self.repository.expire_old_holds(datetime.now(UTC))

    async def confirm_booking(
        self,
        booking_id: uuid.UUID,
        user_id: uuid.UUID,
        idempotency_key: str | None = None,
    ) -> Booking:
        """Confirm an owned hold before its expiration time."""
        return await self.repository.confirm_booking(
            booking_id, user_id, datetime.now(UTC), idempotency_key
        )

    async def cancel_booking(
        self,
        booking_id: uuid.UUID,
        user_id: uuid.UUID,
        role: UserRole = UserRole.MEMBER,
    ) -> Booking:
        """Cancel an eligible booking and flag its payment for refund handling."""
        now = datetime.now(UTC)
        return await self.repository.cancel_booking(
            booking_id,
            user_id,
            now,
            now + CANCELLATION_NOTICE,
            is_admin=role == UserRole.ADMIN,
        )

    async def list_user_bookings(
        self, user_id: uuid.UUID, skip: int, limit: int
    ) -> list[Booking]:
        """List the authenticated user's bookings with pagination."""
        return await self.repository.list_user_bookings(user_id, skip, limit)
