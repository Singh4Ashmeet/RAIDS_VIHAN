"""System and scenario control API routes."""

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

try:
    from core.security import limiter
except ModuleNotFoundError:
    from backend.core.security import limiter

from repositories.ambulance_repo import AmbulanceRepository
from repositories.hospital_repo import HospitalRepository
from schemas.scenario import ScenarioRequest, TrafficOverrideRequest
from services.analytics_service import broadcast_score_update, build_analytics_snapshot
from services.dispatch_service import full_dispatch_pipeline, save_dispatch_bg
from simulation.engine import SimulationEngine
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


async def _prepare_cardiac_fixture() -> None:
    """Reset one deterministic Delhi unit and hospital so demos survive prior runs."""

    ambulance_repo = AmbulanceRepository()
    hospital_repo = HospitalRepository()

    if await ambulance_repo.get_by_id("AMB-001"):
        await ambulance_repo.update(
            "AMB-001",
            {
                "current_lat": 28.6140,
                "current_lng": 77.2090,
                "status": "available",
                "assigned_incident_id": None,
                "assigned_hospital_id": None,
                "crew_readiness": 0.95,
            },
        )

    if await hospital_repo.get_by_id("HOSP-001"):
        await hospital_repo.update(
            "HOSP-001",
            {
                "occupancy_pct": 68.0,
                "er_wait_minutes": 24,
                "icu_beds_available": 12,
                "acceptance_score": 0.84,
                "diversion_status": False,
            },
        )


def _ensure_engine(request: Request) -> SimulationEngine:
    engine = getattr(request.app.state, "simulation_engine", None)
    if engine is None:
        engine = SimulationEngine()
        request.app.state.simulation_engine = engine
    return engine


async def _hospital_for_city(city: str, preferred_id: str | None = None) -> dict[str, object]:
    hospital_repo = HospitalRepository()
    if preferred_id:
        hospital = await hospital_repo.get_by_id(preferred_id)
        if hospital is not None:
            return hospital
    hospitals = await hospital_repo.get_all(city) or await hospital_repo.get_all()
    if not hospitals:
        raise HTTPException(status_code=503, detail="No hospitals are available for scenario simulation.")
    return sorted(
        hospitals,
        key=lambda item: float(item.get("occupancy_pct", 0.0)),
        reverse=True,
    )[0]


async def _ambulance_for_city(city: str, preferred_id: str | None = None) -> dict[str, object]:
    ambulance_repo = AmbulanceRepository()
    if preferred_id:
        ambulance = await ambulance_repo.get_by_id(preferred_id)
        if ambulance is not None:
            return ambulance
    ambulances = await ambulance_repo.get_all(city) or await ambulance_repo.get_all()
    if not ambulances:
        raise HTTPException(status_code=503, detail="No ambulances are available for scenario simulation.")
    available = [item for item in ambulances if item.get("status") == "available"]
    return sorted(available or ambulances, key=lambda item: str(item.get("id")))[0]


async def _create_and_dispatch(
    incident: dict[str, object],
    background_tasks: BackgroundTasks,
) -> dict[str, object]:
    await create_incident(incident)
    dispatch_result = await full_dispatch_pipeline(str(incident["id"]), persist_dispatch=False)
    if isinstance(dispatch_result, JSONResponse):
        return {"incident": incident, "dispatch_plan": None, "dispatch_status": "error"}

    dispatch_payload, dispatch_status, dispatch_message = unwrap_envelope(dispatch_result)
    dispatch_plan = dispatch_payload if isinstance(dispatch_payload, dict) else dispatch_result
    if isinstance(dispatch_plan, dict):
        background_tasks.add_task(save_dispatch_bg, dispatch_plan)
    return {
        "incident": incident,
        "dispatch_plan": dispatch_plan,
        "dispatch_status": dispatch_status,
        "dispatch_message": dispatch_message,
    }


