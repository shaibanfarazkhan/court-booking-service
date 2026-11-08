from fastapi import APIRouter

api_router = APIRouter(prefix="/v1")


@api_router.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Basic health check endpoint to verify service availability."""
    return {"status": "ok"}

