"""Ambulance API routes."""

from __future__ import annotations

from fastapi import APIRouter

from database import fetch_all
from models.ambulance import Ambulance

router = APIRouter(prefix="/ambulances", tags=["ambulances"])


@router.get("", response_model=list[Ambulance])
async def list_ambulances() -> list[Ambulance]:
    """Return all ambulances with current live state."""

    return [Ambulance.model_validate(item) for item in await fetch_all("ambulances")]
