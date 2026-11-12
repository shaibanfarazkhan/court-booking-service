"""Response models and date validation for weekly utilization reports."""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReportDateRange(BaseModel):
    """Inclusive report date range capped at 31 calendar days."""

    model_config = ConfigDict(
        title="Report Date Range",
        json_schema_extra={
            "examples": [{"start_date": "2026-11-02", "end_date": "2026-11-08"}]
        },
    )

    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_range(self) -> "ReportDateRange":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if (self.end_date - self.start_date).days > 30:
            raise ValueError("date range cannot exceed 31 days")
        return self


class DailyUtilization(BaseModel):
    """Utilization totals for one calendar day."""

    model_config = ConfigDict(title="Daily Utilization")
    date: date
    booked_slots: int = Field(ge=0)
    available_slots: int = Field(ge=0)
    utilization_percent: Decimal = Field(ge=0, le=100)


class CourtUtilization(BaseModel):
    """Utilization and estimated revenue for one court."""

    model_config = ConfigDict(title="Court Utilization")
    court_id: uuid.UUID
    court_name: str
    venue_name: str
    sport: str
    total_slots: int = Field(ge=0)
    booked_slots: int = Field(ge=0)
    available_slots: int = Field(ge=0)
    utilization_percent: Decimal = Field(ge=0, le=100)
    estimated_revenue: Decimal = Field(ge=0)


class UtilizationSummary(BaseModel):
    """Aggregate utilization values across the report range."""

    model_config = ConfigDict(title="Utilization Summary")
    total_courts: int = Field(ge=0)
    total_slots: int = Field(ge=0)
    booked_slots: int = Field(ge=0)
    available_slots: int = Field(ge=0)
    cancelled_bookings: int = Field(ge=0)
    confirmed_bookings: int = Field(ge=0)
    utilization_percent: Decimal = Field(ge=0, le=100)
    average_daily_utilization: Decimal = Field(ge=0, le=100)
    estimated_revenue: Decimal = Field(ge=0)


class WeeklyUtilizationReport(BaseModel):
    """Complete weekly utilization report with daily and court breakdowns."""

    model_config = ConfigDict(title="Weekly Utilization Report")
    start_date: date
    end_date: date
    summary: UtilizationSummary
    peak_booking_day: date | None
    least_busy_day: date | None
    daily_breakdown: list[DailyUtilization]
    bookings_per_court: list[CourtUtilization]
    top_courts: list[CourtUtilization]
    least_utilized_courts: list[CourtUtilization]
