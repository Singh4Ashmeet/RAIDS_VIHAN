"""Realtime map payload builders for dispatch, tracking, and rerouting."""

from __future__ import annotations

import asyncio
from typing import Any

from core.config import isoformat_utc
from repositories.ambulance_repo import AmbulanceRepository
from repositories.dispatch_repo import DispatchRepository
from repositories.hospital_repo import HospitalRepository
from repositories.incident_repo import IncidentRepository
from services.dispatch import MANUAL_ESCALATION_TEXT, select_dispatch
from services.geo_service import get_active_traffic_multiplier, is_coordinate_in_city, same_city
from services.routing import get_route_polyline, get_travel_time


def _lnglat(lat: float, lng: float) -> list[float]:
    """Return a Mapbox/MapLibre coordinate pair."""

    return [round(float(lng), 6), round(float(lat), 6)]


def _resource_in_service_area(resource: dict[str, Any] | None, service_city: str | None) -> bool:
    if not resource or not service_city or not same_city(resource.get("city"), service_city):
        return False
    lat = resource.get("current_lat", resource.get("lat"))
    lng = resource.get("current_lng", resource.get("lng"))
    return is_coordinate_in_city(service_city, lat, lng, margin=0.03)


def _route_entities_city_local(
    incident: dict[str, Any],
    ambulance: dict[str, Any],
    hospital: dict[str, Any],
) -> bool:
    service_city = incident.get("city")
    return (
        is_coordinate_in_city(service_city, incident.get("location_lat"), incident.get("location_lng"), margin=0.03)
        and _resource_in_service_area(ambulance, service_city)
        and _resource_in_service_area(hospital, service_city)
    )


def _fallback_segment(start: tuple[float, float], end: tuple[float, float]) -> list[list[float]]:
    """Return a stable straight-line segment when OSRM is unavailable."""

    start_lat, start_lng = start
    end_lat, end_lng = end
    mid_lat = (start_lat + end_lat) / 2.0
    mid_lng = (start_lng + end_lng) / 2.0
    return [
        _lnglat(start_lat, start_lng),
        _lnglat(mid_lat, mid_lng),
        _lnglat(end_lat, end_lng),
    ]


async def _segment_coordinates(
    start_lat: float,
    start_lng: float,
    end_lat: float,
    end_lng: float,
) -> list[list[float]]:
    """Return route segment coordinates in MapLibre [lng, lat] order."""

    route = await get_route_polyline(start_lat, start_lng, end_lat, end_lng)
    if not route:
        return _fallback_segment((start_lat, start_lng), (end_lat, end_lng))
    return [_lnglat(lat, lng) for lat, lng in route]


async def _route_coordinates(
    ambulance: dict[str, Any],
    incident: dict[str, Any],
    hospital: dict[str, Any],
) -> list[list[float]]:
    """Return ambulance -> incident -> hospital route coordinates."""

    to_scene, to_hospital = await asyncio.gather(
        _segment_coordinates(
            float(ambulance["current_lat"]),
            float(ambulance["current_lng"]),
            float(incident["location_lat"]),
            float(incident["location_lng"]),
        ),
        _segment_coordinates(
            float(incident["location_lat"]),
            float(incident["location_lng"]),
            float(hospital["lat"]),
            float(hospital["lng"]),
        ),
    )
    return to_scene + to_hospital[1:]


