"""Pydantic request and response DTOs for booking holds."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import BookingStatus


class BookingHoldRequest(BaseModel):
    """Request a temporary hold on an available time slot."""

    time_slot_id: uuid.UUID


class BookingResponse(BaseModel):
    """Booking data exposed to its owner."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    booking_reference: str
    user_id: uuid.UUID
    court_id: uuid.UUID
    time_slot_id: uuid.UUID
    status: BookingStatus
    total_amount: Decimal
    hold_expires_at: datetime | None
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class BookingListResponse(BaseModel):
    """Paginated list of a user's bookings."""

    items: list[BookingResponse]
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
