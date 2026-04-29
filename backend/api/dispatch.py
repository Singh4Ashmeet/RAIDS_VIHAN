"""Dispatch API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.dispatch import DispatchPlan
from core.response import success
from repositories.dispatch_repo import DispatchRepository

router = APIRouter(prefix="/dispatch", tags=["dispatch"])


@router.get("/{dispatch_id}", response_model=None)
async def get_dispatch(dispatch_id: str) -> dict[str, object]:
    """Return a saved dispatch plan with score explainability details."""

    dispatch_plan = await DispatchRepository().get_by_id(dispatch_id)
    if dispatch_plan is None:
        raise HTTPException(status_code=404, detail="Dispatch plan not found.")
    return success(DispatchPlan.model_validate(dispatch_plan).model_dump(mode="json"))
