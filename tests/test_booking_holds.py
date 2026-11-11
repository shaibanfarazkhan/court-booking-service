"""Service, repository, and API tests for the booking hold lifecycle."""

import asyncio
import uuid
from collections.abc import Coroutine, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, TypeVar
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.dependencies import require_member
from app.api.v1.bookings import (
    _raise_booking_error,
    router,
)
from app.api.v1.bookings import (
    cancel_booking as cancel_booking_endpoint,
)
from app.api.v1.bookings import (
    confirm_booking as confirm_booking_endpoint,
)
from app.api.v1.bookings import (
    create_hold as create_hold_endpoint,
)
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
from app.repositories.booking_repository import BookingRepository
from app.schemas.bookings import BookingHoldRequest
from app.services.booking_service import HOLD_DURATION, BookingService

T = TypeVar("T")


def run(coroutine: Coroutine[Any, Any, T]) -> T:
    """Execute an async unit under synchronous pytest."""
    return asyncio.run(coroutine)


class FakeResult:
    """Small SQLAlchemy result stand-in for repository unit tests."""

    def __init__(self, scalar: Any = None, rows: list[Any] | None = None) -> None:
        self.scalar = scalar
        self.rows = rows or []

    def scalar_one_or_none(self) -> Any:
        return self.scalar

    def scalars(self) -> "FakeResult":
        return self

    def all(self) -> list[Any]:
        return self.rows


class FakeSession:
    """Captures repository statements and supplies deterministic results."""

    def __init__(self, results: Sequence[FakeResult]) -> None:
        self.results = list(results)
        self.statements = []
        self.added = []
        self.flush = AsyncMock()
        self.refresh = AsyncMock()
        self.delete = AsyncMock()

    async def execute(self, statement: Any) -> FakeResult:
        self.statements.append(statement)
        return self.results.pop(0)

    def add(self, entity) -> None:
        self.added.append(entity)


def fake_slot(
    status: SlotStatus = SlotStatus.AVAILABLE,
    expires_at: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        court_id=uuid.uuid4(),
        price=Decimal("42.50"),
        status=status,
        hold_expires_at=expires_at,
    )


def fake_booking(
    slot: SimpleNamespace,
    status: BookingStatus = BookingStatus.HELD,
    hold_expires_at: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        booking_reference="REF123",
        user_id=uuid.uuid4(),
        court_id=slot.court_id,
        time_slot_id=slot.id,
        status=status,
        total_amount=Decimal("42.50"),
        hold_expires_at=hold_expires_at,
        confirmed_at=None,
        cancelled_at=None,
    )


def test_service_creates_fifteen_minute_hold_and_expires_old_holds() -> None:
    service = BookingService(AsyncMock())
    service.repository = AsyncMock()
    expected = object()
    service.repository.create_hold.return_value = expected

    result = run(
        service.create_hold(uuid.uuid4(), BookingHoldRequest(time_slot_id=uuid.uuid4()))
    )

    assert result is expected
    service.repository.expire_old_holds.assert_awaited_once()
    call = service.repository.create_hold.await_args.kwargs
    assert call["hold_expires_at"] - call["now"] == HOLD_DURATION
    assert len(call["booking_reference"]) == 20


def test_service_exposes_expiration_confirmation_cancellation_and_pagination() -> None:
    service = BookingService(AsyncMock())
    service.repository = AsyncMock()
    service.repository.expire_old_holds.return_value = 3
    service.repository.confirm_booking.return_value = "confirmed"
    service.repository.cancel_booking.return_value = "cancelled"
    service.repository.list_user_bookings.return_value = ["first", "second"]
    user_id = uuid.uuid4()
    booking_id = uuid.uuid4()

    assert run(service.expire_old_holds()) == 3
    assert run(service.confirm_booking(booking_id, user_id)) == "confirmed"
    assert run(service.cancel_booking(booking_id, user_id)) == "cancelled"
    assert run(service.list_user_bookings(user_id, 10, 5)) == ["first", "second"]
    service.repository.list_user_bookings.assert_awaited_with(user_id, 10, 5)


