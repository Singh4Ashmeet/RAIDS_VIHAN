"""Patient intake API routes."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from config import isoformat_utc
from database import fetch_one, insert_record
from models.patient import Patient, PatientCreate, PatientCreateResponse, PatientDetailResponse
from services.dispatch_service import full_dispatch_pipeline
from services.geo_service import nearest_city
from services.triage_service import classify_severity
from simulation.incident_sim import build_incident_payload, create_incident

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", response_model=PatientCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(payload: PatientCreate) -> PatientCreateResponse:
    """Create a patient, derive incident details, and trigger dispatch."""

    triage = classify_severity(payload.chief_complaint, payload.sos_mode)
    patient_payload = {
        "id": str(uuid4()),
        "name": payload.name,
        "age": payload.age,
        "gender": payload.gender,
        "mobile": payload.mobile,
        "location_lat": payload.location_lat,
        "location_lng": payload.location_lng,
        "chief_complaint": payload.chief_complaint,
        "severity": triage["severity"],
        "sos_mode": payload.sos_mode,
        "created_at": isoformat_utc(),
        "assigned_ambulance_id": None,
        "assigned_hospital_id": None,
        "status": "waiting",
    }
    await insert_record("patients", patient_payload)
    incident_payload = build_incident_payload(
        city=nearest_city(payload.location_lat, payload.location_lng),
        incident_type=str(triage["incident_type"]),
        severity=str(triage["severity"]),
        patient_count=1,
        location_lat=payload.location_lat,
        location_lng=payload.location_lng,
        description=payload.chief_complaint,
        patient_id=patient_payload["id"],
    )
    await create_incident(incident_payload)
    dispatch_plan = await full_dispatch_pipeline(str(incident_payload["id"]), str(patient_payload["id"]))
    patient_record = await fetch_one("patients", str(patient_payload["id"]))
    if patient_record is None:
        raise HTTPException(status_code=404, detail="Created patient could not be reloaded.")
    return PatientCreateResponse(
        patient=Patient.model_validate(patient_record),
        dispatch_plan=dispatch_plan,
        notification_sent=True,
    )


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
