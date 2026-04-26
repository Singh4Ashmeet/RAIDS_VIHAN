"""Hospital pre-notification creation and persistence."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from config import isoformat_utc
from database import insert_record
from services.nlp_triage import triage_incident

PREP_CHECKLISTS: dict[str, list[str]] = {
    "cardiac": [
        "Prepare cardiac ICU bed",
        "Alert cardiologist on duty",
        "Ready defibrillator in ER",
        "Prepare ECG equipment",
        "IV line setup",
    ],
    "trauma": [
        "Prepare trauma bay",
        "Alert trauma surgeon",
        "Blood type cross-match ready",
        "X-ray / CT on standby",
        "OR on alert",
    ],
    "respiratory": [
        "Prepare ventilator",
        "Alert pulmonologist",
        "Oxygen therapy setup",
        "Nebulizer in ER",
        "ABG test kit ready",
    ],
    "default": [
        "Prepare ER bed",
        "Alert on-call physician",
        "IV line and vitals monitor ready",
    ],
}


async def _prep_checklist(chief_complaint: str) -> list[str]:
    triage = await triage_incident(chief_complaint)
    return PREP_CHECKLISTS.get(str(triage["incident_type"]), PREP_CHECKLISTS["default"])


async def notify_hospital(
    hospital_id: str,
    patient: dict[str, Any],
    dispatch_plan: dict[str, Any],
    ambulance: dict[str, Any],
) -> dict[str, Any]:
    """Build, save, and broadcast a hospital pre-notification event."""

    timestamp = isoformat_utc()
    event = {
        "type": "hospital_notification",
        "hospital_id": hospital_id,
        "patient_name": patient["name"],
        "patient_age": patient["age"],
        "patient_gender": patient["gender"],
        "chief_complaint": patient["chief_complaint"],
        "severity": patient["severity"],
        "eta_minutes": dispatch_plan["eta_minutes"],
        "ambulance_id": ambulance["id"],
        "ambulance_equipment": ambulance["equipment"],
        "ambulance_type": ambulance["type"],
        "prep_checklist": await _prep_checklist(patient["chief_complaint"]),
        "timestamp": timestamp,
    }
    await insert_record(
        "notifications",
        {
            "id": str(uuid4()),
            "hospital_id": hospital_id,
            "patient_name": event["patient_name"],
            "patient_age": event["patient_age"],
            "patient_gender": event["patient_gender"],
            "chief_complaint": event["chief_complaint"],
            "severity": event["severity"],
            "eta_minutes": event["eta_minutes"],
            "ambulance_id": event["ambulance_id"],
            "ambulance_equipment": event["ambulance_equipment"],
            "ambulance_type": event["ambulance_type"],
            "prep_checklist": event["prep_checklist"],
            "timestamp": timestamp,
            "payload": event,
            "created_at": timestamp,
        },
    )
    from api.websocket import broadcast_event

    await broadcast_event(event)
    return event
