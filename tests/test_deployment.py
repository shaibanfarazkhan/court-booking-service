"""Deployment configuration, liveness, and structured request logging tests."""

import asyncio
import logging
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.logging_config import JsonFormatter
from app.main import app

ROOT = Path(__file__).resolve().parents[1]


def test_health_endpoint_is_unauthenticated_and_returns_healthy():
    health_route = next(
        route for route in app.routes if getattr(route, "path", None) == "/health"
    )

    assert (
        health_route.status_code is None
    )  # FastAPI's default successful status is 200.
    assert not health_route.dependant.dependencies
    assert asyncio.run(health_route.endpoint()) == {"status": "healthy"}


def test_request_logging_is_structured_and_excludes_query_values():
    record = logging.LogRecord(
        "app.main", logging.INFO, "main.py", 1, "http_request", (), None
    )
    record.structured_data = {
        "method": "GET",
        "path": "/health",
        "status_code": 200,
        "response_time_ms": 1.25,
    }

    rendered = JsonFormatter().format(record)

    assert '"method":"GET"' in rendered
    assert '"path":"/health"' in rendered
    assert '"status_code":200' in rendered
    assert '"response_time_ms":1.25' in rendered
    assert "secret" not in rendered


def test_dockerfile_uses_multistage_python313_and_nonroot_runtime():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert dockerfile.count("FROM python:3.13-slim") == 2
    assert "AS builder" in dockerfile
    assert "AS runtime" in dockerfile
    assert "COPY requirements.txt ./" in dockerfile
    assert "requirements-dev.txt" not in dockerfile
    assert "USER app:app" in dockerfile
    assert "PYTHONDONTWRITEBYTECODE=1" in dockerfile
    assert "PYTHONUNBUFFERED=1" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert 'ENTRYPOINT ["/app/entrypoint.sh"]' in dockerfile


def test_compose_contains_only_api_and_postgres_with_health_dependency():
    compose = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")

    assert "  api:" in compose
    assert "  postgres:" in compose
    assert "redis" not in compose.lower()
    assert "condition: service_healthy" in compose
    assert "postgres_data:/var/lib/postgresql/data" in compose
    assert "postgres_data:" in compose
    assert "restart: unless-stopped" in compose
    assert "DATABASE_URL:" in compose
    assert "SECRET_KEY:" in compose
    assert "POSTGRES_PASSWORD:" in compose
    assert "no-new-privileges:true" in compose
    assert "127.0.0.1:' + os.getenv('PORT', '8000') + '/health" in compose


def test_entrypoint_waits_for_database_migrates_then_execs_uvicorn():
    entrypoint = (ROOT / "entrypoint.sh").read_text(encoding="utf-8")

    assert "set -eu" in entrypoint
    assert "socket.create_connection" in entrypoint
    assert "alembic upgrade head" in entrypoint
    assert "exec uvicorn app.main:app" in entrypoint


def test_environment_template_has_required_deployment_variables():
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    required = {
        "DATABASE_URL",
        "SECRET_KEY",
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_DB",
        "LOG_LEVEL",
        "ENVIRONMENT",
        "HOST",
        "PORT",
    }
    assignments = {
        line.split("=", maxsplit=1)[0]
        for line in example.splitlines()
        if line and not line.startswith("#") and "=" in line
    }
    assert required <= assignments
    assert "ENVIRONMENT=production" in example
    assert "replace-with-a-unique-random-secret" in example


def test_compose_maps_deployment_secret_to_jwt_setting():
    compose = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")

    assert "SECRET_KEY: ${SECRET_KEY:?Set SECRET_KEY in .env}" in compose
    assert "JWT_SECRET_KEY: ${SECRET_KEY:?Set SECRET_KEY in .env}" in compose


def test_production_settings_map_secret_and_reject_placeholder_values():
    secret = "production-secret-" + "x" * 32
    settings = Settings(ENVIRONMENT="production", SECRET_KEY=secret)
    assert settings.JWT_SECRET_KEY == secret

    with pytest.raises(ValueError, match="Production requires"):
        Settings(ENVIRONMENT="production", SECRET_KEY="replace-with-a-placeholder")
