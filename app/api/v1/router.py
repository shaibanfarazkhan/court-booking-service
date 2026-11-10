from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.api.v1.auth import router as auth_router
from app.api.v1.courts import router as courts_router
from app.db.database import check_database_connection

api_router = APIRouter(prefix="/v1")

# Mount auth routes
api_router.include_router(auth_router)
api_router.include_router(courts_router)


@api_router.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Basic health check endpoint to verify service availability."""
    return {"status": "ok"}


@api_router.get("/health/db", tags=["Health"])
async def database_health_check() -> JSONResponse:
    """Database connectivity health check."""
    is_connected = await check_database_connection()
    if is_connected:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ok", "database": "connected"},
        )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "degraded", "database": "disconnected"},
    )
