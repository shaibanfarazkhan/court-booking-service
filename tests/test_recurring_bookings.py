"""Tests for recurring booking validation, generation, and retry safety."""

import asyncio
import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.exceptions import AccountInactiveError, IdempotencyConflictError
from app.models.enums import BookingStatus, RecurrenceType, SlotStatus
from app.schemas.bookings import RecurringBookingRequest
from app.services.recurring_booking_service import RecurringBookingService


class MemoryRecurringRepository:
    """Shared in-memory repository exercising service orchestration and locking."""

    def __init__(self, slots, availability, conflicts=None, active_user=True):
        self.slots = slots
        self.availability = availability
        self.bookings = list(conflicts or [])
        self.receipts = {}
        self.user_locks = {}
        self.court_locks = {}
        self.active_locks = {}
        self.active_user = active_user

    async def lock_active_user(self, user_id):
        lock = self.user_locks.setdefault(user_id, asyncio.Lock())
        await lock.acquire()
        self.active_locks[asyncio.current_task()] = [lock]
        await asyncio.sleep(0)
        if not self.active_user:
            raise AccountInactiveError("Inactive users cannot create bookings.")

    async def get_idempotent_request(self, user_id, key):
        return self.receipts.get((user_id, key))

    async def lock_active_court(self, court_id):
        lock = self.court_locks.setdefault(court_id, asyncio.Lock())
        await lock.acquire()
        self.active_locks[asyncio.current_task()].append(lock)
        await asyncio.sleep(0)

    async def get_availability(self, court_id, weekdays):
        return [
            row
            for row in self.availability
            if row.court_id == court_id and row.weekday in weekdays
        ]

    async def lock_occurrence_slots(self, court_id, starts):
        return [
            slot
            for slot in self.slots
            if slot.court_id == court_id and slot.start_time in starts
        ]

    async def get_conflicting_slot_ids(self, slot_ids):
        return {
            booking.time_slot_id
            for booking in self.bookings
            if booking.time_slot_id in slot_ids
            and booking.status
            in (
                BookingStatus.HELD,
                BookingStatus.CONFIRMED,
                BookingStatus.COMPLETED,
            )
        }

    async def persist_generated_bookings(self, bookings, receipt):
        self.bookings.extend(bookings)
        if receipt is not None:
            self.receipts[(receipt.user_id, receipt.idempotency_key)] = receipt
        for lock in self.active_locks.pop(asyncio.current_task(), []):
            lock.release()

    async def get_bookings_for_group(self, group_id):
        return [
            booking
            for booking in self.bookings
            if booking.recurring_group_id == group_id
        ]

    @staticmethod
    def create_booking(**kwargs):
        now = kwargs["now"]
        kwargs["slot"].status = SlotStatus.BOOKED
        kwargs["slot"].hold_expires_at = None
        return SimpleNamespace(
            id=uuid.uuid4(),
            booking_reference=uuid.uuid4().hex[:20].upper(),
            user_id=kwargs["user_id"],
            court_id=kwargs["court_id"],
            time_slot_id=kwargs["slot"].id,
            status=BookingStatus.CONFIRMED,
            total_amount=kwargs["slot"].price,
            hold_expires_at=None,
            confirmed_at=now,
            cancelled_at=None,
            refund_eligible=False,
            created_at=now,
            updated_at=now,
            is_recurring=True,
            recurring_group_id=kwargs["group_id"],
        )

    @staticmethod
    def serialize_skips(skipped):
        return [{"date": day.isoformat(), "reason": reason} for day, reason in skipped]


def make_slot(court_id, day, start=time(10), end=time(11)):
    return SimpleNamespace(
        id=uuid.uuid4(),
        court_id=court_id,
        start_time=datetime.combine(day, start, tzinfo=UTC),
        end_time=datetime.combine(day, end, tzinfo=UTC),
        price=Decimal("50.00"),
        status=SlotStatus.AVAILABLE,
        hold_expires_at=None,
    )


def make_availability(court_id, weekday):
    return SimpleNamespace(
        court_id=court_id,
        weekday=weekday,
        available=True,
        start_time=time(8),
        end_time=time(20),
    )


def make_payload(start, end, pattern=RecurrenceType.DAILY, key=None):
    return RecurringBookingRequest(
        court_id=uuid.uuid4(),
        start_date=start,
        end_date=end,
        start_time=time(10),
        end_time=time(11),
        recurrence_type=pattern,
        idempotency_key=key,
    )


def make_service(slots, availability, conflicts=None):
    service = RecurringBookingService(None)
    service.repository = MemoryRecurringRepository(slots, availability, conflicts)
    return service