def test_repository_create_hold_locks_slot_and_marks_it_held() -> None:
    now = datetime.now(UTC)
    slot = fake_slot()
    session = FakeSession(
        [
            FakeResult(scalar=slot),
            FakeResult(rows=[]),
            FakeResult(scalar=None),
            FakeResult(scalar=None),
        ]
    )
    repo = BookingRepository(session)
    result = run(
        repo.create_hold(uuid.uuid4(), slot.id, "REF123", now, now + HOLD_DURATION)
    )

    assert result in session.added
    assert result.status == BookingStatus.HELD
    assert slot.status == SlotStatus.HELD
    assert slot.hold_expires_at == now + HOLD_DURATION
    assert session.statements[0]._for_update_arg is not None


def test_repository_rejects_duplicate_active_hold() -> None:
    now = datetime.now(UTC)
    slot = fake_slot(SlotStatus.HELD, now + timedelta(minutes=4))
    session = FakeSession(
        [
            FakeResult(scalar=slot),
            FakeResult(rows=[]),
            FakeResult(
                scalar=fake_booking(slot, hold_expires_at=now + timedelta(minutes=4))
            ),
        ]
    )
    with pytest.raises(DuplicateActiveHoldError):
        run(
            BookingRepository(session).create_hold(
                uuid.uuid4(), slot.id, "REF123", now, now + HOLD_DURATION
            )
        )


def test_repository_rejects_unavailable_slot() -> None:
    now = datetime.now(UTC)
    slot = fake_slot(SlotStatus.BOOKED)
    session = FakeSession(
        [
            FakeResult(scalar=slot),
            FakeResult(rows=[]),
            FakeResult(scalar=None),
            FakeResult(scalar=None),
        ]
    )
    with pytest.raises(SlotUnavailableError):
        run(
            BookingRepository(session).create_hold(
                uuid.uuid4(), slot.id, "REF123", now, now + HOLD_DURATION
            )
        )


def test_repository_returns_not_found_for_missing_slot() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ResourceNotFoundError):
        run(
            BookingRepository(FakeSession([FakeResult()])).create_hold(
                uuid.uuid4(), uuid.uuid4(), "REF123", now, now + HOLD_DURATION
            )
        )


def test_repository_expire_old_holds_updates_booking_and_slot() -> None:
    now = datetime.now(UTC)
    slot = fake_slot(SlotStatus.HELD, now - timedelta(seconds=1))
    booking = fake_booking(slot, hold_expires_at=now - timedelta(seconds=1))
    session = FakeSession([FakeResult(rows=[slot]), FakeResult(rows=[booking])])

    expired = run(BookingRepository(session).expire_old_holds(now))

    assert expired == 1
    assert booking.status == BookingStatus.EXPIRED
    assert slot.status == SlotStatus.AVAILABLE
    assert slot.hold_expires_at is None
    assert session.statements[0]._for_update_arg.skip_locked is True


def test_repository_confirm_booking_updates_booking_and_slot() -> None:
    now = datetime.now(UTC)
    slot = fake_slot(SlotStatus.HELD, now + HOLD_DURATION)
    booking = fake_booking(slot, hold_expires_at=now + HOLD_DURATION)
    session = FakeSession(
        [
            FakeResult(scalar=booking),
            FakeResult(scalar=slot),
            FakeResult(scalar=booking),
        ]
    )

    confirmed = run(
        BookingRepository(session).confirm_booking(booking.id, booking.user_id, now)
    )

    assert confirmed.status == BookingStatus.CONFIRMED
    assert booking.confirmed_at == now
    assert slot.status == SlotStatus.BOOKED
    assert session.statements[1]._for_update_arg is not None
    assert session.statements[2]._for_update_arg is not None


def test_repository_confirmation_retry_with_same_key_returns_confirmed_booking() -> (
    None
):
    now = datetime.now(UTC)
    slot = fake_slot(SlotStatus.BOOKED)
    booking = fake_booking(slot, status=BookingStatus.CONFIRMED)
    booking.idempotency_key = "confirm-request-1"
    session = FakeSession(
        [
            FakeResult(scalar=booking),
            FakeResult(scalar=slot),
            FakeResult(scalar=booking),
        ]
    )

    result = run(
        BookingRepository(session).confirm_booking(
            booking.id, booking.user_id, now, "confirm-request-1"
        )
    )

    assert result is booking
    assert booking.status == BookingStatus.CONFIRMED
    session.flush.assert_not_awaited()


