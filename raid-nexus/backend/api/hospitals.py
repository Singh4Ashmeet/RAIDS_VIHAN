"""Hospital API routes."""

from __future__ import annotations

from fastapi import APIRouter

from database import fetch_all
from models.hospital import Hospital

router = APIRouter(prefix="/hospitals", tags=["hospitals"])


@router.get("", response_model=list[Hospital])
async def list_hospitals() -> list[Hospital]:
    """Return all hospitals with current live state."""

    return [Hospital.model_validate(item) for item in await fetch_all("hospitals")]
