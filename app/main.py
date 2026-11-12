import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.db.database import (
    check_database_connection,
    close_database_connection,
)
from app.db.session import async_session_factory
from app.services.booking_service import BookingService

logger = logging.getLogger(__name__)
HOLD_EXPIRATION_INTERVAL_SECONDS = 60
configure_logging(settings.LOG_LEVEL)


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

    @application.middleware("http")
    async def log_request(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        started_at = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.error(
                "http_request_failed",
                extra={
                    "structured_data": {
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": 500,
                        "response_time_ms": round(
                            (perf_counter() - started_at) * 1000, 2
                        ),
                    }
                },
            )
            raise
        logger.info(
            "http_request",
            extra={
                "structured_data": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "response_time_ms": round((perf_counter() - started_at) * 1000, 2),
                }
            },
        )
        return response

    @application.get("/health", tags=["Health"], name="liveness_health_check")
    async def liveness_health_check() -> dict[str, str]:
        """Unauthenticated process liveness endpoint for container probes."""
        return {"status": "healthy"}

    application.include_router(api_router, prefix="/api")

    return application


app = create_application()