async def _score_ambulance_option(
    ambulance: dict[str, Any],
    incident: dict[str, Any],
    hospital: dict[str, Any],
    traffic_multiplier: float,
) -> dict[str, Any]:
    """Score one ambulance option for command-center comparison."""

    scene_eta, hospital_eta = await asyncio.gather(
        get_travel_time(
            float(ambulance["current_lat"]),
            float(ambulance["current_lng"]),
            float(incident["location_lat"]),
            float(incident["location_lng"]),
            city=incident.get("city"),
        ),
        get_travel_time(
            float(incident["location_lat"]),
            float(incident["location_lng"]),
            float(hospital["lat"]),
            float(hospital["lng"]),
            city=incident.get("city") or hospital.get("city"),
        ),
    )
    distance_score = max(0.0, min(1.0, 1.0 - (float(scene_eta) / 45.0)))
    traffic_score = max(0.0, min(1.0, 1.0 - ((float(traffic_multiplier) - 1.0) / 3.0)))
    hospital_load_score = max(0.0, min(1.0, 1.0 - (float(hospital.get("occupancy_pct", 100.0)) / 100.0)))
    crew_score = max(0.0, min(1.0, float(ambulance.get("crew_readiness", 0.0))))
    total_score = (
        (0.4 * distance_score)
        + (0.2 * traffic_score)
        + (0.25 * hospital_load_score)
        + (0.15 * crew_score)
    )
    return {
        "ambulance_id": ambulance["id"],
        "hospital_id": hospital["id"],
        "status": ambulance.get("status"),
        "eta_to_scene_minutes": round(float(scene_eta), 2),
        "eta_to_hospital_minutes": round(float(hospital_eta), 2),
        "total_eta_minutes": round(float(scene_eta) + float(hospital_eta), 2),
        "score": round(total_score, 4),
        "score_breakdown": {
            "distance": round(distance_score, 4),
            "traffic": round(traffic_score, 4),
            "hospital_load": round(hospital_load_score, 4),
            "crew_readiness": round(crew_score, 4),
        },
    }


async def _rank_ambulance_options(
    incident: dict[str, Any],
    ambulances: list[dict[str, Any]],
    hospital: dict[str, Any],
    *,
    selected_ambulance_id: str | None = None,
    limit: int = 4,
) -> list[dict[str, Any]]:
    """Return ranked ambulance options for admin dispatch visualization."""

    city = incident.get("city") or hospital.get("city")
    traffic_multiplier = get_active_traffic_multiplier(str(city)) if city else 1.0
    candidates = [
        ambulance
        for ambulance in ambulances
        if ambulance.get("status") != "unavailable"
        and (not city or _resource_in_service_area(ambulance, city))
    ]
    if selected_ambulance_id and not any(item["id"] == selected_ambulance_id for item in candidates):
        selected = next((item for item in ambulances if item["id"] == selected_ambulance_id), None)
        if selected is not None and selected.get("status") != "unavailable" and _resource_in_service_area(selected, city):
            candidates.append(selected)

    scored = await asyncio.gather(
        *[
            _score_ambulance_option(ambulance, incident, hospital, traffic_multiplier)
            for ambulance in candidates
        ]
    )
    scored = sorted(scored, key=lambda item: (-float(item["score"]), float(item["total_eta_minutes"])))
    selected = [item for item in scored if item["ambulance_id"] == selected_ambulance_id]
    remaining = [item for item in scored if item["ambulance_id"] != selected_ambulance_id]
    return (selected + remaining)[:limit]


def _route_status_label(ambulance: dict[str, Any] | None, eta_minutes: float) -> str:
    status = ambulance.get("status") if ambulance else None
    if status == "at_scene":
        return "On scene"
    if status == "transporting":
        return "Transporting patient"
    if eta_minutes <= 2:
        return f"Arriving in {max(1, round(eta_minutes))} mins"
    if status == "en_route":
        return "En route"
    return "Dispatched"


