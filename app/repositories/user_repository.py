"""User repository handling asynchronous database queries for user accounts."""

import uuid

from sqlalchemy import select

from app.db.session import AsyncSession
from app.models.enums import UserRole
from app.models.user import User


class UserRepository:
    """Repository interface for User entity persistence operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """Fetch a user by primary key UUID."""
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Fetch a user by unique lowercase email address."""
        stmt = select(User).where(User.email == email.strip().lower())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def exists_by_email(self, email: str) -> bool:
        """Check if an active account exists with the specified email."""
        user = await self.get_by_email(email)
        return user is not None

    async def create_user(
        self,
        email: str,
        hashed_password: str,
        full_name: str,
        phone_number: str | None = None,
        role: UserRole = UserRole.MEMBER,
    ) -> User:
        """Persist a new User record."""
        user = User(
            email=email.strip().lower(),
            hashed_password=hashed_password,
            full_name=full_name.strip(),
            phone_number=phone_number.strip() if phone_number else None,
            role=role,
            is_active=True,
        )
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)
        return user
