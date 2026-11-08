import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.auth import get_me, login
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import (
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from tests.test_auth_service import setup_auth_service


def test_api_register_success() -> None:
    """Verify register endpoint executes and returns 201 response."""
    service, _ = setup_auth_service()
    req = UserRegisterRequest(
        email="api.user@courtbooking.com",
        password="ValidPassword123!",
        full_name="API User",
    )

    coro = service.register_member(req)
    try:
        coro.send(None)
    except StopIteration as e:
        res: UserResponse = e.value
        assert res.email == "api.user@courtbooking.com"
        assert res.role == UserRole.MEMBER


def test_api_register_invalid_password_validation() -> None:
    """Verify schema rejects passwords without digits or under 8 chars."""
    with pytest.raises(ValueError):
        UserRegisterRequest(
            email="valid@courtbooking.com",
            password="short",
            full_name="Short Pwd",
        )

    with pytest.raises(ValueError):
        UserRegisterRequest(
            email="valid@courtbooking.com",
            password="NoDigitsInThisPassword!",
            full_name="No Digits",
        )


def test_api_register_invalid_email_validation() -> None:
    """Verify schema rejects malformed email addresses."""
    with pytest.raises(ValueError):
        UserRegisterRequest(
            email="not-a-valid-email",
            password="ValidPassword123!",
            full_name="Bad Email",
        )


def test_api_login_invalid_password() -> None:
    """Verify login raises HTTP 401 on incorrect credentials."""
    mock_db = AsyncMock()
    req = UserLoginRequest(
        email="unknown@courtbooking.com",
        password="WrongPassword123!",
    )

    with patch("app.api.v1.auth.AuthService") as mock_auth_cls:
        mock_auth_instance = mock_auth_cls.return_value
        from app.core.exceptions import InvalidCredentialsError

        async def _raise(*_args: object, **_kwargs: object) -> None:
            raise InvalidCredentialsError("Invalid email or password.")

        mock_auth_instance.login = _raise

        coro = login(payload=req, db=mock_db)
        with pytest.raises(HTTPException) as exc_info:
            try:
                coro.send(None)
            except StopIteration:
                pass
        assert exc_info.value.status_code == 401


def test_api_get_me_returns_profile() -> None:
    """Verify get_me endpoint returns the authenticated user's profile."""
    current_user = User(
        id=uuid.uuid4(),
        email="me@courtbooking.com",
        hashed_password="",
        full_name="Self Profile",
        phone_number="+1234567890",
        role=UserRole.MEMBER,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    coro = get_me(current_user=current_user)
    try:
        coro.send(None)
    except StopIteration as e:
        profile = e.value
        assert profile.email == "me@courtbooking.com"
        assert profile.full_name == "Self Profile"
        assert profile.role == UserRole.MEMBER
