"""Build utilization reports from repository aggregates and existing pricing rules."""

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.db.session import AsyncSession
from app.repositories.report_repository import ReportRepository
from app.schemas.report import (
    CourtUtilization,
    DailyUtilization,
    ReportDateRange,
    UtilizationSummary,
    WeeklyUtilizationReport,
)
from app.services.pricing_service import PricingService


class ReportService:
    """Calculate report metrics without loading individual booking records."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = ReportRepository(session)
        self.pricing_service = PricingService(session)

    async def weekly_utilization(
        self, start_date: date, end_date: date
    ) -> WeeklyUtilizationReport:
        """Return court, daily, and overall utilization for an inclusive date range."""
        date_range = ReportDateRange(start_date=start_date, end_date=end_date)
        rows = await self.repository.get_court_daily_aggregates(
            date_range.start_date, date_range.end_date
        )
        court_data: dict[Any, dict[str, Any]] = {}
        daily_data: dict[date, dict[str, int]] = defaultdict(
            lambda: {"booked_slots": 0, "available_slots": 0}
        )
        cancelled = confirmed = 0
        for row in rows:
            court_id = row["court_id"]
            item = court_data.setdefault(
                court_id,
                {
                    "court_id": court_id,
                    "court_name": row["court_name"],
                    "venue_name": row["venue_name"],
                    "sport": row["sport"],
                    "total_slots": 0,
                    "booked_slots": 0,
                    "available_slots": 0,
                    "estimated_revenue": Decimal("0.00"),
                },
            )
            item["total_slots"] += int(row["total_slots"] or 0)
            item["booked_slots"] += int(row["booked_slots"] or 0)
            item["available_slots"] += int(row["available_slots"] or 0)
            cancelled += int(row["cancelled_bookings"] or 0)
            confirmed += int(row["confirmed_bookings"] or 0)
            report_day = row["report_date"]
            if report_day is not None:
                daily_data[report_day]["booked_slots"] += int(row["booked_slots"] or 0)
                daily_data[report_day]["available_slots"] += int(
                    row["available_slots"] or 0
                )

        price_groups = await self.repository.get_priced_booked_slots(
            date_range.start_date, date_range.end_date
        )
        for group in price_groups:
            group_start = group["start_time"]
            group_end = group["end_time"]
            if isinstance(group_start, datetime):
                group_start = group_start.timetz().replace(tzinfo=None)
            if isinstance(group_end, datetime):
                group_end = group_end.timetz().replace(tzinfo=None)
            quote = await self.pricing_service.calculate_price(
                group["court_id"], group["booking_date"], group_start, group_end
            )
            court_data[group["court_id"]]["estimated_revenue"] += (
                quote.final_price * int(group["slot_count"])
            )

        dates = [
            date_range.start_date + timedelta(days=offset)
            for offset in range((date_range.end_date - date_range.start_date).days + 1)
        ]
        daily = [
            DailyUtilization(
                date=day,
                booked_slots=daily_data[day]["booked_slots"],
                available_slots=daily_data[day]["available_slots"],
                utilization_percent=self._percent(
                    daily_data[day]["booked_slots"],
                    daily_data[day]["booked_slots"]
                    + daily_data[day]["available_slots"],
                ),
            )
            for day in dates
        ]
        court_reports = [
            CourtUtilization(
                **item,
                utilization_percent=self._percent(
                    item["booked_slots"], item["total_slots"]
                ),
            )
            for item in court_data.values()
        ]
        court_reports.sort(
            key=lambda item: (-item.utilization_percent, item.court_name)
        )
        total_slots = sum(item.total_slots for item in court_reports)
        booked_slots = sum(item.booked_slots for item in court_reports)
        available_slots = sum(item.available_slots for item in court_reports)
        estimated_revenue = sum(
            (item.estimated_revenue for item in court_reports), Decimal("0.00")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        average_daily = (
            sum((item.utilization_percent for item in daily), Decimal("0"))
            / Decimal(len(daily))
            if daily
            else Decimal("0")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        peak_day = (
            max(daily, key=lambda item: item.booked_slots).date if daily else None
        )
        least_day = (
            min(daily, key=lambda item: item.booked_slots).date if daily else None
        )

        return WeeklyUtilizationReport(
            start_date=start_date,
            end_date=end_date,
            summary=UtilizationSummary(
                total_courts=len(court_reports),
                total_slots=total_slots,
                booked_slots=booked_slots,
                available_slots=available_slots,
                cancelled_bookings=cancelled,
                confirmed_bookings=confirmed,
                utilization_percent=self._percent(booked_slots, total_slots),
                average_daily_utilization=average_daily,
                estimated_revenue=estimated_revenue,
            ),
            peak_booking_day=peak_day,
            least_busy_day=least_day,
            daily_breakdown=daily,
            bookings_per_court=court_reports,
            top_courts=court_reports[:5],
            least_utilized_courts=list(reversed(court_reports[-5:])),
        )

    @staticmethod
    def _percent(numerator: int, denominator: int) -> Decimal:
        if denominator == 0:
            return Decimal("0.00")
        return (Decimal(numerator) * 100 / Decimal(denominator)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
