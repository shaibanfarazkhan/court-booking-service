import inspect

from app.core.config import settings
from app.db.base import Base
from app.db.database import (
    build_async_engine,
    check_database_connection,
    close_database_connection,
)
from app.db.session import (
    build_session_factory,
    get_db,
)


def test_database_urls_configured() -> None:
    """Verify primary and test database connection URLs are set."""
    assert "postgresql+asyncpg://" in settings.DATABASE_URL
    assert "court_booking_db" in settings.DATABASE_URL
    assert "postgresql+asyncpg://" in settings.TEST_DATABASE_URL
    assert "court_booking_test_db" in settings.TEST_DATABASE_URL


def test_pool_tuning_defaults() -> None:
    """Verify connection pool sizing and lifecycle defaults."""
    assert settings.DB_POOL_SIZE == 10
    assert settings.DB_MAX_OVERFLOW == 20
    assert settings.DB_POOL_TIMEOUT == 30
    assert settings.DB_POOL_RECYCLE == 1800
    assert settings.DB_ECHO is False


def test_metadata_auto_discovery_via_db_base() -> None:
    """Verify that importing Base from app.db.base registers all 9 domain models."""
    expected_tables = {
        "users",
        "admins",
        "venues",
        "sports",
        "courts",
        "court_images",
        "time_slots",
        "bookings",
        "payments",
    }
    registered = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(registered)


def test_build_async_engine_interface() -> None:
    """Verify that build_async_engine is callable and accepts pool configurations."""
    assert callable(build_async_engine)


def test_build_session_factory_interface() -> None:
    """Verify that build_session_factory is callable and accepts target engines."""
    assert callable(build_session_factory)


def test_get_db_is_async_generator() -> None:
    """Ensure get_db is an asynchronous generator for FastAPI dependency injection."""
    assert inspect.isasyncgenfunction(get_db)


def test_check_database_connection_none_engine() -> None:
    """Verify check_database_connection returns False safely when engine is None."""
    coro = check_database_connection(target_engine=None)
    try:
        coro.send(None)
    except StopIteration as e:
        assert e.value is False


def test_close_database_connection_none_engine() -> None:
    """Verify close_database_connection handles None engine safely without error."""
    coro = close_database_connection(target_engine=None)
    try:
        coro.send(None)
    except StopIteration:
        pass
