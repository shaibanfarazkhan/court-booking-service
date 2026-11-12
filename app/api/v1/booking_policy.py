"""Staff administration endpoints for global booking limits."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import require_staff
from app.core.exceptions import BookingPolicyError, ResourceNotFoundError
from app.db.session import AsyncSession, get_db
from app.models.user import User
from app.schemas.booking_policy import BookingPolicyInput, BookingPolicyResponse
from app.services.booking_policy_service import BookingPolicyService

router = APIRouter(prefix="/booking-policy", tags=["Booking Policy"])


@router.get("", response_model=BookingPolicyResponse)
async def get_booking_policy(
    db: AsyncSession = Depends(get_db), _staff: User = Depends(require_staff)
) -> BookingPolicyResponse:
    """Return the active global booking policy (staff or admin only)."""
    try:
        return await BookingPolicyService(db).get_policy()
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


@router.put("", response_model=BookingPolicyResponse)
async def update_booking_policy(
    payload: BookingPolicyInput,
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(require_staff),
) -> BookingPolicyResponse:
    """Create or replace the active global booking policy."""
    try:
        return await BookingPolicyService(db).update_policy(payload)
    except (BookingPolicyError, ResourceNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
