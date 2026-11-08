"""Authentication and account lifecycle domain service."""

import uuid

from app.core.config import settings
from app.core.exceptions import (
    AccountInactiveError,
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidTokenError,
    UserNotFoundError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import AsyncSession
from app.models.enums import UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    TokenRefreshRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)


class AuthService:
    """Service orchestrating authentication, registration, and token rotation."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)

    async def register_member(
        self,
        request: UserRegisterRequest,
    ) -> UserResponse:
        """Register a new customer account with the MEMBER role."""
        if await self.user_repo.exists_by_email(request.email):
            raise DuplicateEmailError(
                f"An account with email '{request.email}' already exists."
            )

        hashed_pwd = hash_password(request.password)
        user = await self.user_repo.create_user(
            email=request.email,
            hashed_password=hashed_pwd,
            full_name=request.full_name,
            phone_number=request.phone_number,
            role=UserRole.MEMBER,
        )
        return UserResponse.model_validate(user)

    async def login(self, request: UserLoginRequest) -> TokenResponse:
        """Authenticate user credentials and issue access + refresh tokens."""
        user = await self.user_repo.get_by_email(request.email)
        if user is None or not verify_password(request.password, user.hashed_password):
            raise InvalidCredentialsError("Invalid email or password.")

        if not user.is_active:
            raise AccountInactiveError("This account is currently deactivated.")

        token_payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": str(user.role.value),
        }
        access_token = create_access_token(data=token_payload)
        refresh_token = create_refresh_token(data={"sub": str(user.id)})

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh_tokens(
        self,
        request: TokenRefreshRequest,
    ) -> TokenResponse:
        """Rotate tokens using a valid refresh token."""
        try:
            payload = decode_token(request.refresh_token)
        except Exception as e:
            raise InvalidTokenError("Invalid or expired refresh token.") from e

        if payload.get("type") != "refresh":
            raise InvalidTokenError("Provided token is not a refresh token.")

        sub = payload.get("sub")
        if not sub:
            raise InvalidTokenError("Refresh token missing subject identifier.")

        try:
            user_id = uuid.UUID(sub)
        except ValueError as e:
            raise InvalidTokenError("Malformed subject identifier.") from e

        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError("User associated with token not found.")

        if not user.is_active:
            raise AccountInactiveError("This account is currently deactivated.")

        token_payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": str(user.role.value),
        }
        new_access_token = create_access_token(data=token_payload)
        new_refresh_token = create_refresh_token(data={"sub": str(user.id)})

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def get_user_profile(self, user_id: uuid.UUID) -> UserResponse:
        """Retrieve the public user profile."""
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError("User profile not found.")
        return UserResponse.model_validate(user)
