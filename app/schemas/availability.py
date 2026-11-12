"""Public response DTOs for searchable bookable time slots."""

import uuid
from datetime import date, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import SlotStatus

AvailabilitySort = Literal["time", "venue", "court"]


class AvailabilitySlotResponse(BaseModel):
    """Public, minimal representation of an available court time slot."""

    model_config = ConfigDict(from_attributes=True, title="Available Court Slot")

    slot_id: uuid.UUID
    court_id: uuid.UUID
    court_name: str
    venue_id: uuid.UUID
    venue_name: str
    sport: str
    date: date
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time
    status: SlotStatus
    price: Decimal
    available: bool


class AvailabilitySearchResponse(BaseModel):
    """Paginated public availability search results."""

    model_config = ConfigDict(title="Availability Search Results")

    items: list[AvailabilitySlotResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
