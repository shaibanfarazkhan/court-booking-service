"""Transaction, locking, and shared fixture regression coverage."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.core.exceptions import BookingPolicyError
from app.db import session as session_module
from app.models.enums import UserRole
from app.repositories.booking_repository import BookingRepository
from app.services.booking_policy_service import BookingPolicyService


class SessionContext:
    """Async context manager exposing transaction calls for dependency tests."""

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *_exc_info):
        return None


class SessionFactory:
    """Callable session factory compatible with the application dependency."""

    def __init__(self, session):
        self.session = session

    def __call__(self):
        return SessionContext(self.session)


def test_database_dependency_commits_and_closes_after_success(monkeypatch):
    session = SimpleNamespace(
        commit=AsyncMock(), rollback=AsyncMock(), close=AsyncMock()
    )
    monkeypatch.setattr(
        session_module, "async_session_factory", SessionFactory(session)
    )

    async def exercise():
        dependency = session_module.get_db()
        assert await anext(dependency) is session
        with pytest.raises(StopAsyncIteration):
            await anext(dependency)

    asyncio.run(exercise())
    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()
    session.close.assert_awaited_once()


def test_database_dependency_rolls_back_and_closes_on_failure(monkeypatch):
    session = SimpleNamespace(
        commit=AsyncMock(), rollback=AsyncMock(), close=AsyncMock()
    )
    monkeypatch.setattr(
        session_module, "async_session_factory", SessionFactory(session)
    )

    async def exercise():
        dependency = session_module.get_db()
        assert await anext(dependency) is session
        with pytest.raises(RuntimeError, match="transaction failed"):
            await dependency.athrow(RuntimeError("transaction failed"))

    asyncio.run(exercise())
    session.commit.assert_not_awaited()
    session.rollback.assert_awaited_once()
    session.close.assert_awaited_once()


def test_member_lock_compiles_to_database_row_lock():
    session = AsyncMock()
    repository = BookingRepository(session)

    asyncio.run(repository.lock_member(uuid.uuid4()))

    statement = session.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect())).lower()
    assert "for update" in sql
    assert "users" in sql


def test_booking_policy_accepts_exact_minimum_and_maximum_durations():
    service = BookingPolicyService(None)
    service.repository = AsyncMock()
    service.repository.get_active_policy.return_value = SimpleNamespace(
        min_duration_minutes=30,
        max_duration_minutes=60,
        daily_limit=5,
        weekly_limit=10,
        future_booking_limit=20,
    )
    service.repository.has_overlap.return_value = False
    service.repository.count_daily_bookings.return_value = 0
    service.repository.count_weekly_bookings.return_value = 0
    service.repository.count_future_bookings.return_value = 0
    now = datetime.now(UTC)
    start = now + timedelta(days=2)

    async def exercise():
        await service.validate_booking(None, start, start + timedelta(minutes=30), now)
        await service.validate_booking(None, start, start + timedelta(minutes=60), now)

    asyncio.run(exercise())
    assert service.repository.has_overlap.await_count == 2


def test_booking_policy_limit_failure_is_not_swallowed():
    service = BookingPolicyService(None)
    service.repository = AsyncMock()
    service.repository.get_active_policy.return_value = SimpleNamespace(
        min_duration_minutes=30,
        max_duration_minutes=60,
        daily_limit=1,
        weekly_limit=2,
        future_booking_limit=3,
    )
    service.repository.has_overlap.return_value = False
    service.repository.count_daily_bookings.return_value = 1
    start = datetime.now(UTC) + timedelta(days=2)

    with pytest.raises(BookingPolicyError, match="Daily"):
        asyncio.run(
            service.validate_booking(None, start, start + timedelta(minutes=30), start)
        )


def test_shared_user_factory_covers_roles_and_inactive_state(user_factory):
    member = user_factory()
    staff = user_factory(role=UserRole.STAFF)
    admin = user_factory(role=UserRole.ADMIN)
    inactive = user_factory(is_active=False)

    assert member.role is UserRole.MEMBER and member.is_active
    assert staff.role is UserRole.STAFF
    assert admin.role is UserRole.ADMIN
    assert not inactive.is_active
