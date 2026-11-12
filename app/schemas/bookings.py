"""Pydantic request and response DTOs for booking holds."""

import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.enums import BookingStatus, RecurrenceType


class BookingHoldRequest(BaseModel):
    """Request a temporary hold on an available time slot."""

    model_config = ConfigDict(
        title="Booking Hold Request",
        json_schema_extra={
            "examples": [{"time_slot_id": "00000000-0000-4000-8000-000000000001"}]
        },
    )

    time_slot_id: uuid.UUID = Field(
        description="UUID of an available time slot to hold."
    )


class BookingResponse(BaseModel):
    """Booking data exposed to its owner."""

    model_config = ConfigDict(from_attributes=True, title="Booking")

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

    model_config = ConfigDict(title="Booking List")

    items: list[BookingResponse] = Field(description="Bookings on this page.")
    skip: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)


class RecurringBookingRequest(BaseModel):
    """Create confirmed bookings on dates matching a daily or weekly pattern."""

    model_config = ConfigDict(
        title="Recurring Booking Request",
        json_schema_extra={
            "examples": [
                {
                    "court_id": "00000000-0000-4000-8000-000000000002",
                    "start_date": "2026-12-01",
                    "end_date": "2026-12-15",
                    "start_time": "10:00:00",
                    "end_time": "11:00:00",
                    "recurrence_type": "WEEKLY",
                    "timezone": "Asia/Kolkata",
                    "idempotency_key": "member-series-20261201",
                }
            ]
        },
    )

    court_id: uuid.UUID = Field(description="Court where occurrences are requested.")
    start_date: date = Field(description="First eligible local calendar date.")
    end_date: date = Field(description="Last eligible local calendar date, inclusive.")
    start_time: time = Field(description="Local start time for each occurrence.")
    end_time: time = Field(description="Local end time for each occurrence.")
    recurrence_type: RecurrenceType = Field(
        description="Occurrence pattern: DAILY or WEEKLY."
    )
    timezone: str = Field(
        default="UTC", description="IANA timezone for the court times."
    )
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        description="Optional key used to safely retry the same series request.",
    )

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
