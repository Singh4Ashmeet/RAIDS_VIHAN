"""Hospital API routes."""

from __future__ import annotations

from fastapi import APIRouter

from models.hospital import Hospital
from core.response import success
from repositories.hospital_repo import HospitalRepository

router = APIRouter(prefix="/hospitals", tags=["hospitals"])


@router.get("", response_model=None)
async def list_hospitals() -> dict[str, object]:
    """Return all hospitals with current live state."""

    hospitals = [Hospital.model_validate(item).model_dump(mode="json") for item in await HospitalRepository().get_all()]
    return success(hospitals)