def test_repository_confirmation_retry_with_different_key_is_rejected() -> None:
    now = datetime.now(UTC)
    slot = fake_slot(SlotStatus.BOOKED)
    booking = fake_booking(slot, status=BookingStatus.CONFIRMED)
    booking.idempotency_key = "original-key"
    session = FakeSession(
        [
            FakeResult(scalar=booking),
            FakeResult(scalar=slot),
            FakeResult(scalar=booking),
        ]
    )

    with pytest.raises(BookingStateError):
        run(
            BookingRepository(session).confirm_booking(
                booking.id, booking.user_id, now, "different-key"
            )
        )


def test_repository_stores_key_as_part_of_successful_transition() -> None:
    now = datetime.now(UTC)
    slot = fake_slot(SlotStatus.HELD, now + HOLD_DURATION)
    booking = fake_booking(slot, hold_expires_at=now + HOLD_DURATION)
    session = FakeSession(
        [
            FakeResult(scalar=booking),
            FakeResult(scalar=slot),
            FakeResult(scalar=booking),
        ]
    )

    run(
        BookingRepository(session).confirm_booking(
            booking.id, booking.user_id, now, "new-key"
        )
    )

    assert booking.idempotency_key == "new-key"


def test_repository_expired_confirmation_persists_expiration_transition() -> None:
    now = datetime.now(UTC)
    slot = fake_slot(SlotStatus.HELD, now - timedelta(seconds=1))
    booking = fake_booking(slot, hold_expires_at=now - timedelta(seconds=1))
    session = FakeSession(
        [
            FakeResult(scalar=booking),
            FakeResult(scalar=slot),
            FakeResult(scalar=booking),
        ]
    )

    with pytest.raises(BookingHoldExpiredError):
        run(
            BookingRepository(session).confirm_booking(booking.id, booking.user_id, now)
        )
    assert booking.status == BookingStatus.EXPIRED
    assert slot.status == SlotStatus.AVAILABLE
    session.flush.assert_awaited_once()


def test_repository_confirmation_rejects_wrong_state_and_owner() -> None:
    now = datetime.now(UTC)
    slot = fake_slot(SlotStatus.BOOKED)
    booking = fake_booking(slot, status=BookingStatus.CONFIRMED)
    session = FakeSession(
        [
            FakeResult(scalar=booking),
            FakeResult(scalar=slot),
            FakeResult(scalar=booking),
        ]
    )
    with pytest.raises(BookingStateError):
        run(
            BookingRepository(session).confirm_booking(booking.id, booking.user_id, now)
        )

    missing_session = FakeSession([FakeResult()])
    with pytest.raises(BookingNotFoundError):
        run(
            BookingRepository(missing_session).confirm_booking(
                uuid.uuid4(), uuid.uuid4(), now
            )
        )


def test_repository_cancel_booking_releases_slot() -> None:
    now = datetime.now(UTC)
    slot = fake_slot(SlotStatus.BOOKED)
    booking = fake_booking(slot, status=BookingStatus.CONFIRMED)
    session = FakeSession(
        [
            FakeResult(scalar=booking),
            FakeResult(scalar=slot),
            FakeResult(scalar=booking),
        ]
    )

    cancelled = run(
        BookingRepository(session).cancel_booking(booking.id, booking.user_id, now)
    )

    assert cancelled.status == BookingStatus.CANCELLED
    assert cancelled.cancelled_at == now
    assert slot.status == SlotStatus.AVAILABLE


def test_repository_list_user_bookings_applies_pagination() -> None:
    session = FakeSession([FakeResult(rows=["one", "two"])])
    bookings = run(BookingRepository(session).list_user_bookings(uuid.uuid4(), 5, 2))
    assert bookings == ["one", "two"]
    query = session.statements[0].compile()
    assert "LIMIT" in str(query).upper()
    assert "OFFSET" in str(query).upper()


