"""Hospital API routes."""

from __future__ import annotations

from fastapi import APIRouter

from database import fetch_all
from models.hospital import Hospital
from utils.response import success

router = APIRouter(prefix="/hospitals", tags=["hospitals"])


@router.get("", response_model=None)
async def list_hospitals() -> dict[str, object]:
    """Return all hospitals with current live state."""

    hospitals = [Hospital.model_validate(item).model_dump(mode="json") for item in await fetch_all("hospitals")]
    return success(hospitals)
