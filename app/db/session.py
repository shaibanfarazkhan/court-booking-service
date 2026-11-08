"""Asynchronous session factory and FastAPI database dependency injection."""

from collections.abc import AsyncGenerator
from typing import Any

try:
    from sqlalchemy.ext.asyncio import (
        AsyncEngine,
        AsyncSession,
        async_sessionmaker,
    )
except ImportError:
    AsyncEngine = Any  # type: ignore[misc, assignment]
    AsyncSession = Any  # type: ignore[misc, assignment]

    def async_sessionmaker(*_args: Any, **_kwargs: Any) -> Any:  # type: ignore[misc]
        msg = (
            "SQLAlchemy asyncio requires 'greenlet'. Run: pip install -r"
            " requirements.txt"
        )
        raise RuntimeError(msg)


from app.db.database import engine


def build_session_factory(
    target_engine: AsyncEngine | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Create an async_sessionmaker bound to the given or default AsyncEngine."""
    active_engine = target_engine or engine
    return async_sessionmaker(
        bind=active_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


# Default application session maker
async_session_factory: async_sessionmaker[AsyncSession] | None
try:
    async_session_factory = build_session_factory(engine)
except Exception:
    async_session_factory = None  # type: ignore[assignment]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an isolated transaction-aware AsyncSession.

    - Commits the transaction if the endpoint executes without exceptions.
    - Rolls back the transaction if an unhandled exception is raised.
    - Closes the session connection back to the connection pool on exit.
    """
    if async_session_factory is None:
        raise RuntimeError("Database session factory is not configured.")

    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
