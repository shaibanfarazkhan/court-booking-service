import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.dependencies import require_admin, require_member, require_staff
from app.core.exceptions import (
    AccountInactiveError,
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from app.core.security import create_refresh_token, hash_password
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import (
    TokenRefreshRequest,
    UserLoginRequest,
    UserRegisterRequest,
)
from app.services.auth_service import AuthService


class MockSession:
    """Mock async session for testing repository/service interactions."""

    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}
        self.users_by_email: dict[str, User] = {}

    def add(self, entity: User) -> None:
        if not entity.id:
            entity.id = uuid.uuid4()
        self.users[entity.id] = entity
        self.users_by_email[entity.email.lower()] = entity

    async def flush(self) -> None:
        pass

    async def refresh(self, _entity: User) -> None:
        pass

    async def execute(self, _stmt: object) -> MagicMock:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        return mock_result


class FakeUserRepository:
    """Mock user repository matching interface without real database."""

    def __init__(self, session: MockSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.session.users.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        return self.session.users_by_email.get(email.strip().lower())

    async def exists_by_email(self, email: str) -> bool:
        return email.strip().lower() in self.session.users_by_email

    async def create_user(
        self,
        email: str,
        hashed_password: str,
        full_name: str,
        phone_number: str | None = None,
        role: UserRole = UserRole.MEMBER,
    ) -> User:
        user = User(
            email=email.strip().lower(),
            hashed_password=hashed_password,
            full_name=full_name,
            phone_number=phone_number,
            role=role,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.session.add(user)
        return user


def setup_auth_service() -> tuple[AuthService, MockSession]:
    """Helper creating an AuthService backed by in-memory mock repository."""
    session = MockSession()
    service = AuthService(session=session)  # type: ignore[arg-type]
    service.user_repo = FakeUserRepository(session)  # type: ignore[assignment]
    return service, session


def test_register_member_success() -> None:
    """Verify new member registration persists user with MEMBER role."""
    service, _ = setup_auth_service()
    req = UserRegisterRequest(
        email="roger.federer@tennis.com",
        password="GrandSlamWinner2026!",
        full_name="Roger Federer",
        phone_number="+41791234567",
    )

    coro = service.register_member(req)
    try:
        coro.send(None)
    except StopIteration as e:
        user_res = e.value
        assert user_res.email == "roger.federer@tennis.com"
        assert user_res.full_name == "Roger Federer"
        assert user_res.role == UserRole.MEMBER
        assert user_res.is_active is True


def test_register_duplicate_email_raises_error() -> None:
    """Verify registration with duplicate email raises DuplicateEmailError."""
    service, session = setup_auth_service()
    existing_user = User(
        email="rafa.nadal@tennis.com",
        hashed_password=hash_password("Password123!"),
        full_name="Rafael Nadal",
        role=UserRole.MEMBER,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(existing_user)

    req = UserRegisterRequest(
        email="rafa.nadal@tennis.com",
        password="DifferentPassword456!",
        full_name="Rafa Nadal Duplicate",
    )

    coro = service.register_member(req)
    with pytest.raises(DuplicateEmailError):
        try:
            coro.send(None)
        except StopIteration as e:
            raise e.value from None


def test_login_success() -> None:
    """Verify login with correct credentials issues valid JWT token pair."""
    service, session = setup_auth_service()
    hashed = hash_password("ValidPassword123!")
    user = User(
        email="novak.djokovic@tennis.com",
        hashed_password=hashed,
        full_name="Novak Djokovic",
        role=UserRole.MEMBER,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(user)

    req = UserLoginRequest(
        email="novak.djokovic@tennis.com",
        password="ValidPassword123!",
    )

    coro = service.login(req)
    try:
        coro.send(None)
    except StopIteration as e:
        token_res = e.value
        assert token_res.access_token is not None
        assert token_res.refresh_token is not None
        assert token_res.token_type == "bearer"
        assert token_res.expires_in > 0


def test_login_invalid_credentials_raises_error() -> None:
    """Verify login with wrong password raises InvalidCredentialsError."""
    service, session = setup_auth_service()
    hashed = hash_password("CorrectPassword123!")
    user = User(
        email="carlos.alcaraz@tennis.com",
        hashed_password=hashed,
        full_name="Carlos Alcaraz",
        role=UserRole.MEMBER,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(user)

    req = UserLoginRequest(
        email="carlos.alcaraz@tennis.com",
        password="WrongPassword999!",
    )

    coro = service.login(req)
    with pytest.raises(InvalidCredentialsError):
        try:
            coro.send(None)
        except StopIteration as e:
            raise e.value from None


def test_login_inactive_user_raises_error() -> None:
    """Verify inactive account is blocked from logging in."""
    service, session = setup_auth_service()
    hashed = hash_password("Password123!")
    user = User(
        email="inactive.player@tennis.com",
        hashed_password=hashed,
        full_name="Inactive Player",
        role=UserRole.MEMBER,
        is_active=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(user)

    req = UserLoginRequest(
        email="inactive.player@tennis.com",
        password="Password123!",
    )

    coro = service.login(req)
    with pytest.raises(AccountInactiveError):
        try:
            coro.send(None)
        except StopIteration as e:
            raise e.value from None


def test_refresh_tokens_success() -> None:
    """Verify valid refresh token rotates access and refresh tokens."""
    service, session = setup_auth_service()
    user = User(
        email="serena.williams@tennis.com",
        hashed_password=hash_password("TennisQueen2026!"),
        full_name="Serena Williams",
        role=UserRole.MEMBER,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(user)

    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    req = TokenRefreshRequest(refresh_token=refresh_token)

    coro = service.refresh_tokens(req)
    try:
        coro.send(None)
    except StopIteration as e:
        token_res = e.value
        assert token_res.access_token is not None
        assert token_res.refresh_token is not None


def test_refresh_tokens_invalid_token_raises_error() -> None:
    """Verify invalid refresh token raises InvalidTokenError."""
    service, _ = setup_auth_service()
    req = TokenRefreshRequest(refresh_token="invalid.malformed.token")

    coro = service.refresh_tokens(req)
    with pytest.raises(InvalidTokenError):
        try:
            coro.send(None)
        except StopIteration as e:
            raise e.value from None


def test_role_dependencies() -> None:
    """Verify role guard dependencies for member, staff, and admin."""
    member_user = User(
        id=uuid.uuid4(),
        email="m@test.com",
        hashed_password="",
        full_name="Member",
        role=UserRole.MEMBER,
        is_active=True,
    )
    staff_user = User(
        id=uuid.uuid4(),
        email="s@test.com",
        hashed_password="",
        full_name="Staff",
        role=UserRole.STAFF,
        is_active=True,
    )
    admin_user = User(
        id=uuid.uuid4(),
        email="a@test.com",
        hashed_password="",
        full_name="Admin",
        role=UserRole.ADMIN,
        is_active=True,
    )

    # require_member accepts MEMBER, STAFF, ADMIN
    coro = require_member(member_user)
    try:
        coro.send(None)
    except StopIteration as e:
        assert e.value == member_user

    # require_staff blocks MEMBER
    coro = require_staff(member_user)
    with pytest.raises(HTTPException) as exc_info:
        try:
            coro.send(None)
        except StopIteration:
            pass
    assert exc_info.value.status_code == 403

    # require_staff allows STAFF and ADMIN
    coro = require_staff(staff_user)
    try:
        coro.send(None)
    except StopIteration as e:
        assert e.value == staff_user

    # require_admin blocks STAFF
    coro = require_admin(staff_user)
    with pytest.raises(HTTPException) as exc_info:
        try:
            coro.send(None)
        except StopIteration:
            pass
    assert exc_info.value.status_code == 403

    # require_admin allows ADMIN
    coro = require_admin(admin_user)
    try:
        coro.send(None)
    except StopIteration as e:
        assert e.value == admin_user
