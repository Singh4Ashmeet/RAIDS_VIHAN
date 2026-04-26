"""Dispatch orchestration service for incidents and patient-linked flows."""

from __future__ import annotations

import os
import logging
from typing import Any
from uuid import uuid4

from agents.graph import run_dispatch_pipeline as _graph_run
from config import isoformat_utc
from database import fetch_all, fetch_one, insert_record, update_record
from services.analytics_service import build_analytics_snapshot, broadcast_score_update
from services.audit_service import log_ai_dispatch
from services.dispatch import select_dispatch
from services.nlp_triage import triage_incident
from services.notification_service import notify_hospital
from services.traffic import get_traffic_multiplier
from utils.response import error, fallback, success

USE_GRAPH_PIPELINE = os.getenv("RAID_NEXUS_USE_GRAPH_PIPELINE", "").lower() in {"1", "true", "yes"}
logger = logging.getLogger(__name__)


def _dispatch_created_payload(dispatch_plan: dict[str, Any]) -> dict[str, Any]:
    """Return the trimmed dispatch payload pushed to live clients."""

    return {
        "type": "dispatch_created",
        "audit_id": dispatch_plan.get("audit_id"),
        "dispatch_plan": {
            "id": dispatch_plan["id"],
            "ambulance_id": dispatch_plan["ambulance_id"],
            "hospital_id": dispatch_plan["hospital_id"],
            "incident_id": dispatch_plan["incident_id"],
            "eta_minutes": dispatch_plan["eta_minutes"],
            "status": dispatch_plan["status"],
            "score_breakdown": dispatch_plan["score_breakdown"],
            "baseline_eta_minutes": dispatch_plan["baseline_eta_minutes"],
            "explanation_text": dispatch_plan["explanation_text"],
            "created_at": dispatch_plan["created_at"],
            "traffic_multiplier": dispatch_plan["traffic_multiplier"],
            "city": dispatch_plan["city"],
            "audit_id": dispatch_plan.get("audit_id"),
            "override_id": dispatch_plan.get("override_id"),
            "requires_human_review": dispatch_plan.get("requires_human_review", False),
            "review_reason": dispatch_plan.get("review_reason"),
            "triage_confidence": dispatch_plan.get("triage_confidence"),
            "triage_version": dispatch_plan.get("triage_version"),
            "language_detected": dispatch_plan.get("language_detected"),
            "language_name": dispatch_plan.get("language_name"),
            "original_complaint": dispatch_plan.get("original_complaint"),
            "translated_complaint": dispatch_plan.get("translated_complaint"),
            "translation_model": dispatch_plan.get("translation_model"),
        },
    }


async def _dispatch_traffic_context(incident: dict[str, Any], hospital: dict[str, Any]) -> tuple[float, str | None]:
    """Return the display traffic multiplier for the chosen dispatch route."""

    city = incident.get("city") or hospital.get("city")
    midpoint_lat = (float(incident["location_lat"]) + float(hospital["lat"])) / 2.0
    midpoint_lng = (float(incident["location_lng"]) + float(hospital["lng"])) / 2.0
    multiplier = await get_traffic_multiplier(midpoint_lat, midpoint_lng, city=city)
    return round(multiplier, 2), city


