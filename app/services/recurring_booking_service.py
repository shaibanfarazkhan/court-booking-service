"""Business rules for generating daily and weekly booking occurrences."""

import hashlib
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.exceptions import IdempotencyConflictError
from app.db.session import AsyncSession
from app.models.availability import Availability
from app.models.booking import Booking
from app.models.enums import RecurrenceType, SlotStatus
from app.models.recurring_booking_request import (
    RecurringBookingRequest as RecurringBookingRequestRecord,
)
from app.repositories.recurring_booking_repository import RecurringBookingRepository
from app.schemas.bookings import (
    RecurringBookingRequest,
    RecurringBookingResponse,
    SkippedOccurrence,
)

MAX_RECURRENCE_DAYS = 90
MAX_GENERATED_BOOKINGS = 100


class RecurringBookingService:
    """Validate recurrence rules and coordinate atomic booking persistence."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = RecurringBookingRepository(session)

    async def create_recurring_bookings(
        self, user_id: uuid.UUID, payload: RecurringBookingRequest
    ) -> RecurringBookingResponse:
        """Create each available occurrence and report dates that were skipped."""
        if payload.end_date < payload.start_date:
            raise ValueError("end_date must be on or after start_date")
        if (payload.end_date - payload.start_date).days + 1 > MAX_RECURRENCE_DAYS:
            raise ValueError("recurrence duration cannot exceed 90 days")
        if payload.start_time >= payload.end_time:
            raise ValueError("end_time must be after start_time")
        try:
            timezone = ZoneInfo(payload.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc

        occurrences = self._generate_occurrences(payload, timezone)
        if len(occurrences) > MAX_GENERATED_BOOKINGS:
            raise ValueError("recurrence cannot generate more than 100 bookings")
        self._reject_overlapping_occurrences(occurrences)
        request_hash = self._request_hash(payload)

        # User row locking serializes the same member's idempotency-key lookup;
        # court and slot locks serialize different members competing for inventory.
        await self.repository.lock_active_user(user_id)
        if payload.idempotency_key is not None:
            prior = await self.repository.get_idempotent_request(
                user_id, payload.idempotency_key
            )
            if prior is not None:
                if prior.request_hash != request_hash:
                    raise IdempotencyConflictError(
                        "Idempotency key was already used for a different request."
                    )
                return RecurringBookingResponse(
                    recurring_group_id=prior.recurring_group_id,
                    created_bookings=await self.repository.get_bookings_for_group(
                        prior.recurring_group_id
                    ),
                    skipped_occurrences=prior.skipped_occurrences,
                )

        await self.repository.lock_active_court(payload.court_id)
        availability = await self.repository.get_availability(
            payload.court_id, {occurrence[0].weekday() for occurrence in occurrences}
        )
        starts = [start_utc for _, start_utc, _ in occurrences]
        slots = await self.repository.lock_occurrence_slots(payload.court_id, starts)
        slots_by_start = {slot.start_time.astimezone(UTC): slot for slot in slots}
        potential_ids = {slot.id for slot in slots}
        conflicting_ids = await self.repository.get_conflicting_slot_ids(potential_ids)

        availability_by_weekday: dict[int, list[Availability]] = {}
        for window in availability:
            availability_by_weekday.setdefault(window.weekday, []).append(window)

        now = datetime.now(UTC)
        group_id = uuid.uuid4()
        created: list[Booking] = []
        skipped: list[tuple[date, str]] = []
        for occurrence_date, start_utc, end_utc in occurrences:
            is_available = any(
                window.available
                and window.start_time <= payload.start_time
                and window.end_time >= payload.end_time
                for window in availability_by_weekday.get(occurrence_date.weekday(), [])
            )
            if not is_available:
                skipped.append((occurrence_date, "outside_availability"))
                continue

            slot = slots_by_start.get(start_utc)
            if slot is None or slot.end_time.astimezone(UTC) != end_utc:
                skipped.append((occurrence_date, "slot_not_found"))
                continue
            if slot.status != SlotStatus.AVAILABLE:
                skipped.append(
                    (
                        occurrence_date,
                        "slot_blocked"
                        if slot.status == SlotStatus.BLOCKED
                        else "slot_unavailable",
                    )
                )
                continue
            if slot.id in conflicting_ids:
                skipped.append((occurrence_date, "booking_conflict"))
                continue

            created.append(
                self.repository.create_booking(
                    user_id=user_id,
                    court_id=payload.court_id,
                    slot=slot,
                    group_id=group_id,
                    now=now,
                )
            )

        receipt = None
        if payload.idempotency_key is not None:
            receipt = RecurringBookingRequestRecord(
                user_id=user_id,
                idempotency_key=payload.idempotency_key,
                request_hash=request_hash,
                recurring_group_id=group_id,
                skipped_occurrences=self.repository.serialize_skips(skipped),
            )
        await self.repository.persist_generated_bookings(created, receipt)
        return RecurringBookingResponse(
            recurring_group_id=group_id,
            created_bookings=created,
            skipped_occurrences=[
                SkippedOccurrence(date=skipped_date, reason=reason)
                for skipped_date, reason in skipped
            ],
        )

    @staticmethod
    def _generate_occurrences(
        payload: RecurringBookingRequest, timezone: ZoneInfo
    ) -> list[tuple[date, datetime, datetime]]:
        step = timedelta(
            days=1 if payload.recurrence_type == RecurrenceType.DAILY else 7
        )
        occurrences: list[tuple[date, datetime, datetime]] = []
        current = payload.start_date
        while current <= payload.end_date:
            local_start = datetime.combine(current, payload.start_time, tzinfo=timezone)
            local_end = datetime.combine(current, payload.end_time, tzinfo=timezone)
            occurrences.append(
                (current, local_start.astimezone(UTC), local_end.astimezone(UTC))
            )
            current += step
        return occurrences

    @staticmethod
    def _reject_overlapping_occurrences(
        occurrences: list[tuple[date, datetime, datetime]],
    ) -> None:
        ordered = sorted(occurrences, key=lambda occurrence: occurrence[1])
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if current[1] < previous[2]:
                raise ValueError("recurrence occurrences must not overlap")

    @staticmethod
    def _request_hash(payload: RecurringBookingRequest) -> str:
        canonical = json.dumps(
            payload.model_dump(mode="json", exclude={"idempotency_key"}),
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
