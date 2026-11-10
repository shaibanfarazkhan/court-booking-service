"""DTOs for venue and court management."""

import uuid
from datetime import datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CourtType, SurfaceType


class VenueCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    slug: str = Field(
        min_length=1, max_length=160, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    )
    description: str | None = None
    address: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    postal_code: str = Field(min_length=1, max_length=20)
    opening_time: time
    closing_time: time


class VenueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    address: str
    city: str
    state: str
    postal_code: str
    opening_time: time
    closing_time: time
    is_active: bool
    created_at: datetime


class CourtCreate(BaseModel):
    venue_id: uuid.UUID
    sport_id: uuid.UUID
    name: str = Field(min_length=1, max_length=100)
    court_type: CourtType = CourtType.INDOOR
    surface_type: SurfaceType = SurfaceType.HARD
    base_price_per_hour: Decimal = Field(ge=0, max_digits=10, decimal_places=2)


class CourtResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    venue_id: uuid.UUID
    sport_id: uuid.UUID
    name: str
    court_type: CourtType
    surface_type: SurfaceType
    base_price_per_hour: Decimal
    is_active: bool
    created_at: datetime
