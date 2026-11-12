"""Pydantic schemas for authentication and user accounts."""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import UserRole


class UserRegisterRequest(BaseModel):
    """Payload for registering a new user account."""

    model_config = ConfigDict(
        title="Member Registration Request",
        json_schema_extra={
            "examples": [
                {
                    "email": "member@example.com",
                    "password": "CourtPlay123",
                    "full_name": "Court Member",
                    "phone_number": "+15550102030",
                }
            ]
        },
    )

    email: str = Field(
        ..., max_length=255, description="Unique email address for the account."
    )
    password: str = Field(
        ...,
        min_length=8,
        description=(
            "Password between 8 and 72 bytes with at least one letter and one number"
        ),
    )
    full_name: str = Field(
        ..., min_length=2, max_length=150, description="Member's display name."
    )
    phone_number: str | None = Field(
        default=None, max_length=30, description="Optional contact phone number."
    )

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

    model_config = ConfigDict(
        title="Login Request",
        json_schema_extra={
            "examples": [{"email": "member@example.com", "password": "CourtPlay123"}]
        },
    )

    email: str = Field(..., max_length=255, description="Registered account email.")
    password: str = Field(..., min_length=1, description="Account password.")

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

    model_config = ConfigDict(
        title="Token Refresh Request",
        json_schema_extra={"examples": [{"refresh_token": "<signed-refresh-token>"}]},
    )

    refresh_token: str = Field(
        ..., min_length=10, description="Previously issued refresh token."
    )


class TokenResponse(BaseModel):
    """Response containing signed authentication tokens."""

    model_config = ConfigDict(
        title="JWT Token Pair",
        json_schema_extra={
            "examples": [
                {
                    "access_token": "<signed-access-token>",
                    "refresh_token": "<signed-refresh-token>",
                    "token_type": "bearer",
                    "expires_in": 1800,
                }
            ]
        },
    )

    access_token: str = Field(description="Short-lived signed access token.")
    refresh_token: str = Field(description="Longer-lived token used for rotation.")
    token_type: str = Field(default="bearer", description="Authorization scheme.")
    expires_in: int = Field(description="Access-token lifetime in seconds.")


class UserResponse(BaseModel):
    """Public user profile data transfer object."""

    model_config = ConfigDict(
        from_attributes=True,
        title="User Profile",
        json_schema_extra={
            "examples": [
                {
                    "id": "00000000-0000-4000-8000-000000000010",
                    "email": "member@example.com",
                    "full_name": "Court Member",
                    "phone_number": None,
                    "role": "MEMBER",
                    "is_active": True,
                    "created_at": "2026-12-01T10:00:00Z",
                }
            ]
        },
    )

    id: uuid.UUID
    email: str
    full_name: str
    phone_number: str | None = None
    role: UserRole
    is_active: bool
    created_at: datetime
