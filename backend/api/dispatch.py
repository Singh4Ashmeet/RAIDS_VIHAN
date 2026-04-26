"""Dispatch API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from database import fetch_one
from models.dispatch import DispatchPlan

router = APIRouter(prefix="/dispatch", tags=["dispatch"])


@router.get("/{dispatch_id}", response_model=DispatchPlan)
async def get_dispatch(dispatch_id: str) -> DispatchPlan:
    """Return a saved dispatch plan with score explainability details."""

    dispatch_plan = await fetch_one("dispatch_plans", dispatch_id)
    if dispatch_plan is None:
        raise HTTPException(status_code=404, detail="Dispatch plan not found.")
    return DispatchPlan.model_validate(dispatch_plan)
