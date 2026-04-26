"""Ambulance API routes."""

from __future__ import annotations

from fastapi import APIRouter

from database import fetch_all
from models.ambulance import Ambulance
from utils.response import success

router = APIRouter(prefix="/ambulances", tags=["ambulances"])


@router.get("", response_model=None)
async def list_ambulances() -> dict[str, object]:
    """Return all ambulances with current live state."""

    ambulances = [Ambulance.model_validate(item).model_dump(mode="json") for item in await fetch_all("ambulances")]
    return success(ambulances)
