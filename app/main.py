import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.database import (
    check_database_connection,
    close_database_connection,
)
from app.db.session import async_session_factory
from app.services.booking_service import BookingService

logger = logging.getLogger(__name__)
HOLD_EXPIRATION_INTERVAL_SECONDS = 60


async def _expire_booking_holds_periodically() -> None:
    """Periodically release holds whose 15-minute deadline has elapsed."""
    if async_session_factory is None:
        logger.warning(
            "Booking hold expiration worker is disabled without a DB session"
        )
        return

    while True:
        try:
            async with async_session_factory() as session:
                async with session.begin():
                    expired_count = await BookingService(session).expire_old_holds()
            if expired_count:
                logger.info("Expired %d booking holds", expired_count)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Booking hold expiration run failed")
        await asyncio.sleep(HOLD_EXPIRATION_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager handling startup validation and graceful shutdown."""
    # Startup: attempt database connectivity check
    await check_database_connection()
    expiration_task = asyncio.create_task(_expire_booking_holds_periodically())
    try:
        yield
    finally:
        expiration_task.cancel()
        try:
            await expiration_task
        except asyncio.CancelledError:
            pass
        # Shutdown: dispose connection pool
        await close_database_connection()


def create_application() -> FastAPI:
    """Application factory for Court Booking Service."""
    application = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    application.include_router(api_router, prefix="/api")

    return application


app = create_application()
