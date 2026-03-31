"""Incident API routes."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from database import fetch_all
from models.incident import Incident, IncidentCreate
from services.dispatch_service import full_dispatch_pipeline
from simulation.incident_sim import build_incident_payload, create_incident

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_manual_incident(payload: IncidentCreate) -> dict[str, object]:
    """Create an incident and immediately run the dispatch pipeline."""

    incident_payload = build_incident_payload(
        city=payload.city,
        incident_type=payload.type,
        severity=payload.severity,
        patient_count=payload.patient_count,
        location_lat=payload.location_lat,
        location_lng=payload.location_lng,
        description=payload.description,
        patient_id=payload.patient_id,
    )
    await create_incident(incident_payload)
    dispatch_plan = await full_dispatch_pipeline(str(incident_payload["id"]), payload.patient_id)
    return {
        "incident": Incident.model_validate(incident_payload),
        "dispatch_plan": dispatch_plan,
    }


@router.get("", response_model=list[Incident])
async def list_incidents(status_filter: str | None = Query(default=None, alias="status")) -> list[Incident]:
    """List incidents, optionally filtered by status."""

    if status_filter:
        incidents = await fetch_all("incidents", where_clause="status = ?", params=(status_filter,))
    else:
        incidents = await fetch_all("incidents")
    return [Incident.model_validate(item) for item in incidents]