def test_hold_api_returns_created_booking_and_uses_authenticated_user() -> None:
    user = SimpleNamespace(id=uuid.uuid4())
    db = AsyncMock()
    booking = SimpleNamespace(booking_reference="REF123")
    service = BookingService(db)
    service.create_hold = AsyncMock(return_value=booking)
    original = BookingService

    class ServiceFactory:
        def __new__(cls, _session):
            return service

    import app.api.v1.bookings as booking_api

    booking_api.BookingService = ServiceFactory
    try:
        result = run(
            create_hold_endpoint(
                BookingHoldRequest(time_slot_id=uuid.uuid4()), db, user
            )
        )
    finally:
        booking_api.BookingService = original
    assert result is booking
    service.create_hold.assert_awaited_once()


def test_confirm_api_returns_410_response_after_expiration() -> None:
    user = SimpleNamespace(id=uuid.uuid4())
    service = BookingService(AsyncMock())
    service.confirm_booking = AsyncMock(
        side_effect=BookingHoldExpiredError("The booking hold has expired.")
    )
    original = BookingService

    class ServiceFactory:
        def __new__(cls, _session):
            return service

    import app.api.v1.bookings as booking_api

    booking_api.BookingService = ServiceFactory
    try:
        response = run(confirm_booking_endpoint(uuid.uuid4(), AsyncMock(), user))
    finally:
        booking_api.BookingService = original
    assert isinstance(response, JSONResponse)
    assert response.status_code == 410


def test_confirm_api_passes_idempotency_key_to_service() -> None:
    user = SimpleNamespace(id=uuid.uuid4())
    booking_id = uuid.uuid4()
    service = BookingService(AsyncMock())
    booking = SimpleNamespace(status=BookingStatus.CONFIRMED)
    service.confirm_booking = AsyncMock(return_value=booking)
    original = BookingService

    class ServiceFactory:
        def __new__(cls, _session):
            return service

    import app.api.v1.bookings as booking_api

    booking_api.BookingService = ServiceFactory
    try:
        result = run(
            confirm_booking_endpoint(
                booking_id, AsyncMock(), user, idempotency_key="retry-key"
            )
        )
    finally:
        booking_api.BookingService = original
    assert result is booking
    service.confirm_booking.assert_awaited_once_with(booking_id, user.id, "retry-key")


def test_cancel_api_returns_booking() -> None:
    user = SimpleNamespace(id=uuid.uuid4())
    db = AsyncMock()
    booking = SimpleNamespace(status=BookingStatus.CANCELLED)
    service = BookingService(db)
    service.cancel_booking = AsyncMock(return_value=booking)
    original = BookingService

    class ServiceFactory:
        def __new__(cls, _session):
            return service

    import app.api.v1.bookings as booking_api

    booking_api.BookingService = ServiceFactory
    try:
        response = run(cancel_booking_endpoint(uuid.uuid4(), db, user))
    finally:
        booking_api.BookingService = original
    assert response is booking


def test_booking_errors_map_to_expected_http_statuses() -> None:
    errors = [
        (BookingNotFoundError("missing"), 404),
        (ResourceNotFoundError("missing"), 404),
        (BookingHoldExpiredError("expired"), 410),
        (BookingStateError("state"), 409),
        (DuplicateActiveHoldError("duplicate"), 409),
        (SlotUnavailableError("unavailable"), 409),
    ]
    for error, expected_status in errors:
        with pytest.raises(HTTPException) as exc_info:
            _raise_booking_error(error)
        assert exc_info.value.status_code == expected_status


def test_booking_routes_require_member_authentication() -> None:
    assert {route.path for route in router.routes} == {
        "/bookings/holds",
        "/bookings/{booking_id}/confirm",
        "/bookings/{booking_id}/cancel",
        "/bookings/my",
    }
    for route in router.routes:
        dependencies = {dependency.call for dependency in route.dependant.dependencies}
        assert require_member in dependencies


def test_booking_model_supports_expired_status_and_booking_history() -> None:
    assert BookingStatus.EXPIRED.value == "EXPIRED"
    assert hasattr(Booking, "expires_at")
    assert Booking.__table__.columns["time_slot_id"].unique is not True
    assert TimeSlot.bookings.property.uselist is True


def test_locking_selects_use_for_update() -> None:
    query = select(TimeSlot).with_for_update(skip_locked=True)
    assert query._for_update_arg is not None
    assert query._for_update_arg.skip_locked is True
