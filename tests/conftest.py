"""Pytest fixtures and configuration."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from app.models.enums import UserRole
from app.models.user import User

try:
    import httpx
    import pytest_asyncio

    from app.main import app

    @pytest_asyncio.fixture  # type: ignore[misc]
    async def async_client() -> Any:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            yield client

except ImportError:
    # Fallback if httpx/pytest_asyncio are not yet installed in the active environment
    pass


@pytest.fixture
def user_factory() -> Callable[..., User]:
    """Build consistent users for authentication and authorization tests."""

    def build_user(*, role: UserRole = UserRole.MEMBER, is_active: bool = True) -> User:
        now = datetime.now(UTC)
        return User(
            id=uuid.uuid4(),
            email=f"{uuid.uuid4().hex}@example.test",
            hashed_password="test-hash",
            full_name="Test User",
            role=role,
            is_active=is_active,
            created_at=now,
            updated_at=now,
        )

    return build_user
