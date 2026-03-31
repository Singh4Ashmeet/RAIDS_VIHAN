"""Dispatch API routes."""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from database import fetch_one
from models.dispatch import DispatchPlan
from services.dispatch_service import full_dispatch_pipeline

router = APIRouter(prefix="/dispatch", tags=["dispatch"])


class DispatchRequest(BaseModel):
    """Manual dispatch trigger request."""

    incident_id: str
    patient_id: str | None = None


@router.post("", response_model=DispatchPlan)
async def trigger_dispatch(payload: DispatchRequest) -> DispatchPlan:
    """Manually execute the dispatch pipeline for an incident."""

    try:
        dispatch_plan = await full_dispatch_pipeline(payload.incident_id, payload.patient_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return DispatchPlan.model_validate(dispatch_plan)


@router.get("/{dispatch_id}", response_model=DispatchPlan)
async def get_dispatch(dispatch_id: str) -> DispatchPlan:
    """Return a saved dispatch plan with score explainability details."""

    dispatch_plan = await fetch_one("dispatch_plans", dispatch_id)
    if dispatch_plan is None:
        raise HTTPException(status_code=404, detail="Dispatch plan not found.")
    return DispatchPlan.model_validate(dispatch_plan)
