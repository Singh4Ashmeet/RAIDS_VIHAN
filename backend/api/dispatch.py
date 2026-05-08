"""Dispatch API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.dispatch import DispatchPlan
from core.response import success
from repositories.ambulance_repo import AmbulanceRepository
from repositories.dispatch_repo import DispatchRepository
from repositories.hospital_repo import HospitalRepository
from services.dispatch_service import structured_dispatch_explanation

router = APIRouter(prefix="/dispatch", tags=["dispatch"])


@router.get("/{dispatch_id}", response_model=None)
async def get_dispatch(dispatch_id: str) -> dict[str, object]:
    """Return a saved dispatch plan with score explainability details."""

    dispatch_plan = await DispatchRepository().get_by_id(dispatch_id)
    if dispatch_plan is None:
        raise HTTPException(status_code=404, detail="Dispatch plan not found.")
    payload = DispatchPlan.model_validate(dispatch_plan).model_dump(mode="json")
    ambulance = await AmbulanceRepository().get_by_id(payload["ambulance_id"])
    hospital = await HospitalRepository().get_by_id(payload["hospital_id"])
    payload["explanation"] = structured_dispatch_explanation(payload, ambulance, hospital)
    return success(payload)
