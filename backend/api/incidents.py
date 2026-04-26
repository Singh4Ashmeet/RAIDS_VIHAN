"""Incident API routes."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response, status
from fastapi.responses import JSONResponse

from database import fetch_all
from models.incident import Incident, IncidentCreate
from services.dispatch_service import full_dispatch_pipeline
from simulation.incident_sim import build_incident_payload, create_incident
from utils.response import fallback, success, unwrap_envelope

try:
    from security import limiter, sanitize_text_field, validate_incident_type, validate_india_coordinates, validate_severity
    from services.anomaly_detector import analyze_incident, record_incident
except ModuleNotFoundError:
    from backend.security import limiter, sanitize_text_field, validate_incident_type, validate_india_coordinates, validate_severity
    from backend.services.anomaly_detector import analyze_incident, record_incident

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.post("", response_model=None, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def create_manual_incident(
    payload: IncidentCreate,
    request: Request,
    response: Response,
) -> dict[str, object] | JSONResponse:
    """Create an incident and immediately run the dispatch pipeline."""

    validate_india_coordinates(payload.location_lat, payload.location_lng)
    incident_type = validate_incident_type(payload.type)
    severity = validate_severity(payload.severity)
    description = sanitize_text_field(payload.description, max_length=2000)

    incident_payload = build_incident_payload(
        city=payload.city.strip(),
        incident_type=incident_type,
        severity=severity,
        patient_count=payload.patient_count,
        location_lat=payload.location_lat,
        location_lng=payload.location_lng,
        description=description,
        patient_id=payload.patient_id,
        triage_confidence=payload.triage_confidence,
        requires_human_review=payload.requires_human_review,
        review_reason=payload.review_reason,
        triage_version=payload.triage_version,
        language_detected=payload.language_detected,
        language_name=payload.language_name,
        original_complaint=payload.original_complaint,
        translated_complaint=payload.translated_complaint,
        translation_model=payload.translation_model,
        has_anomaly=payload.has_anomaly,
        anomaly_flags=payload.anomaly_flags,
    )

    submitter_ip = request.client.host if request.client and request.client.host else "unknown"
    anomalies = await analyze_incident(incident_payload, submitter_ip)
    if anomalies:
        incident_payload["has_anomaly"] = True
        incident_payload["anomaly_flags"] = [anomaly["anomaly_type"] for anomaly in anomalies]

    await create_incident(incident_payload)
    record_incident(incident_payload)

    if anomalies:
        from api.websocket import broadcast_admin_event

        await broadcast_admin_event(
            {
                "type": "anomaly_detected",
                "anomalies": anomalies,
                "incident_id": incident_payload["id"],
            }
        )

    dispatch_result = await full_dispatch_pipeline(str(incident_payload["id"]), payload.patient_id)
    if isinstance(dispatch_result, JSONResponse):
        return dispatch_result

    dispatch_payload, dispatch_status, dispatch_message = unwrap_envelope(dispatch_result)
    dispatch_plan = dispatch_payload if isinstance(dispatch_payload, dict) else dispatch_result
    if dispatch_status == "fallback":
        response.status_code = status.HTTP_207_MULTI_STATUS
    else:
        response.status_code = status.HTTP_201_CREATED

    body = {
        "incident": Incident.model_validate(incident_payload),
        "dispatch_plan": dispatch_plan,
    }
    if dispatch_status == "fallback":
        body["dispatch_status"] = dispatch_status
        body["dispatch_message"] = dispatch_message
        return fallback(body, dispatch_message or "Fallback dispatch")
    return success(body, message="Incident created")


@router.get("", response_model=None)
async def list_incidents(status_filter: str | None = Query(default=None, alias="status")) -> dict[str, object]:
    """List incidents, optionally filtered by status."""

    if status_filter:
        incidents = await fetch_all("incidents", where_clause="status = ?", params=(status_filter,))
    else:
        incidents = await fetch_all("incidents")
    payload = [Incident.model_validate(item).model_dump(mode="json") for item in incidents]
    return success(payload)
