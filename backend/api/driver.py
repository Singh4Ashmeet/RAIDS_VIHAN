"""Backward-compatible driver-client API scaffold."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from core.response import success
from repositories.ambulance_repo import AmbulanceRepository
from repositories.dispatch_repo import DispatchRepository

router = APIRouter(prefix="/driver", tags=["driver"])


class DriverLocationRequest(BaseModel):
    lat: float
    lng: float
    timestamp: str
    driver_id: str | None = None
    ambulance_id: str | None = None


class DriverStatusRequest(BaseModel):
    status: Literal["en_route", "on_scene", "available"]
    driver_id: str | None = None
    ambulance_id: str | None = None


def _ambulance_id(payload: DriverLocationRequest | DriverStatusRequest) -> str | None:
    return payload.ambulance_id or payload.driver_id


@router.get("/dispatches/{driver_id}", response_model=None)
async def get_driver_dispatches(driver_id: str) -> dict[str, object]:
    """Return active dispatches for a driver/ambulance identifier."""

    active = await DispatchRepository().get_active()
    return success([
        dispatch
        for dispatch in active
        if dispatch.get("ambulance_id") == driver_id or dispatch.get("driver_id") == driver_id
    ])


@router.post("/location", response_model=None)
async def update_driver_location(payload: DriverLocationRequest) -> dict[str, object]:
    """Accept a driver location update and persist it when an ambulance id is provided."""

    ambulance_id = _ambulance_id(payload)
    persisted = False
    if ambulance_id:
        ambulance = await AmbulanceRepository().get_by_id(ambulance_id)
        if ambulance is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ambulance not found.")
        await AmbulanceRepository().update_position(ambulance_id, payload.lat, payload.lng)
        persisted = True
    return success({
        "driver_id": payload.driver_id,
        "ambulance_id": ambulance_id,
        "lat": payload.lat,
        "lng": payload.lng,
        "timestamp": payload.timestamp,
        "persisted": persisted,
    })


@router.post("/status", response_model=None)
async def update_driver_status(payload: DriverStatusRequest) -> dict[str, object]:
    """Accept a driver status update and persist it when an ambulance id is provided."""

    ambulance_id = _ambulance_id(payload)
    persisted = False
    if ambulance_id:
        ambulance = await AmbulanceRepository().get_by_id(ambulance_id)
        if ambulance is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ambulance not found.")
        mapped_status = "at_scene" if payload.status == "on_scene" else payload.status
        await AmbulanceRepository().update_status(ambulance_id, mapped_status)
        persisted = True
    return success({
        "driver_id": payload.driver_id,
        "ambulance_id": ambulance_id,
        "status": payload.status,
        "persisted": persisted,
    })
