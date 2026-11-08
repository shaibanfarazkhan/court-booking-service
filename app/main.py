from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.database import (
    check_database_connection,
    close_database_connection,
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager handling startup validation and graceful shutdown."""
    # Startup: attempt database connectivity check
    await check_database_connection()
    yield
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
