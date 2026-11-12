"""Pydantic DTOs for venue, court, and recurring availability management."""

import uuid
from datetime import datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import SurfaceType


class VenueCreate(BaseModel):
    """Fields needed to register a venue."""

    model_config = ConfigDict(
        title="Venue Creation Request",
        json_schema_extra={
            "examples": [
                {
                    "name": "Central Sports Club",
                    "address": "10 Main Road",
                    "city": "Hyderabad",
                    "state": "Telangana",
                    "country": "India",
                    "timezone": "Asia/Kolkata",
                    "postal_code": "500001",
                    "opening_time": "06:00:00",
                    "closing_time": "22:00:00",
                }
            ]
        },
    )

    name: str = Field(min_length=1, max_length=150)
    address: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    country: str = Field(min_length=1, max_length=100)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    postal_code: str = Field(min_length=1, max_length=20)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    slug: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    opening_time: time = time(0, 0)
    closing_time: time = time(23, 59)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def validate_hours(self) -> "VenueCreate":
        if self.closing_time <= self.opening_time:
            raise ValueError("closing_time must be after opening_time")
        return self


class VenuePatch(BaseModel):
    """Fields that can be changed on an existing venue."""

    model_config = ConfigDict(
        title="Venue Update Request",
        json_schema_extra={"examples": [{"description": "Updated club facilities"}]},
    )

    name: str | None = Field(default=None, min_length=1, max_length=150)
    address: str | None = Field(default=None, min_length=1, max_length=255)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    state: str | None = Field(default=None, min_length=1, max_length=100)
    country: str | None = Field(default=None, min_length=1, max_length=100)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    postal_code: str | None = Field(default=None, min_length=1, max_length=20)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    slug: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    opening_time: time | None = None
    closing_time: time | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_null_required_fields(cls, values: object) -> object:
        if isinstance(values, dict):
            nullable = {"latitude", "longitude", "description"}
            for field_name, value in values.items():
                if value is None and field_name not in nullable:
                    raise ValueError(f"{field_name} cannot be null")
        return values

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def validate_hours(self) -> "VenuePatch":
        if self.opening_time is not None and self.closing_time is not None:
            if self.closing_time <= self.opening_time:
                raise ValueError("closing_time must be after opening_time")
        return self


class VenueResponse(BaseModel):
    """Public venue representation."""

    model_config = ConfigDict(from_attributes=True, title="Venue")

    id: uuid.UUID
    name: str
    address: str
    city: str
    state: str
    country: str
    timezone: str
    postal_code: str
    latitude: Decimal | None
    longitude: Decimal | None
    slug: str
    description: str | None
    opening_time: time
    closing_time: time
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CourtCreate(BaseModel):
    """Fields needed to register a court."""

    model_config = ConfigDict(
        title="Court Creation Request",
        json_schema_extra={
            "examples": [
                {
                    "venue_id": "00000000-0000-0000-0000-000000000001",
                    "name": "Court 1",
                    "sport_type": "Tennis",
                    "surface_type": "HARD",
                    "indoor": False,
                    "base_price_per_hour": "750.00",
                }
            ]
        },
    )

    venue_id: uuid.UUID
    name: str = Field(min_length=1, max_length=100)
    sport_type: str = Field(min_length=1, max_length=100)
    surface_type: SurfaceType
    indoor: bool
    active: bool = True
    base_price_per_hour: Decimal = Field(
        default=Decimal("0.00"), ge=0, max_digits=10, decimal_places=2
    )

    @field_validator("sport_type")
    @classmethod
    def normalize_sport_type(cls, value: str) -> str:
        return value.strip()


class CourtPatch(BaseModel):
    """Fields that can be changed on an existing court."""

    model_config = ConfigDict(
        title="Court Update Request",
        json_schema_extra={
            "examples": [{"base_price_per_hour": "800.00", "active": True}]
        },
    )

    venue_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sport_type: str | None = Field(default=None, min_length=1, max_length=100)
    surface_type: SurfaceType | None = None
    indoor: bool | None = None
    active: bool | None = None
    base_price_per_hour: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )

    @model_validator(mode="before")
    @classmethod
    def reject_null_fields(cls, values: object) -> object:
        if isinstance(values, dict) and any(value is None for value in values.values()):
            raise ValueError("Court fields cannot be null")
        return values


class CourtResponse(BaseModel):
    """Public court representation."""

    model_config = ConfigDict(from_attributes=True, title="Court")

    id: uuid.UUID
    venue_id: uuid.UUID
    name: str
    sport_type: str
    surface_type: SurfaceType
    indoor: bool
    active: bool
    base_price_per_hour: Decimal
    created_at: datetime
    updated_at: datetime


class AvailabilityCreate(BaseModel):
    """Fields for adding a recurring weekly availability window."""

    model_config = ConfigDict(
        title="Recurring Availability Request",
        json_schema_extra={
            "examples": [
                {
                    "court_id": "00000000-0000-0000-0000-000000000002",
                    "weekday": 0,
                    "start_time": "09:00:00",
                    "end_time": "10:00:00",
                    "available": True,
                }
            ]
        },
    )

    court_id: uuid.UUID
    weekday: int = Field(ge=0, le=6, description="Monday=0 through Sunday=6")
    start_time: time
    end_time: time
    available: bool = True

    @model_validator(mode="after")
    def validate_time_range(self) -> "AvailabilityCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AvailabilityPatch(BaseModel):
    """Fields that can be changed on a weekly availability window."""

    model_config = ConfigDict(
        title="Availability Update Request",
        json_schema_extra={
            "examples": [{"start_time": "10:00:00", "end_time": "11:00:00"}]
        },
    )

    court_id: uuid.UUID | None = None
    weekday: int | None = Field(default=None, ge=0, le=6)
    start_time: time | None = None
    end_time: time | None = None
    available: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_null_fields(cls, values: object) -> object:
        if isinstance(values, dict) and any(value is None for value in values.values()):
            raise ValueError("Availability fields cannot be null")
        return values


class AvailabilityResponse(BaseModel):
    """Recurring availability representation."""

    model_config = ConfigDict(from_attributes=True, title="Recurring Availability")

    id: uuid.UUID
    court_id: uuid.UUID
    weekday: int
    start_time: time
    end_time: time
    available: bool
    created_at: datetime
    updated_at: datetime
