from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings


def create_application() -> FastAPI:
    """Application factory for Court Booking Service."""
    application = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    application.include_router(api_router, prefix="/api")

    return application


app = create_application()