async def build_dispatch_map_context(
    dispatch_plan: dict[str, Any],
    *,
    incident: dict[str, Any] | None = None,
    ambulance: dict[str, Any] | None = None,
    hospital: dict[str, Any] | None = None,
    ambulances: list[dict[str, Any]] | None = None,
    hospitals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build route geometry, alternatives, and score payload for a dispatch."""

    incident_repo = IncidentRepository()
    ambulance_repo = AmbulanceRepository()
    hospital_repo = HospitalRepository()
    incident = incident or await incident_repo.get_by_id(str(dispatch_plan["incident_id"]))
    ambulance = ambulance or await ambulance_repo.get_by_id(str(dispatch_plan["ambulance_id"]))
    hospital = hospital or await hospital_repo.get_by_id(str(dispatch_plan["hospital_id"]))
    if incident is None or ambulance is None or hospital is None:
        return {}

    all_ambulances = ambulances or await ambulance_repo.get_all()
    all_hospitals = hospitals or await hospital_repo.get_all()
    city = incident.get("city") or hospital.get("city")
    if not _route_entities_city_local(incident, ambulance, hospital):
        return {
            "route": None,
            "alternate_routes": [],
            "ambulance_options": [],
            "service_city": city,
            "manual_escalation": True,
            "reroute_blocked_reason": MANUAL_ESCALATION_TEXT,
            "map_entities": {
                "incident": incident,
                "ambulance": ambulance,
                "hospital": hospital,
                "hospitals": all_hospitals,
            },
        }

    route_task = _route_coordinates(ambulance, incident, hospital)
    options_task = _rank_ambulance_options(
        incident,
        all_ambulances,
        hospital,
        selected_ambulance_id=str(dispatch_plan["ambulance_id"]),
    )
    coordinates, ambulance_options = await asyncio.gather(route_task, options_task)

    option_by_id = {item["ambulance_id"]: item for item in ambulance_options}
    selected_option = option_by_id.get(str(dispatch_plan["ambulance_id"]))
    eta_minutes = float(
        selected_option["total_eta_minutes"]
        if selected_option is not None
        else dispatch_plan.get("eta_minutes", 0.0)
    )

    alternate_routes: list[dict[str, Any]] = []
    alternate_options = [item for item in ambulance_options if item["ambulance_id"] != dispatch_plan["ambulance_id"]]
    ambulance_by_id = {item["id"]: item for item in all_ambulances}
    for option in alternate_options[:3]:
        alternate_ambulance = ambulance_by_id.get(option["ambulance_id"])
        if alternate_ambulance is None:
            continue
        alternate_coordinates = await _route_coordinates(alternate_ambulance, incident, hospital)
        alternate_routes.append(
            {
                "ambulance_id": option["ambulance_id"],
                "hospital_id": hospital["id"],
                "eta_minutes": option["total_eta_minutes"],
                "score": option["score"],
                "coordinates": alternate_coordinates,
            }
        )

    return {
        "route": {
            "dispatch_id": dispatch_plan.get("id"),
            "incident_id": incident["id"],
            "ambulance_id": ambulance["id"],
            "hospital_id": hospital["id"],
            "service_city": city,
            "eta_minutes": round(eta_minutes, 2),
            "status_label": _route_status_label(ambulance, eta_minutes),
            "traffic_multiplier": get_active_traffic_multiplier(str(city)) if city else 1.0,
            "coordinates": coordinates,
            "updated_at": isoformat_utc(),
        },
        "alternate_routes": alternate_routes,
        "ambulance_options": ambulance_options,
        "map_entities": {
            "incident": incident,
            "ambulance": ambulance,
            "hospital": hospital,
            "hospitals": all_hospitals,
        },
    }


async def build_dispatch_update_event(dispatch_plan: dict[str, Any], **context: Any) -> dict[str, Any]:
    """Return a WebSocket dispatch_update event."""

    map_context = await build_dispatch_map_context(dispatch_plan, **context)
    return {
        "type": "dispatch_update",
        "dispatch_id": dispatch_plan.get("id"),
        "dispatch_plan": dispatch_plan,
        **map_context,
    }


async def build_active_dispatch_eta_events(limit: int = 5) -> list[dict[str, Any]]:
    """Return lightweight ETA updates for active dispatches without refetching polylines."""

    dispatch_repo = DispatchRepository()
    ambulance_repo = AmbulanceRepository()
    hospital_repo = HospitalRepository()
    incident_repo = IncidentRepository()
    events: list[dict[str, Any]] = []
    for dispatch_plan in (await dispatch_repo.get_active())[:limit]:
        incident = await incident_repo.get_by_id(str(dispatch_plan["incident_id"]))
        ambulance = await ambulance_repo.get_by_id(str(dispatch_plan["ambulance_id"]))
        hospital = await hospital_repo.get_by_id(str(dispatch_plan["hospital_id"]))
        if incident is None or ambulance is None or hospital is None:
            continue
        if not _route_entities_city_local(incident, ambulance, hospital):
            continue
        status = ambulance.get("status")
        if status == "transporting":
            eta_minutes = await get_travel_time(
                float(ambulance["current_lat"]),
                float(ambulance["current_lng"]),
                float(hospital["lat"]),
                float(hospital["lng"]),
                city=incident.get("city") or hospital.get("city"),
            )
        elif status == "at_scene":
            eta_minutes = await get_travel_time(
                float(incident["location_lat"]),
                float(incident["location_lng"]),
                float(hospital["lat"]),
                float(hospital["lng"]),
                city=incident.get("city") or hospital.get("city"),
            )
        else:
            eta_to_scene, eta_to_hospital = await asyncio.gather(
                get_travel_time(
                    float(ambulance["current_lat"]),
                    float(ambulance["current_lng"]),
                    float(incident["location_lat"]),
                    float(incident["location_lng"]),
                    city=incident.get("city"),
                ),
                get_travel_time(
                    float(incident["location_lat"]),
                    float(incident["location_lng"]),
                    float(hospital["lat"]),
                    float(hospital["lng"]),
                    city=incident.get("city") or hospital.get("city"),
                ),
            )
            eta_minutes = eta_to_scene + eta_to_hospital
        eta_minutes = round(float(eta_minutes), 2)
        events.append(
            {
                "type": "dispatch_update",
                "dispatch_id": dispatch_plan.get("id"),
                "dispatch_plan": {
                    "id": dispatch_plan.get("id"),
                    "incident_id": dispatch_plan.get("incident_id"),
                    "ambulance_id": dispatch_plan.get("ambulance_id"),
                    "hospital_id": dispatch_plan.get("hospital_id"),
                    "eta_minutes": eta_minutes,
                    "status": dispatch_plan.get("status"),
                    "updated_at": isoformat_utc(),
                },
                "route": {
                    "dispatch_id": dispatch_plan.get("id"),
                    "incident_id": incident["id"],
                    "ambulance_id": ambulance["id"],
                    "hospital_id": hospital["id"],
                    "eta_minutes": eta_minutes,
                    "status_label": _route_status_label(ambulance, eta_minutes),
                    "traffic_multiplier": get_active_traffic_multiplier(str(incident.get("city") or hospital.get("city"))),
                    "updated_at": isoformat_utc(),
                },
            }
        )
    return events


def _route_change_label(reason: str) -> str:
    labels = {
        "traffic": "Rerouting due to traffic",
        "hospital_load": "Rerouting due to hospital load",
        "ambulance_breakdown": "Rerouting due to ambulance breakdown",
    }
    return labels.get(reason, "Rerouting due to live conditions")


def _blocked_route_change_event(
    base_event: dict[str, Any],
    dispatch_plan: dict[str, Any],
    old_route: dict[str, Any] | None,
    selection: dict[str, Any] | None,
    service_city: str | None,
) -> dict[str, Any]:
    reason = (
        selection.get("reroute_blocked_reason")
        if selection
        else MANUAL_ESCALATION_TEXT
    )
    return {
        **base_event,
        "dispatch_id": dispatch_plan.get("id"),
        "old_route": old_route,
        "new_route": None,
        "alternate_routes": [],
        "ambulance_options": [],
        "manual_escalation": True,
        "service_city": service_city,
        "reroute_blocked_reason": reason or MANUAL_ESCALATION_TEXT,
        "label": "Manual escalation required; no same-city unit/hospital available",
    }


def _matches_route_change(
    dispatch_plan: dict[str, Any],
    incident: dict[str, Any] | None,
    hospital: dict[str, Any] | None,
    *,
    city: str | None,
    affected_ambulance_id: str | None,
    affected_hospital_id: str | None,
) -> bool:
    if affected_ambulance_id and dispatch_plan.get("ambulance_id") == affected_ambulance_id:
        return True
    if affected_hospital_id and dispatch_plan.get("hospital_id") == affected_hospital_id:
        return True
    if city:
        return city in {incident.get("city") if incident else None, hospital.get("city") if hospital else None}
    return True


async def build_route_change_event(
    *,
    reason: str,
    city: str | None = None,
    affected_ambulance_id: str | None = None,
    affected_hospital_id: str | None = None,
) -> dict[str, Any]:
    """Build a route_change event for active dispatches impacted by a simulation mutation."""

    dispatch_repo = DispatchRepository()
    incident_repo = IncidentRepository()
    ambulance_repo = AmbulanceRepository()
    hospital_repo = HospitalRepository()
    active_dispatches = await dispatch_repo.get_active()
    base_event: dict[str, Any] = {
        "type": "route_change",
        "reason": reason,
        "label": _route_change_label(reason),
        "city": city,
        "affected_ambulance_id": affected_ambulance_id,
        "affected_hospital_id": affected_hospital_id,
        "timestamp": isoformat_utc(),
    }
    blocked_candidate: dict[str, Any] | None = None

    for dispatch_plan in active_dispatches:
        incident = await incident_repo.get_by_id(str(dispatch_plan["incident_id"]))
        current_ambulance = await ambulance_repo.get_by_id(str(dispatch_plan["ambulance_id"]))
        current_hospital = await hospital_repo.get_by_id(str(dispatch_plan["hospital_id"]))
        if not _matches_route_change(
            dispatch_plan,
            incident,
            current_hospital,
            city=city,
            affected_ambulance_id=affected_ambulance_id,
            affected_hospital_id=affected_hospital_id,
        ):
            continue
        if incident is None or current_ambulance is None or current_hospital is None:
            continue

        ambulances, hospitals = await asyncio.gather(
            ambulance_repo.get_all(),
            hospital_repo.get_all(),
        )
        old_context = await build_dispatch_map_context(
            dispatch_plan,
            incident=incident,
            ambulance=current_ambulance,
            hospital=current_hospital,
            ambulances=ambulances,
            hospitals=hospitals,
        )
        old_route = old_context.get("route")
        if old_route is None:
            blocked_candidate = blocked_candidate or _blocked_route_change_event(
                base_event,
                dispatch_plan,
                None,
                None,
                incident.get("city"),
            )
            continue

        selection = await select_dispatch(incident, ambulances, hospitals)
        if selection.get("status") == "error":
            return _blocked_route_change_event(
                base_event,
                dispatch_plan,
                old_route,
                selection,
                selection.get("service_city") or incident.get("city"),
            )

        next_ambulance = await ambulance_repo.get_by_id(str(selection["ambulance_id"]))
        next_hospital = await hospital_repo.get_by_id(str(selection["hospital_id"]))
        if next_ambulance is None or next_hospital is None:
            return _blocked_route_change_event(
                base_event,
                dispatch_plan,
                old_route,
                None,
                selection.get("service_city") or incident.get("city"),
            )
        if not _route_entities_city_local(incident, next_ambulance, next_hospital):
            return _blocked_route_change_event(
                base_event,
                dispatch_plan,
                old_route,
                selection,
                selection.get("service_city") or incident.get("city"),
            )

        next_dispatch = {
            **dispatch_plan,
            "ambulance_id": selection["ambulance_id"],
            "hospital_id": selection["hospital_id"],
            "eta_minutes": selection["eta_minutes"],
            "score_breakdown": selection.get("score_breakdown"),
            "baseline_eta_minutes": selection.get("baseline_eta_minutes"),
            "explanation_text": selection.get("explanation_text"),
        }
        new_context = await build_dispatch_map_context(
            next_dispatch,
            incident=incident,
            ambulance=next_ambulance,
            hospital=next_hospital,
            ambulances=ambulances,
            hospitals=hospitals,
        )
        return {
            **base_event,
            "dispatch_id": dispatch_plan.get("id"),
            "old_route": old_route,
            "new_route": new_context.get("route"),
            "alternate_routes": new_context.get("alternate_routes", []),
            "ambulance_options": new_context.get("ambulance_options", []),
            "manual_escalation": False,
            "service_city": selection.get("service_city") or incident.get("city"),
            "score_breakdown": selection.get("score_breakdown"),
        }

    return blocked_candidate or base_event
