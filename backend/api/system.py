"""System and scenario control API routes."""

from __future__ import annotations
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

try:
    from security import limiter
except ModuleNotFoundError:
    from backend.security import limiter

from services.analytics_service import broadcast_score_update, build_analytics_snapshot
from services.dispatch_service import full_dispatch_pipeline
from simulation.incident_sim import build_incident_payload, create_incident
from utils.response import unwrap_envelope

router = APIRouter(tags=["system"])


class ScenarioRequest(BaseModel):
    """Scenario request payload."""

    type: Literal["cardiac", "overload", "breakdown", "traffic"]


@router.post("/scenarios/run", response_model=None)
@router.post("/simulate/scenario", response_model=None)
@limiter.limit("2/minute")
async def trigger_scenario(
    payload: ScenarioRequest,
    request: Request,
    response: Response,
) -> dict[str, object] | JSONResponse:
    """Apply a live scenario mutation for demos and smoke checks."""

    engine = request.app.state.simulation_engine
    body: dict[str, object] = {"scenario": payload.type}

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
        dispatch_result = await full_dispatch_pipeline(str(incident["id"]))
        if isinstance(dispatch_result, JSONResponse):
            return dispatch_result

        dispatch_payload, dispatch_status, dispatch_message = unwrap_envelope(dispatch_result)
        dispatch_plan = dispatch_payload if isinstance(dispatch_payload, dict) else dispatch_result
        if dispatch_status == "fallback":
            response.status_code = status.HTTP_207_MULTI_STATUS
            body["dispatch_status"] = dispatch_status
            body["dispatch_message"] = dispatch_message
        body["dispatch_plan"] = dispatch_plan
    elif payload.type == "overload":
        body["overload"] = await engine.apply_hospital_overload("HOSP-005")
    elif payload.type == "breakdown":
        body["breakdown"] = await engine.apply_ambulance_outage("AMB-007", 60)
    elif payload.type == "traffic":
        body["traffic"] = await engine.apply_traffic_override("Bengaluru", 2.5, 60)
    else:  # pragma: no cover - protected by Literal validation
        raise HTTPException(status_code=422, detail="Unsupported scenario type.")

    from api.websocket import broadcast_event

    await broadcast_event({"type": "scenario_triggered", **body})
    return body


@router.get("/analytics")
async def get_analytics() -> dict[str, float | int]:
    """Return derived analytics for the current local day."""

    analytics = await build_analytics_snapshot()
    await broadcast_score_update(analytics)
    return analytics