async def full_dispatch_pipeline(incident_id: str, patient_id: str | None = None) -> Any:
    """Run the complete dispatch lifecycle for an incident."""

    try:
        graph_plan: dict[str, Any] | None = None

        if USE_GRAPH_PIPELINE:
            try:
                graph_plan = await _graph_run(incident_id, patient_id)
            except Exception as e:
                print(f"[RAID] Graph pipeline failed, using persisted pipeline: {e}")

        incident = await fetch_one("incidents", incident_id)
        if incident is None:
            raise ValueError(f"Incident {incident_id} was not found.")

        patient = await fetch_one("patients", patient_id) if patient_id else None
        triage_source = patient["chief_complaint"] if patient else incident["description"]
        triage = await triage_incident(
            triage_source,
            city=incident.get("city"),
            sos_mode=bool(patient["sos_mode"]) if patient else False,
        )

        incident_updates = {
            "type": triage["incident_type"],
            "severity": triage["severity"],
            "status": "open",
            "triage_confidence": triage.get("triage_confidence"),
            "requires_human_review": bool(triage.get("requires_human_review", False)),
            "review_reason": triage.get("review_reason"),
            "triage_version": triage.get("triage_version"),
            "language_detected": triage.get("language_detection", {}).get("language_code"),
            "language_name": triage.get("language_detection", {}).get("language_name"),
            "original_complaint": triage.get("translation", {}).get("original_text"),
            "translated_complaint": triage.get("translation", {}).get("translated_text"),
            "translation_model": triage.get("translation", {}).get("model_used"),
        }
        translated_text = triage.get("translation", {}).get("translated_text")
        if translated_text:
            incident_updates["description"] = translated_text
        await update_record("incidents", incident_id, incident_updates)
        incident.update(incident_updates)

        if patient is not None:
            patient_updates = {"severity": triage["severity"], "status": "waiting"}
            await update_record("patients", patient_id, patient_updates)
            patient.update(patient_updates)

        ambulances = await fetch_all("ambulances")
        hospitals = await fetch_all("hospitals")
        selection = await select_dispatch(incident, ambulances, hospitals)
        if selection["status"] == "error":
            return error(selection["explanation_text"], code=500)

        ambulance = await fetch_one("ambulances", selection["ambulance_id"])
        hospital = await fetch_one("hospitals", selection["hospital_id"])
        if ambulance is None or hospital is None:
            raise ValueError("Selected dispatch targets could not be reloaded.")
        traffic_multiplier, traffic_city = await _dispatch_traffic_context(incident, hospital)

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

        score_breakdown = selection.get("score_breakdown") or {}
        components = score_breakdown.get("components", {})
        weights_used = score_breakdown.get("weights_used", {})
        ambulance_score = round(
            (weights_used.get("w1", 0.0) * components.get("eta_score", 0.0))
            + (weights_used.get("w3", 0.0) * components.get("crew_readiness_score", 0.0)),
            4,
        )
        hospital_score = round(
            (weights_used.get("w2", 0.0) * components.get("specialty_score", 0.0))
            + (weights_used.get("w4", 0.0) * components.get("capacity_score", 0.0))
            + (weights_used.get("w5", 0.0) * components.get("er_wait_score", 0.0)),
            4,
        )
        dispatch_plan = {
            "id": str(uuid4()),
            "incident_id": incident_id,
            "patient_id": patient_id,
            "ambulance_id": selection["ambulance_id"],
            "hospital_id": selection["hospital_id"],
            "ambulance_score": ambulance_score,
            "hospital_score": hospital_score,
            "route_score": round(components.get("eta_score", 0.0), 4),
            "final_score": round(score_breakdown.get("total_score", 0.0), 4) if score_breakdown else 0.0,
            "eta_minutes": round(float(selection["eta_minutes"]), 2),
            "distance_km": round((float(selection["eta_minutes"]) / 60.0) * 40.0, 3),
            "rejected_ambulances": [],
            "rejected_hospitals": [],
            "score_breakdown": selection["score_breakdown"],
            "explanation_text": selection["explanation_text"],
            "fallback_hospital_id": None,
            "created_at": isoformat_utc(),
            "status": "fallback" if selection["status"] == "fallback" else "active",
            "baseline_eta_minutes": selection["baseline_eta_minutes"],
            "overload_avoided": False,
            "override_id": None,
            "traffic_multiplier": traffic_multiplier,
            "city": traffic_city,
            "requires_human_review": bool(triage.get("requires_human_review", False)),
            "review_reason": triage.get("review_reason"),
            "triage_confidence": triage.get("triage_confidence"),
            "triage_version": triage.get("triage_version"),
            "language_detected": triage.get("language_detection", {}).get("language_code"),
            "language_name": triage.get("language_detection", {}).get("language_name"),
            "original_complaint": triage.get("translation", {}).get("original_text"),
            "translated_complaint": triage.get("translation", {}).get("translated_text"),
            "translation_model": triage.get("translation", {}).get("model_used"),
        }

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
                "override_id": dispatch_plan["override_id"],
            },
        )
        try:
            audit_id = await log_ai_dispatch(dispatch_plan, incident, actor_id="system")
        except Exception as exc:
            logger.warning("Dispatch audit logging failed for %s: %s", dispatch_plan["id"], exc)
            audit_id = None
        dispatch_plan["audit_id"] = audit_id

        from api.websocket import broadcast_event

        await broadcast_event(_dispatch_created_payload(dispatch_plan))
        analytics = await build_analytics_snapshot()
        await broadcast_score_update(analytics)
        if selection["status"] == "fallback":
            return fallback(dispatch_plan, "Fallback dispatch")
        return success(dispatch_plan)
    except Exception as e:
        print(f"[DISPATCH ERROR] {e}")
        return error(str(e), code=500)
