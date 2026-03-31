"""System and scenario control API routes."""

from __future__ import annotations

from datetime import datetime
from statistics import mean
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config import KOLKATA_TZ
from database import fetch_all
from services.dispatch_service import full_dispatch_pipeline
from simulation.incident_sim import build_incident_payload, create_incident

router = APIRouter(tags=["system"])


class ScenarioRequest(BaseModel):
    """Scenario request payload."""

    type: Literal["cardiac", "overload", "breakdown", "traffic"]


def _is_today_local(timestamp: str) -> bool:
    parsed = datetime.fromisoformat(timestamp)
    return parsed.astimezone(KOLKATA_TZ).date() == datetime.now(tz=KOLKATA_TZ).date()


@router.post("/simulate/scenario")
async def trigger_scenario(payload: ScenarioRequest, request: Request) -> dict[str, object]:
    """Apply a live scenario mutation for demos and smoke checks."""

    engine = request.app.state.simulation_engine
    response: dict[str, object] = {"scenario": payload.type}

    if payload.type == "cardiac":
        incident = build_incident_payload(
            city="Delhi",
            incident_type="cardiac",
            severity="critical",
            patient_count=1,
            location_lat=28.6139,
            location_lng=77.2090,
            description="critical cardiac emergency with chest pain",
        )
        await create_incident(incident)
        dispatch_plan = await full_dispatch_pipeline(str(incident["id"]))
        response["dispatch_plan"] = dispatch_plan
    elif payload.type == "overload":
        response["overload"] = await engine.apply_hospital_overload("HOSP-005")
    elif payload.type == "breakdown":
        response["breakdown"] = await engine.apply_ambulance_outage("AMB-007", 60)
    elif payload.type == "traffic":
        response["traffic"] = await engine.apply_traffic_override("Bengaluru", 2.5, 60)
    else:  # pragma: no cover - protected by Literal validation
        raise HTTPException(status_code=422, detail="Unsupported scenario type.")

    from api.websocket import broadcast_event

    await broadcast_event({"type": "scenario_triggered", **response})
    return response


@router.get("/analytics")
async def get_analytics() -> dict[str, float | int]:
    """Return derived analytics for the current local day."""

    incidents = [item for item in await fetch_all("incidents") if _is_today_local(item["created_at"])]
    dispatches = [item for item in await fetch_all("dispatch_plans") if _is_today_local(item["created_at"])]
    notifications = [item for item in await fetch_all("notifications") if _is_today_local(item["created_at"])]

    ai_eta_values = [float(item["eta_minutes"]) for item in dispatches]
    baseline_values = [
        float(item["baseline_eta_minutes"])
        for item in dispatches
        if item.get("baseline_eta_minutes") is not None
    ]
    overloads_prevented = sum(1 for item in dispatches if item.get("overload_avoided"))
    return {
        "avg_eta_ai": round(mean(ai_eta_values), 2) if ai_eta_values else 0.0,
        "avg_eta_baseline": round(mean(baseline_values), 2) if baseline_values else 0.0,
        "incidents_today": len(incidents),
        "dispatches_today": len(dispatches),
        "hospitals_notified": len(notifications),
        "overloads_prevented": overloads_prevented,
    }