async def _spawn_mass_casualty(city: str, background_tasks: BackgroundTasks) -> dict[str, object]:
    offsets = [
        (0.0000, 0.0000, "trauma"),
        (0.0040, 0.0024, "accident"),
        (-0.0036, 0.0032, "cardiac"),
        (0.0028, -0.0042, "respiratory"),
        (-0.0048, -0.0018, "trauma"),
        (0.0052, -0.0030, "accident"),
        (-0.0024, 0.0050, "cardiac"),
        (0.0018, 0.0048, "other"),
    ]
    base_lat, base_lng = 28.6139, 77.2090
    created: list[dict[str, object]] = []
    dispatches: list[dict[str, object] | None] = []
    for index, (lat_offset, lng_offset, incident_type) in enumerate(offsets, start=1):
        incident = build_incident_payload(
            city=city,
            incident_type=incident_type,
            severity="critical",
            patient_count=2 if index <= 4 else 1,
            location_lat=base_lat + lat_offset,
            location_lng=base_lng + lng_offset,
            description=f"mass casualty cluster incident {index}",
        )
        if index <= 3:
            result = await _create_and_dispatch(incident, background_tasks)
            created.append(result["incident"])
            dispatches.append(result["dispatch_plan"])
        else:
            await create_incident(incident)
            created.append(incident)
    return {"incidents": created, "dispatches": dispatches, "manual_assignments_required": 5}


async def _spawn_multi_zone(city: str, background_tasks: BackgroundTasks) -> dict[str, object]:
    zones = [
        ("North", 28.7041, 77.1025, "trauma"),
        ("Central", 28.6304, 77.2177, "cardiac"),
        ("South", 28.5274, 77.2160, "respiratory"),
        ("East", 28.6735, 77.3059, "accident"),
    ]
    results: list[dict[str, object]] = []
    for zone, lat, lng, incident_type in zones:
        incident = build_incident_payload(
            city=city,
            incident_type=incident_type,
            severity="high" if incident_type != "cardiac" else "critical",
            patient_count=1,
            location_lat=lat,
            location_lng=lng,
            description=f"{zone} zone {incident_type} scenario",
        )
        results.append(await _create_and_dispatch(incident, background_tasks))
    return {"zones": [zone for zone, *_ in zones], "results": results}


@router.post("/scenarios/run", response_model=None)
@router.post("/simulate/scenario", response_model=None)
@limiter.limit("12/minute")
async def trigger_scenario(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    payload: ScenarioRequest = Body(...),
) -> dict[str, object] | JSONResponse:
    """Apply a live scenario mutation for demos and smoke checks."""

    engine = _ensure_engine(request)
    body: dict[str, object] = {"scenario": payload.type}

    if payload.type == "cardiac":
        await _prepare_cardiac_fixture()
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
    elif payload.type in {"overload", "hospital_overload"}:
        preferred_hospital_id = (
            "HOSP-005"
            if payload.type == "overload"
            else "HOSP-001" if payload.city == "Delhi" else None
        )
        hospital = await _hospital_for_city(payload.city, preferred_hospital_id)
        body["overload"] = await engine.apply_hospital_overload(str(hospital["id"]))
    elif payload.type == "breakdown":
        ambulance = await _ambulance_for_city(payload.city, "AMB-007")
        body["breakdown"] = await engine.apply_ambulance_outage(str(ambulance["id"]), payload.duration_seconds)
    elif payload.type in {"traffic", "traffic_surge"}:
        body["traffic"] = await engine.apply_traffic_override(
            payload.city,
            payload.traffic_multiplier,
            payload.duration_seconds,
        )
    elif payload.type == "mass_casualty":
        body["mass_casualty"] = await _spawn_mass_casualty(payload.city, background_tasks)
    elif payload.type == "multi_zone":
        body["multi_zone"] = await _spawn_multi_zone(payload.city, background_tasks)
    else:  # pragma: no cover - protected by Literal validation
        raise HTTPException(status_code=422, detail="Unsupported scenario type.")

    from api.websocket import broadcast_event

    await broadcast_event({"type": "scenario_triggered", **body})
    return success(body, message="Scenario triggered")


@router.post("/simulate/traffic", response_model=None)
@limiter.limit("20/minute")
async def set_traffic_override(
    request: Request,
    payload: TrafficOverrideRequest = Body(...),
) -> dict[str, object]:
    """Set a simulation traffic multiplier without requiring a preset scenario."""

    engine = _ensure_engine(request)
    traffic = await engine.apply_traffic_override(
        payload.city,
        payload.multiplier,
        payload.duration_seconds,
    )
    from api.websocket import broadcast_event

    await broadcast_event(
        {
            "type": "traffic_update",
            "traffic": traffic,
            "timestamp": traffic["expires_at"],
        }
    )
    return success({"traffic": traffic}, message="Traffic multiplier updated")


@router.get("/analytics", response_model=None)
async def get_analytics() -> dict[str, object]:
    """Return derived analytics for the current local day."""

    analytics = await build_analytics_snapshot()
    await broadcast_score_update(analytics)
    return success(analytics)
