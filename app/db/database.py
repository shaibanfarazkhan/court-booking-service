"""SQLAlchemy 2.0 Async Engine and Connection Management."""

import logging
from typing import Any

from sqlalchemy import text

try:
    from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
except ImportError:
    AsyncEngine = Any  # type: ignore[misc, assignment]

    def create_async_engine(*_args: Any, **_kwargs: Any) -> Any:  # type: ignore[misc]
        msg = (
            "SQLAlchemy asyncio requires 'greenlet'. Run: pip install -r"
            " requirements.txt"
        )
        raise RuntimeError(msg)


from app.core.config import settings

logger = logging.getLogger(__name__)


def build_async_engine(database_url: str | None = None, **kwargs: Any) -> AsyncEngine:
    """Build a production-tuned SQLAlchemy AsyncEngine with connection pooling."""
    url = database_url or settings.DATABASE_URL
    engine_kwargs: dict[str, Any] = {
        "echo": settings.DB_ECHO,
        "pool_pre_ping": True,
        "pool_recycle": settings.DB_POOL_RECYCLE,
    }

    if "sqlite" not in url:
        engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
        engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
        engine_kwargs["pool_timeout"] = settings.DB_POOL_TIMEOUT

    engine_kwargs.update(kwargs)
    return create_async_engine(url, **engine_kwargs)


# Lazy / safely initialized global engine
engine: AsyncEngine
try:
    engine = build_async_engine()
except Exception as e:
    logger.warning("Could not initialize global AsyncEngine: %s", e)
    engine = None  # type: ignore[assignment]


async def check_database_connection(
    target_engine: AsyncEngine | None = None,
) -> bool:
    """Ping the database by executing `SELECT 1` to verify connectivity."""
    active_engine = target_engine or engine
    if active_engine is None:
        return False
    try:
        async with active_engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            scalar = result.scalar()
            is_healthy = scalar == 1
            if is_healthy:
                logger.info("Database connectivity check succeeded.")
            return bool(is_healthy)
    except Exception as exc:
        logger.warning("Database connectivity check failed: %s", exc)
        return False


async def close_database_connection(
    target_engine: AsyncEngine | None = None,
) -> None:
    """Dispose the database connection pool gracefully during shutdown."""
    active_engine = target_engine or engine
    if active_engine is None:
        return
    logger.info("Disposing database connection pool...")
    await active_engine.dispose()
    logger.info("Database connection pool disposed.")