def test_daily_recurrence_creates_confirmed_bookings() -> None:
    start = date(2026, 12, 1)
    days = [start + timedelta(days=offset) for offset in range(3)]
    payload = make_payload(start, days[-1])
    slots = [make_slot(payload.court_id, day) for day in days]
    service = make_service(
        slots, [make_availability(payload.court_id, day.weekday()) for day in days]
    )

    result = asyncio.run(service.create_recurring_bookings(uuid.uuid4(), payload))

    assert len(result.created_bookings) == 3
    assert not result.skipped_occurrences
    assert all(
        item.status == BookingStatus.CONFIRMED for item in result.created_bookings
    )
    assert all(item.is_recurring for item in service.repository.bookings)
    assert len({item.recurring_group_id for item in service.repository.bookings}) == 1
    assert all(slot.status == SlotStatus.BOOKED for slot in slots)


def test_weekly_recurrence_creates_one_booking_each_week() -> None:
    start = date(2026, 12, 1)
    days = [start + timedelta(days=7 * offset) for offset in range(3)]
    payload = make_payload(start, days[-1], RecurrenceType.WEEKLY)
    slots = [make_slot(payload.court_id, day) for day in days]
    service = make_service(
        slots, [make_availability(payload.court_id, start.weekday())]
    )

    result = asyncio.run(service.create_recurring_bookings(uuid.uuid4(), payload))

    assert len(result.created_bookings) == 3
    assert not result.skipped_occurrences


def test_unavailable_dates_are_skipped_while_available_dates_are_created() -> None:
    start = date(2026, 12, 1)
    days = [start + timedelta(days=offset) for offset in range(3)]
    payload = make_payload(start, days[-1])
    slots = [make_slot(payload.court_id, day) for day in days]
    availability = [make_availability(payload.court_id, days[0].weekday())]
    service = make_service(slots, availability)

    result = asyncio.run(service.create_recurring_bookings(uuid.uuid4(), payload))

    assert len(result.created_bookings) == 1
    assert [(item.date, item.reason) for item in result.skipped_occurrences] == [
        (days[1], "outside_availability"),
        (days[2], "outside_availability"),
    ]


def test_booking_conflicts_are_skipped_instead_of_failing_the_series() -> None:
    start = date(2026, 12, 1)
    days = [start, start + timedelta(days=1)]
    payload = make_payload(start, days[-1])
    slots = [make_slot(payload.court_id, day) for day in days]
    conflict = SimpleNamespace(time_slot_id=slots[0].id, status=BookingStatus.CONFIRMED)
    service = make_service(
        slots,
        [make_availability(payload.court_id, day.weekday()) for day in days],
        [conflict],
    )

    result = asyncio.run(service.create_recurring_bookings(uuid.uuid4(), payload))

    assert len(result.created_bookings) == 1
    assert result.skipped_occurrences[0].date == days[0]
    assert result.skipped_occurrences[0].reason == "booking_conflict"


def test_slot_already_held_or_blocked_is_skipped() -> None:
    start = date(2026, 12, 1)
    payload = make_payload(start, start)
    slot = make_slot(payload.court_id, start)
    slot.status = SlotStatus.BLOCKED
    service = make_service(
        [slot], [make_availability(payload.court_id, start.weekday())]
    )

    result = asyncio.run(service.create_recurring_bookings(uuid.uuid4(), payload))

    assert result.created_bookings == []
    assert result.skipped_occurrences[0].reason == "slot_blocked"


def test_invalid_recurrence_and_date_ranges_are_rejected() -> None:
    court_id = uuid.uuid4()
    with pytest.raises(ValidationError):
        RecurringBookingRequest(
            court_id=court_id,
            start_date=date(2026, 12, 2),
            end_date=date(2026, 12, 1),
            start_time=time(10),
            end_time=time(11),
            recurrence_type="MONTHLY",
        )
    with pytest.raises(ValidationError):
        make_payload(date(2026, 1, 1), date(2026, 4, 1), RecurrenceType.DAILY)


def test_request_rejects_invalid_time_and_more_than_ninety_dates() -> None:
    with pytest.raises(ValidationError):
        RecurringBookingRequest(
            court_id=uuid.uuid4(),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 1),
            start_time=time(11),
            end_time=time(10),
            recurrence_type=RecurrenceType.DAILY,
        )
    with pytest.raises(ValidationError):
        make_payload(date(2026, 1, 1), date(2026, 4, 1), RecurrenceType.DAILY)


def test_request_rejects_timezone_embedded_in_local_time() -> None:
    with pytest.raises(ValidationError):
        RecurringBookingRequest(
            court_id=uuid.uuid4(),
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 1),
            start_time=time(10, tzinfo=UTC),
            end_time=time(11),
            recurrence_type=RecurrenceType.DAILY,
        )


