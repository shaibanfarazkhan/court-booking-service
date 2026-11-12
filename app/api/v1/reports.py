"""Staff-only report endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from app.api.dependencies import require_staff
from app.db.session import AsyncSession, get_db
from app.models.user import User
from app.schemas.report import WeeklyUtilizationReport
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/weekly-utilization", response_model=WeeklyUtilizationReport)
async def weekly_utilization_report(
    start_date: date,
    end_date: date,
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(require_staff),
) -> WeeklyUtilizationReport:
    """Return utilization and booking statistics for up to 31 inclusive days."""
    try:
        return await ReportService(db).weekly_utilization(start_date, end_date)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
