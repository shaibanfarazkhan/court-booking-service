"""Pydantic request and response DTOs for booking holds."""

import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import BookingStatus, RecurrenceType


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
    refund_eligible: bool
    created_at: datetime
    updated_at: datetime


class BookingListResponse(BaseModel):
    """Paginated list of a user's bookings."""

    items: list[BookingResponse]
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)


class RecurringBookingRequest(BaseModel):
    """Create confirmed bookings on dates matching a daily or weekly pattern."""

    court_id: uuid.UUID
    start_date: date
    end_date: date
    start_time: time
    end_time: time
    recurrence_type: RecurrenceType
    timezone: str = "UTC"
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_local_time(cls, value: time) -> time:
        if value.tzinfo is not None:
            raise ValueError("start_time and end_time must be local wall times")
        return value

    @model_validator(mode="after")
    def validate_recurrence_range(self) -> "RecurringBookingRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.end_date - self.start_date >= timedelta(days=90):
            raise ValueError("recurrence duration cannot exceed 90 days")
        if self.start_time >= self.end_time:
            raise ValueError("end_time must be after start_time")
        return self


class SkippedOccurrence(BaseModel):
    """An occurrence omitted because the court cannot fulfill it."""

    date: date
    reason: str


class RecurringBookingResponse(BaseModel):
    """Created booking records and occurrence-level skip explanations."""

    recurring_group_id: uuid.UUID
    created_bookings: list[BookingResponse]
    skipped_occurrences: list[SkippedOccurrence]
