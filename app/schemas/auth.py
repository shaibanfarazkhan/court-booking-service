"""Pydantic schemas for authentication and user accounts."""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import UserRole


class UserRegisterRequest(BaseModel):
    """Payload for registering a new user account."""

    email: str = Field(..., max_length=255, description="Unique email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=72,
        description=(
            "Password between 8 and 72 bytes with at least one letter and one number"
        ),
    )
    full_name: str = Field(..., min_length=2, max_length=150)
    phone_number: str | None = Field(default=None, max_length=30)

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        cleaned = value.strip().lower()
        email_regex = r"^[\w\.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_regex, cleaned):
            raise ValueError("Invalid email format")
        return cleaned

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password cannot be longer than 72 bytes")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain at least one numeric digit")
        if not any(char.isalpha() for char in value):
            raise ValueError("Password must contain at least one letter")
        return value


class UserLoginRequest(BaseModel):
    """Payload for authenticating and obtaining tokens."""

    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=1, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password_length(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password cannot be longer than 72 bytes")
        return value


class TokenRefreshRequest(BaseModel):
    """Payload for refreshing an expired access token."""

    refresh_token: str = Field(..., min_length=10)


class TokenResponse(BaseModel):
    """Response containing signed authentication tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """Public user profile data transfer object."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    phone_number: str | None = None
    role: UserRole
    is_active: bool
    created_at: datetime
