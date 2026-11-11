"""Booking hold, confirmation, cancellation, and owner-list endpoints."""

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.api.dependencies import require_member
from app.core.exceptions import (
    AccountInactiveError,
    BookingHoldExpiredError,
    BookingNotFoundError,
    BookingOwnershipError,
    BookingStateError,
    CancellationWindowError,
    DuplicateActiveHoldError,
    IdempotencyConflictError,
    ResourceNotFoundError,
    SlotUnavailableError,
)
from app.db.session import AsyncSession, get_db
from app.models.user import User
from app.schemas.bookings import (
    BookingHoldRequest,
    BookingListResponse,
    BookingResponse,
    RecurringBookingRequest,
    RecurringBookingResponse,
)
from app.services.booking_service import BookingService
from app.services.recurring_booking_service import RecurringBookingService

router = APIRouter(prefix="/bookings", tags=["Bookings"])


def _raise_booking_error(error: Exception) -> None:
    if isinstance(error, (BookingNotFoundError, ResourceNotFoundError)):
        raise HTTPException(status_code=404, detail=error.message) from error
    if isinstance(error, BookingHoldExpiredError):
        raise HTTPException(status_code=410, detail=error.message) from error
    if isinstance(error, BookingOwnershipError):
        raise HTTPException(status_code=403, detail=error.message) from error
    if isinstance(error, CancellationWindowError):
        raise HTTPException(status_code=409, detail=error.message) from error
    if isinstance(error, AccountInactiveError):
        raise HTTPException(status_code=403, detail=error.message) from error
    if isinstance(error, IdempotencyConflictError):
        raise HTTPException(status_code=409, detail=error.message) from error
    if isinstance(error, ValueError):
        raise HTTPException(status_code=422, detail=str(error)) from error
    if isinstance(
        error,
        (BookingStateError, DuplicateActiveHoldError, SlotUnavailableError),
    ):
        raise HTTPException(status_code=409, detail=error.message) from error
    raise error


@router.post(
    "/holds",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_hold(
    payload: BookingHoldRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member),
) -> BookingResponse:
    """Hold an available time slot for 15 minutes."""
    try:
        return await BookingService(db).create_hold(current_user.id, payload)
    except (
        DuplicateActiveHoldError,
        ResourceNotFoundError,
        SlotUnavailableError,
    ) as exc:
        _raise_booking_error(exc)


@router.post("/{booking_id}/confirm", response_model=BookingResponse)
async def confirm_booking(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member),
    idempotency_key: str | None = Header(
        default=None, alias="Idempotency-Key", min_length=1, max_length=64
    ),
) -> BookingResponse | JSONResponse:
    """Confirm an unexpired hold; persist expiry before returning HTTP 410."""
    try:
        return await BookingService(db).confirm_booking(
            booking_id, current_user.id, idempotency_key
        )
    except BookingHoldExpiredError as exc:
        return JSONResponse(status_code=410, content={"detail": exc.message})
    except (BookingNotFoundError, ResourceNotFoundError, BookingStateError) as exc:
        _raise_booking_error(exc)


@router.post(
    "/recurring",
    response_model=RecurringBookingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_recurring_bookings(
    payload: RecurringBookingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member),
) -> RecurringBookingResponse:
    """Create eligible daily or weekly confirmed bookings for the member."""
    try:
        return await RecurringBookingService(db).create_recurring_bookings(
            current_user.id, payload
        )
    except (
        AccountInactiveError,
        IdempotencyConflictError,
        ResourceNotFoundError,
        ValueError,
    ) as exc:
        _raise_booking_error(exc)


@router.post("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member),
) -> BookingResponse:
    """Cancel an owned confirmed booking and release its slot."""
    try:
        return await BookingService(db).cancel_booking(
            booking_id, current_user.id, current_user.role
        )
    except (
        BookingNotFoundError,
        BookingOwnershipError,
        CancellationWindowError,
        ResourceNotFoundError,
        BookingStateError,
    ) as exc:
        _raise_booking_error(exc)


@router.get("/my", response_model=BookingListResponse)
async def list_user_bookings(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_member),
) -> BookingListResponse:
    """Return the authenticated user's bookings with pagination metadata."""
    items = await BookingService(db).list_user_bookings(current_user.id, skip, limit)
    return BookingListResponse(items=items, skip=skip, limit=limit)
