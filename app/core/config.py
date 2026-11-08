import os
from typing import Any

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    # Fallback to standard Pydantic BaseModel if pydantic-settings is not yet installed
    from pydantic import BaseModel

    class BaseSettings(BaseModel):  # type: ignore[no-redef]
        """Lightweight fallback settings container using os.environ."""

        def __init__(self, **values: Any) -> None:
            data = {}
            for field_name, field_info in self.__class__.model_fields.items():
                env_val = os.getenv(field_name)
                if env_val is not None:
                    # Basic type conversion for bool/int
                    if field_info.annotation is bool:
                        data[field_name] = env_val.lower() in ("true", "1", "yes")
                    elif field_info.annotation is int:
                        data[field_name] = int(env_val)
                    else:
                        data[field_name] = env_val
                elif field_name in values:
                    data[field_name] = values[field_name]
                else:
                    data[field_name] = field_info.default
            super().__init__(**data)

    SettingsConfigDict = dict  # type: ignore[misc, assignment]


class Settings(BaseSettings):
    """Application runtime configuration parsed from environment variables."""

    APP_NAME: str = "Court Booking Service"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # PostgreSQL configuration
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "court_booking_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Async Database connection URLs
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/court_booking_db"
    )
    TEST_DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/court_booking_test_db"
    )

    # Database connection pool tuning
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False

    # Security & JWT Configuration
    JWT_SECRET_KEY: str = "court-booking-jwt-secret-key-32-bytes-minimum-security-token"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Security & JWT Configuration
    JWT_SECRET_KEY: str = (
        "court-booking-jwt-secret-key-32-bytes-minimum-security-token"
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