def test_idempotent_retry_returns_the_original_created_bookings() -> None:
    start = date(2026, 12, 1)
    payload = make_payload(start, start + timedelta(days=1), key="series-key")
    slots = [make_slot(payload.court_id, start + timedelta(days=i)) for i in range(2)]
    service = make_service(
        slots,
        [
            make_availability(payload.court_id, (start + timedelta(days=i)).weekday())
            for i in range(2)
        ],
    )
    user_id = uuid.uuid4()

    first, retry = asyncio.run(_create_twice(service, user_id, payload))

    assert first.recurring_group_id == retry.recurring_group_id
    assert [booking.id for booking in first.created_bookings] == [
        booking.id for booking in retry.created_bookings
    ]
    assert len(service.repository.bookings) == 2


async def _create_twice(service, user_id, payload):
    return await asyncio.gather(
        service.create_recurring_bookings(user_id, payload),
        service.create_recurring_bookings(user_id, payload),
    )


def test_idempotency_key_cannot_be_reused_for_different_request() -> None:
    start = date(2026, 12, 1)
    payload = make_payload(start, start, key="same-key")
    service = make_service([], [])
    user_id = uuid.uuid4()

    asyncio.run(service.create_recurring_bookings(user_id, payload))
    changed = payload.model_copy(update={"end_date": start + timedelta(days=1)})

    with pytest.raises(IdempotencyConflictError):
        asyncio.run(service.create_recurring_bookings(user_id, changed))


def test_same_key_concurrent_requests_create_only_one_series() -> None:
    start = date(2026, 12, 1)
    payload = make_payload(start, start + timedelta(days=1), key="parallel-key")
    slots = [make_slot(payload.court_id, start + timedelta(days=i)) for i in range(2)]
    service = make_service(
        slots,
        [
            make_availability(payload.court_id, (start + timedelta(days=i)).weekday())
            for i in range(2)
        ],
    )

    results = asyncio.run(_create_twice(service, uuid.uuid4(), payload))

    assert len(service.repository.bookings) == 2
    assert results[0].recurring_group_id == results[1].recurring_group_id


def test_concurrent_members_cannot_book_same_recurring_slots_twice() -> None:
    start = date(2026, 12, 1)
    payload = make_payload(start, start)
    slot = make_slot(payload.court_id, start)
    service = make_service(
        [slot], [make_availability(payload.court_id, start.weekday())]
    )

    first, second = asyncio.run(
        _create_for_two_members(service, payload, uuid.uuid4(), uuid.uuid4())
    )

    assert len(service.repository.bookings) == 1
    assert sorted(len(result.created_bookings) for result in (first, second)) == [0, 1]


async def _create_for_two_members(service, payload, first_user, second_user):
    return await asyncio.gather(
        service.create_recurring_bookings(first_user, payload),
        service.create_recurring_bookings(second_user, payload),
    )


def test_inactive_member_is_rejected() -> None:
    start = date(2026, 12, 1)
    payload = make_payload(start, start)
    service = make_service([], [])
    service.repository.active_user = False

    with pytest.raises(AccountInactiveError):
        asyncio.run(service.create_recurring_bookings(uuid.uuid4(), payload))


def test_each_booking_uses_authenticated_member_as_owner() -> None:
    start = date(2026, 12, 1)
    payload = make_payload(start, start)
    slot = make_slot(payload.court_id, start)
    service = make_service(
        [slot], [make_availability(payload.court_id, start.weekday())]
    )
    owner_id = uuid.uuid4()

    result = asyncio.run(service.create_recurring_bookings(owner_id, payload))

    assert result.created_bookings[0].user_id == owner_id


def test_time_zone_is_used_to_resolve_local_slot_times() -> None:
    local_day = date(2026, 12, 1)
    payload = RecurringBookingRequest(
        court_id=uuid.uuid4(),
        start_date=local_day,
        end_date=local_day,
        start_time=time(10),
        end_time=time(11),
        recurrence_type=RecurrenceType.DAILY,
        timezone="Asia/Kolkata",
    )
    slot = SimpleNamespace(
        id=uuid.uuid4(),
        court_id=payload.court_id,
        start_time=datetime(2026, 12, 1, 4, 30, tzinfo=UTC),
        end_time=datetime(2026, 12, 1, 5, 30, tzinfo=UTC),
        price=Decimal("50.00"),
        status=SlotStatus.AVAILABLE,
        hold_expires_at=None,
    )
    service = make_service(
        [slot], [make_availability(payload.court_id, local_day.weekday())]
    )

    result = asyncio.run(service.create_recurring_bookings(uuid.uuid4(), payload))

    assert len(result.created_bookings) == 1
