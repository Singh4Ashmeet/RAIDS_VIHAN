"""Dispatch orchestration service for incidents and patient-linked flows."""

from __future__ import annotations

from typing import Any

from database import fetch_all, fetch_one, insert_record, update_record
from services.notification_service import notify_hospital
from services.scoring_service import select_best_dispatch
from services.triage_service import classify_severity


async def full_dispatch_pipeline(incident_id: str, patient_id: str | None = None) -> dict[str, Any]:
    """Run the complete dispatch lifecycle for an incident."""

    incident = await fetch_one("incidents", incident_id)
    if incident is None:
        raise ValueError(f"Incident {incident_id} was not found.")

    patient = await fetch_one("patients", patient_id) if patient_id else None
    triage_source = patient["chief_complaint"] if patient else incident["description"]
    triage = classify_severity(triage_source, bool(patient["sos_mode"]) if patient else False)

    incident_updates = {
        "type": triage["incident_type"],
        "severity": triage["severity"],
        "status": "open",
    }
    await update_record("incidents", incident_id, incident_updates)
    incident.update(incident_updates)

    if patient is not None:
        patient_updates = {"severity": triage["severity"], "status": "waiting"}
        await update_record("patients", patient_id, patient_updates)
        patient.update(patient_updates)

    ambulances = await fetch_all("ambulances")
    hospitals = await fetch_all("hospitals")
    dispatch_plan = select_best_dispatch(incident, ambulances, hospitals)

    ambulance = await fetch_one("ambulances", dispatch_plan["ambulance_id"])
    hospital = await fetch_one("hospitals", dispatch_plan["hospital_id"])
    if ambulance is None or hospital is None:
        raise ValueError("Selected dispatch targets could not be reloaded.")

    await update_record(
        "ambulances",
        ambulance["id"],
        {
            "status": "en_route",
            "assigned_incident_id": incident_id,
            "assigned_hospital_id": hospital["id"],
        },
    )
    incoming_patients = list(hospital["incoming_patients"])
    patient_token = patient_id or incident_id
    if patient_token not in incoming_patients:
        incoming_patients.append(patient_token)
    await update_record(
        "hospitals",
        hospital["id"],
        {
            "incoming_patients": incoming_patients,
        },
    )
    await update_record(
        "incidents",
        incident_id,
        {
            "status": "dispatched",
            "patient_id": patient_id,
        },
    )
    if patient is not None:
        await update_record(
            "patients",
            patient_id,
            {
                "assigned_ambulance_id": ambulance["id"],
                "assigned_hospital_id": hospital["id"],
                "status": "dispatched",
                "severity": triage["severity"],
            },
        )
        patient = await fetch_one("patients", patient_id)

    if patient is not None:
        await notify_hospital(hospital["id"], patient, dispatch_plan, ambulance)

    await insert_record(
        "dispatch_plans",
        {
            "id": dispatch_plan["id"],
            "incident_id": dispatch_plan["incident_id"],
            "patient_id": dispatch_plan["patient_id"],
            "ambulance_id": dispatch_plan["ambulance_id"],
            "hospital_id": dispatch_plan["hospital_id"],
            "ambulance_score": dispatch_plan["ambulance_score"],
            "hospital_score": dispatch_plan["hospital_score"],
            "route_score": dispatch_plan["route_score"],
            "final_score": dispatch_plan["final_score"],
            "eta_minutes": dispatch_plan["eta_minutes"],
            "distance_km": dispatch_plan["distance_km"],
            "rejected_ambulances": dispatch_plan["rejected_ambulances"],
            "rejected_hospitals": dispatch_plan["rejected_hospitals"],
            "explanation_text": dispatch_plan["explanation_text"],
            "fallback_hospital_id": dispatch_plan["fallback_hospital_id"],
            "created_at": dispatch_plan["created_at"],
            "status": dispatch_plan["status"],
            "baseline_eta_minutes": dispatch_plan["baseline_eta_minutes"],
            "overload_avoided": dispatch_plan["overload_avoided"],
        },
    )

    saved_dispatch = await fetch_one("dispatch_plans", dispatch_plan["id"])
    from api.websocket import broadcast_event

    await broadcast_event(
        {
            "type": "dispatch_created",
            "dispatch_plan": saved_dispatch,
        }
    )
    return saved_dispatch
