"""Pricing calculation and staff pricing-rule administration endpoints."""

import uuid
from datetime import date, time

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.dependencies import require_staff
from app.core.exceptions import PricingRuleOverlapError, ResourceNotFoundError
from app.db.session import AsyncSession, get_db
from app.models.user import User
from app.schemas.pricing import (
    PricingCalculationResponse,
    PricingRuleInput,
    PricingRuleListResponse,
    PricingRuleResponse,
)
from app.services.pricing_service import PricingService

router = APIRouter(prefix="/pricing", tags=["Pricing"])


def _raise_pricing_error(error: Exception) -> None:
    if isinstance(error, ResourceNotFoundError):
        raise HTTPException(status_code=404, detail=error.message) from error
    if isinstance(error, PricingRuleOverlapError):
        raise HTTPException(status_code=409, detail=error.message) from error
    if isinstance(error, ValueError):
        raise HTTPException(status_code=422, detail=str(error)) from error
    raise error


@router.get("/calculate", response_model=PricingCalculationResponse)
async def calculate_price(
    court_id: uuid.UUID,
    booking_date: date,
    start_time: time,
    end_time: time,
    db: AsyncSession = Depends(get_db),
) -> PricingCalculationResponse:
    """Return an explanatory quote using the court's configured pricing rules."""
    try:
        return await PricingService(db).calculate_price(
            court_id, booking_date, start_time, end_time
        )
    except (ResourceNotFoundError, ValueError) as exc:
        _raise_pricing_error(exc)


@router.post(
    "/rules",
    response_model=PricingRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pricing_rule(
    payload: PricingRuleInput,
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(require_staff),
) -> PricingRuleResponse:
    """Create a scoped pricing rule (staff or admin only)."""
    try:
        return await PricingService(db).create_rule(payload)
    except (PricingRuleOverlapError, ResourceNotFoundError, ValueError) as exc:
        _raise_pricing_error(exc)


@router.put("/rules/{rule_id}", response_model=PricingRuleResponse)
async def update_pricing_rule(
    rule_id: uuid.UUID,
    payload: PricingRuleInput,
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(require_staff),
) -> PricingRuleResponse:
    """Replace a pricing rule definition (staff or admin only)."""
    try:
        return await PricingService(db).update_rule(rule_id, payload)
    except (PricingRuleOverlapError, ResourceNotFoundError, ValueError) as exc:
        _raise_pricing_error(exc)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pricing_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(require_staff),
) -> Response:
    """Delete a pricing rule (staff or admin only)."""
    try:
        await PricingService(db).delete_rule(rule_id)
    except ResourceNotFoundError as exc:
        _raise_pricing_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/rules", response_model=PricingRuleListResponse)
async def list_pricing_rules(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _staff: User = Depends(require_staff),
) -> PricingRuleListResponse:
    """List configured rules in priority order (staff or admin only)."""
    try:
        return await PricingService(db).list_rules(page, page_size)
    except ValueError as exc:
        _raise_pricing_error(exc)
