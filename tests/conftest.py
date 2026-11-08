"""Pytest fixtures and configuration."""

from typing import Any

try:
    import httpx
    import pytest_asyncio

    from app.main import app

    @pytest_asyncio.fixture  # type: ignore[misc]
    async def async_client() -> Any:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            yield client

except ImportError:
    # Fallback if httpx/pytest_asyncio are not yet installed in the active environment
    pass
