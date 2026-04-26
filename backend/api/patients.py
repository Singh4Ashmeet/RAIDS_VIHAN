"""Patient intake API routes."""

from __future__ import annotations
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from config import isoformat_utc
from database import fetch_one, insert_record
from models.patient import Patient, PatientCreate, PatientDetailResponse
from services.dispatch_service import full_dispatch_pipeline
from services.geo_service import nearest_city
from services.nlp_triage import triage_incident
from simulation.incident_sim import build_incident_payload, create_incident
from utils.response import error, fallback, success, unwrap_envelope

try:
    from security import sanitize_text_field, validate_india_coordinates
    from services.anomaly_detector import analyze_incident, record_incident
except ModuleNotFoundError:
    from backend.security import sanitize_text_field, validate_india_coordinates
    from backend.services.anomaly_detector import analyze_incident, record_incident

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", response_model=None, status_code=status.HTTP_201_CREATED)
async def create_patient(
    payload: PatientCreate,
    request: Request,
    response: Response,
) -> dict[str, object] | JSONResponse:
    """Create a patient, derive incident details, and trigger dispatch."""

    try:
        validate_india_coordinates(payload.location_lat, payload.location_lng)
        chief_complaint = sanitize_text_field(payload.chief_complaint, max_length=1000)
        city = await nearest_city(payload.location_lat, payload.location_lng)
        triage = await triage_incident(chief_complaint, city=city, sos_mode=payload.sos_mode)
        translation = triage.get("translation") if isinstance(triage.get("translation"), dict) else None
        incident_complaint = (
            str(translation["translated_text"])
            if translation and translation.get("was_translated")
            else chief_complaint
        )
        patient_payload = {
            "id": str(uuid4()),
            "name": payload.name,
            "age": payload.age,
            "gender": payload.gender,
            "mobile": payload.mobile,
            "location_lat": payload.location_lat,
            "location_lng": payload.location_lng,
            "chief_complaint": chief_complaint,
            "severity": triage["severity"],
            "sos_mode": payload.sos_mode,
            "created_at": isoformat_utc(),
            "assigned_ambulance_id": None,
            "assigned_hospital_id": None,
            "status": "waiting",
        }
        await insert_record("patients", patient_payload)
        incident_payload = build_incident_payload(
            city=city,
            incident_type=str(triage["incident_type"]),
            severity=str(triage["severity"]),
            patient_count=1,
            location_lat=payload.location_lat,
            location_lng=payload.location_lng,
            description=incident_complaint,
            patient_id=patient_payload["id"],
            triage_confidence=triage.get("triage_confidence"),
            requires_human_review=bool(triage.get("requires_human_review", False)),
            review_reason=triage.get("review_reason"),
            triage_version=triage.get("triage_version"),
            language_detected=triage.get("language_detection", {}).get("language_code"),
            language_name=triage.get("language_detection", {}).get("language_name"),
            original_complaint=translation.get("original_text") if translation else None,
            translated_complaint=translation.get("translated_text") if translation else None,
            translation_model=translation.get("model_used") if translation else None,
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
        dispatch_result = await full_dispatch_pipeline(str(incident_payload["id"]), str(patient_payload["id"]))
        if isinstance(dispatch_result, JSONResponse):
            return dispatch_result

        patient_record = await fetch_one("patients", str(patient_payload["id"]))
        if patient_record is None:
            return error("Created patient could not be reloaded.", code=500)

        dispatch_payload, dispatch_status, dispatch_message = unwrap_envelope(dispatch_result)
        dispatch_plan = dispatch_payload if isinstance(dispatch_payload, dict) else dispatch_result
        patient_data = Patient.model_validate(patient_record).model_dump(mode="json")
        response_payload = {
            "patient": patient_data,
            "dispatch_plan": dispatch_plan,
            "notification_sent": bool(
                isinstance(dispatch_plan, dict) and dispatch_plan.get("hospital_id")
            ),
        }

        if dispatch_status == "fallback":
            response.status_code = status.HTTP_207_MULTI_STATUS
            response_payload["dispatch_status"] = dispatch_status
            response_payload["dispatch_message"] = dispatch_message or "Fallback dispatch"
            return fallback(response_payload, dispatch_message or "Fallback dispatch")

        response.status_code = status.HTTP_201_CREATED
        return success(response_payload, message="Patient created")
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        if isinstance(exc, ValueError):
            return error(str(exc), code=500)
        return error(str(exc), code=500)


@router.get("/{patient_id}", response_model=PatientDetailResponse)
async def get_patient(patient_id: str) -> PatientDetailResponse:
    """Return a patient together with assigned ambulance and hospital details."""

    patient = await fetch_one("patients", patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    ambulance = await fetch_one("ambulances", patient["assigned_ambulance_id"]) if patient.get("assigned_ambulance_id") else None
    hospital = await fetch_one("hospitals", patient["assigned_hospital_id"]) if patient.get("assigned_hospital_id") else None
    return PatientDetailResponse(
        patient=Patient.model_validate(patient),
        assigned_ambulance=ambulance,
        assigned_hospital=hospital,
    )
