"""Booking policy administration schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BookingPolicyInput(BaseModel):
    """Complete replacement for global booking limits."""

    daily_limit: int = Field(gt=0, le=100)
    weekly_limit: int = Field(gt=0, le=500)
    future_booking_limit: int = Field(gt=0, le=500)
    min_duration_minutes: int = Field(gt=0, le=1440)
    max_duration_minutes: int = Field(gt=0, le=1440)

    @model_validator(mode="after")
    def validate_duration_range(self) -> "BookingPolicyInput":
        if self.max_duration_minutes < self.min_duration_minutes:
            raise ValueError(
                "max_duration_minutes must be at least min_duration_minutes"
            )
        return self


class BookingPolicyResponse(BaseModel):
    """Active booking policy returned to administrators."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    active: bool
    daily_limit: int
    weekly_limit: int
    future_booking_limit: int
    min_duration_minutes: int
    max_duration_minutes: int
    created_at: datetime
    updated_at: datetime
