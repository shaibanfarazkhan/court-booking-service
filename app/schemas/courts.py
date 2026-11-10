"""Pydantic DTOs for venue, court, and recurring availability management."""

import uuid
from datetime import datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import SurfaceType


class VenueCreate(BaseModel):
    """Fields needed to register a venue."""

    name: str = Field(min_length=1, max_length=150)
    address: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    country: str = Field(min_length=1, max_length=100)
    postal_code: str = Field(min_length=1, max_length=20)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    slug: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    opening_time: time = time(0, 0)
    closing_time: time = time(23, 59)

    @model_validator(mode="after")
    def validate_hours(self) -> "VenueCreate":
        if self.closing_time <= self.opening_time:
            raise ValueError("closing_time must be after opening_time")
        return self


class VenuePatch(BaseModel):
    """Fields that can be changed on an existing venue."""

    name: str | None = Field(default=None, min_length=1, max_length=150)
    address: str | None = Field(default=None, min_length=1, max_length=255)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    state: str | None = Field(default=None, min_length=1, max_length=100)
    country: str | None = Field(default=None, min_length=1, max_length=100)
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

    @model_validator(mode="after")
    def validate_hours(self) -> "VenuePatch":
        if self.opening_time is not None and self.closing_time is not None:
            if self.closing_time <= self.opening_time:
                raise ValueError("closing_time must be after opening_time")
        return self


class VenueResponse(BaseModel):
    """Public venue representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    address: str
    city: str
    state: str
    country: str
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

    model_config = ConfigDict(from_attributes=True)

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

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    court_id: uuid.UUID
    weekday: int
    start_time: time
    end_time: time
    available: bool
    created_at: datetime
    updated_at: datetime
