from app.api.v1.router import api_router
from app.core.config import settings
from app.main import app


def test_settings_initialization() -> None:
    """Verify application configuration loads default settings correctly."""
    assert settings.APP_NAME == "Court Booking Service"
    assert settings.PORT == 8000
    assert "court_booking_db" in settings.DATABASE_URL


def test_app_initialization() -> None:
    """Verify FastAPI application boots and registers routes properly."""
    assert app.title == "Court Booking Service"
    assert str(app.url_path_for("health_check")) == "/api/v1/health"
    assert str(app.url_path_for("database_health_check")) == "/api/v1/health/db"


def test_health_check_payload() -> None:
    """Verify health check router registration."""
    assert api_router.prefix == "/v1"
