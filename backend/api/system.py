"""System and scenario control API routes."""

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

try:
    from core.security import limiter
except ModuleNotFoundError:
    from backend.core.security import limiter

from repositories.hospital_repo import HospitalRepository
from schemas.scenario import ScenarioRequest
from services.analytics_service import broadcast_score_update, build_analytics_snapshot
from services.dispatch_service import full_dispatch_pipeline, save_dispatch_bg
from simulation.incident_sim import build_incident_payload, create_incident
from core.response import error, success, unwrap_envelope

router = APIRouter(tags=["system"])


def rejection_reason(hospital: dict[str, object]) -> str:
    """Return a concise scenario explanation for a rejected hospital."""

    if hospital.get("diversion_status"):
        return "Hospital is on diversion"
    if float(hospital.get("occupancy_pct", 100.0)) >= 95.0:
        return "Critical capacity pressure"
    specialties_value = hospital.get("specialties") or []
    specialties = {str(item).strip().lower() for item in specialties_value}
    if "cardiology" not in specialties:
        return "No cardiology specialty match"
    return "Lower composite dispatch score"


def _cardiac_explanation(dispatch_plan: dict[str, object], hospitals: list[dict[str, object]]) -> dict[str, object]:
    score_breakdown = dispatch_plan.get("score_breakdown") if isinstance(dispatch_plan, dict) else {}
    if not isinstance(score_breakdown, dict):
        score_breakdown = {}
    components = score_breakdown.get("components")
    if not isinstance(components, dict):
        components = {}

    selected_hospital_id = dispatch_plan.get("hospital_id") if isinstance(dispatch_plan, dict) else None
    rejected_hospitals = [
        hospital
        for hospital in hospitals
        if hospital.get("id") != selected_hospital_id
    ][:3]
    return {
        "selected_reason": "Nearest ALS unit with highest composite score",
        "score_breakdown": {
            "eta_score": round(float(components.get("eta_score", 0.0)), 3),
            "capacity_score": round(float(components.get("capacity_score", 0.0)), 3),
            "specialty_score": round(float(components.get("specialty_score", 0.0)), 3),
            "final_score": round(float(score_breakdown.get("total_score", 0.0)), 3),
        },
        "rejected_hospitals": [
            {
                "id": hospital.get("id"),
                "name": hospital.get("name"),
                "reason": rejection_reason(hospital),
            }
            for hospital in rejected_hospitals
        ],
    }


@router.post("/scenarios/run", response_model=None)
@router.post("/simulate/scenario", response_model=None)
@limiter.limit("2/minute")
async def trigger_scenario(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: ScenarioRequest = Body(...),
) -> dict[str, object] | JSONResponse:
    """Apply a live scenario mutation for demos and smoke checks."""

    engine = getattr(request.app.state, "simulation_engine", None)
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
        dispatch_result = await full_dispatch_pipeline(str(incident["id"]), persist_dispatch=False)
        if isinstance(dispatch_result, JSONResponse):
            return dispatch_result

        dispatch_payload, dispatch_status, dispatch_message = unwrap_envelope(dispatch_result)
        if dispatch_status == "error":
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            return error(dispatch_message or "Dispatch failed", code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        dispatch_plan = dispatch_payload if isinstance(dispatch_payload, dict) else dispatch_result
        if isinstance(dispatch_plan, dict):
            background_tasks.add_task(save_dispatch_bg, dispatch_plan)
        if dispatch_status == "fallback":
            response.status_code = status.HTTP_207_MULTI_STATUS
            body["dispatch_status"] = dispatch_status
            body["dispatch_message"] = dispatch_message
        body["dispatch_plan"] = dispatch_plan
        if isinstance(dispatch_plan, dict):
            hospitals = await HospitalRepository().get_all(str(dispatch_plan.get("city") or incident["city"]))
            body["explanation"] = _cardiac_explanation(dispatch_plan, hospitals)
    elif engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Background simulation is disabled for this deployment.",
        )
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
    return success(body, message="Scenario triggered")


@router.get("/analytics", response_model=None)
async def get_analytics() -> dict[str, object]:
    """Return derived analytics for the current local day."""

    analytics = await build_analytics_snapshot()
    await broadcast_score_update(analytics)
    return success(analytics)
