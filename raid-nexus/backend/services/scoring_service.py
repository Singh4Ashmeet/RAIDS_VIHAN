"""Dispatch scoring helpers for ambulances, hospitals, and routing."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from config import ANALYTICS_OVERLOAD_THRESHOLD, INCIDENT_EQUIPMENT_REQUIREMENTS, INCIDENT_SPECIALTY_REQUIREMENTS, isoformat_utc
from services.geo_service import get_active_traffic_multiplier, route_travel_minutes, score_route


def _equipment_match_score(ambulance: dict[str, Any], incident_type: str) -> float:
    required = INCIDENT_EQUIPMENT_REQUIREMENTS.get(incident_type, [])
    if not required:
        return 1.0
    equipment = set(ambulance.get("equipment", []))
    matches = sum(1 for item in required if item in equipment)
    return matches / len(required)


def _availability_score(status: str) -> float:
    if status == "available":
        return 1.0
    if status == "at_hospital":
        return 0.3
    return 0.0


def evaluate_ambulance(ambulance: dict[str, Any], incident: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a single ambulance candidate for an incident."""

    traffic_multiplier = get_active_traffic_multiplier(incident["city"])
    route = score_route(
        ambulance["current_lat"],
        ambulance["current_lng"],
        incident["location_lat"],
        incident["location_lng"],
        traffic_multiplier,
        incident["city"],
    )
    eta_minutes = route["travel_time_minutes"]
    eta_score = max(0.0, 1.0 - (eta_minutes / 30.0))
    equipment_score = _equipment_match_score(ambulance, incident["type"])
    crew_score = float(ambulance["crew_readiness"])
    availability_score = _availability_score(ambulance["status"])
    final_score = (
        (eta_score * 0.40)
        + (equipment_score * 0.25)
        + (crew_score * 0.20)
        + (availability_score * 0.15)
    )
    return {
        "id": ambulance["id"],
        "score": round(final_score, 3),
        "eta_minutes": round(eta_minutes, 2),
        "breakdown": {
            "eta_score": round(eta_score, 3),
            "equipment_score": round(equipment_score, 3),
            "crew_readiness_score": round(crew_score, 3),
            "availability_score": round(availability_score, 3),
        },
        "route": route,
    }


def evaluate_hospital(
    hospital: dict[str, Any],
    incident: dict[str, Any],
    origin_lat: float,
    origin_lng: float,
) -> dict[str, Any]:
    """Evaluate a single hospital candidate for a transport destination."""

    traffic_multiplier = get_active_traffic_multiplier(incident["city"])
    route = score_route(origin_lat, origin_lng, hospital["lat"], hospital["lng"], traffic_multiplier, incident["city"])
    specialty_requirements = INCIDENT_SPECIALTY_REQUIREMENTS.get(incident["type"])
    if specialty_requirements:
        specialty_score = 1.0 if (hospital["type"] in specialty_requirements or any(spec in hospital["specialties"] for spec in specialty_requirements)) else 0.0
    else:
        specialty_score = 0.5
    occupancy_score = max(0.0, 1.0 - (float(hospital["occupancy_pct"]) / 100.0))
    er_wait_score = max(0.0, 1.0 - (int(hospital["er_wait_minutes"]) / 60.0))
    travel_time_score = max(0.0, 1.0 - (route["travel_time_minutes"] / 40.0))
    icu_score = float(hospital["icu_beds_available"]) / max(int(hospital["total_icu_beds"]), 1)
    final_score = (
        (specialty_score * 0.30)
        + (occupancy_score * 0.25)
        + (er_wait_score * 0.20)
        + (travel_time_score * 0.15)
        + (icu_score * 0.10)
    )
    if hospital["diversion_status"]:
        final_score *= 0.1
    return {
        "id": hospital["id"],
        "score": round(final_score, 3),
        "travel_minutes": round(route["travel_time_minutes"], 2),
        "breakdown": {
            "specialty_score": round(specialty_score, 3),
            "occupancy_score": round(occupancy_score, 3),
            "er_wait_score": round(er_wait_score, 3),
            "travel_time_score": round(travel_time_score, 3),
            "icu_score": round(icu_score, 3),
        },
        "route": route,
        "occupancy_pct": hospital["occupancy_pct"],
        "diversion_status": hospital["diversion_status"],
    }


def compute_baseline_eta(
    incident: dict[str, Any],
    ambulances: list[dict[str, Any]],
    hospitals: list[dict[str, Any]],
) -> tuple[float | None, dict[str, Any] | None]:
    """Compute the simple nearest-neighbor baseline ETA and chosen baseline hospital."""

    available_ambulances = [ambulance for ambulance in ambulances if ambulance["city"] == incident["city"] and ambulance["status"] == "available"]
    eligible_hospitals = [hospital for hospital in hospitals if hospital["city"] == incident["city"] and not hospital["diversion_status"]]
    if not available_ambulances or not eligible_hospitals:
        return None, None

    nearest_ambulance = min(
        available_ambulances,
        key=lambda item: score_route(
            item["current_lat"],
            item["current_lng"],
            incident["location_lat"],
            incident["location_lng"],
            get_active_traffic_multiplier(incident["city"]),
            incident["city"],
        )["travel_time_minutes"],
    )
    nearest_hospital = min(
        eligible_hospitals,
        key=lambda item: score_route(
            incident["location_lat"],
            incident["location_lng"],
            item["lat"],
            item["lng"],
            get_active_traffic_multiplier(incident["city"]),
            incident["city"],
        )["travel_time_minutes"],
    )
    pickup_minutes = score_route(
        nearest_ambulance["current_lat"],
        nearest_ambulance["current_lng"],
        incident["location_lat"],
        incident["location_lng"],
        get_active_traffic_multiplier(incident["city"]),
        incident["city"],
    )["travel_time_minutes"]
    hospital_minutes = score_route(
        incident["location_lat"],
        incident["location_lng"],
        nearest_hospital["lat"],
        nearest_hospital["lng"],
        get_active_traffic_multiplier(incident["city"]),
        incident["city"],
    )["travel_time_minutes"]
    return round(pickup_minutes + hospital_minutes, 2), nearest_hospital


def select_best_dispatch(
    incident: dict[str, Any],
    all_ambulances: list[dict[str, Any]],
    all_hospitals: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate candidates and return the best dispatch payload."""

    valid_ambulances = [
        ambulance
        for ambulance in all_ambulances
        if ambulance["city"] == incident["city"] and ambulance["status"] in {"available", "at_hospital"}
    ]
    if not valid_ambulances:
        raise ValueError(f"No ambulances available in {incident['city']}.")

    scored_ambulances = [evaluate_ambulance(ambulance, incident) for ambulance in valid_ambulances]
    scored_ambulances.sort(key=lambda item: item["score"], reverse=True)
    top_ambulances = scored_ambulances[:3]

    city_hospitals = [hospital for hospital in all_hospitals if hospital["city"] == incident["city"]]
    if not city_hospitals:
        raise ValueError(f"No hospitals configured in {incident['city']}.")

    best_combo: dict[str, Any] | None = None
    best_hospital_scores: list[dict[str, Any]] = []
    for ambulance_score in top_ambulances:
        ambulance = next(item for item in valid_ambulances if item["id"] == ambulance_score["id"])
        hospital_scores = [
            evaluate_hospital(
                hospital,
                incident,
                incident["location_lat"],
                incident["location_lng"],
            )
            for hospital in city_hospitals
        ]
        hospital_scores.sort(key=lambda item: item["score"], reverse=True)

        for hospital_score in hospital_scores:
            total_route_to_incident = ambulance_score["route"]
            total_route_to_hospital = hospital_score["route"]
            total_distance = round(
                total_route_to_incident["distance_km"] + total_route_to_hospital["distance_km"],
                3,
            )
            total_eta = round(
                total_route_to_incident["travel_time_minutes"] + total_route_to_hospital["travel_time_minutes"],
                2,
            )
            total_route_score = max(0.0, 1.0 - (total_eta / 45.0))
            final_score = (
                (ambulance_score["score"] * 0.40)
                + (hospital_score["score"] * 0.40)
                + (total_route_score * 0.20)
            )
            candidate = {
                "ambulance": ambulance,
                "hospital": next(item for item in city_hospitals if item["id"] == hospital_score["id"]),
                "ambulance_score": ambulance_score,
                "hospital_score": hospital_score,
                "route_score": round(total_route_score, 3),
                "eta_minutes": total_eta,
                "distance_km": total_distance,
                "final_score": round(final_score, 3),
            }
            if best_combo is None or candidate["final_score"] > best_combo["final_score"]:
                best_combo = candidate
                best_hospital_scores = hospital_scores

    if best_combo is None:
        raise ValueError("Dispatch selection failed to produce a candidate.")

    rejected_ambulances = []
    for ambulance_score in scored_ambulances:
        if ambulance_score["id"] == best_combo["ambulance"]["id"]:
            continue
        rejected_ambulances.append(
            {
                "id": ambulance_score["id"],
                "score": ambulance_score["score"],
                "eta_minutes": ambulance_score["eta_minutes"],
                "reason": "Lower combined dispatch utility than selected ambulance.",
                "breakdown": ambulance_score["breakdown"],
            }
        )

    rejected_hospitals = []
    fallback_hospital_id = None
    if len(best_hospital_scores) > 1:
        fallback_hospital_id = best_hospital_scores[1]["id"]
    for hospital_score in best_hospital_scores:
        if hospital_score["id"] == best_combo["hospital"]["id"]:
            continue
        rejected_hospitals.append(
            {
                "id": hospital_score["id"],
                "score": hospital_score["score"],
                "travel_minutes": hospital_score["travel_minutes"],
                "occupancy_pct": hospital_score["occupancy_pct"],
                "diversion_status": hospital_score["diversion_status"],
                "reason": "Lower hospital suitability than selected destination.",
                "breakdown": hospital_score["breakdown"],
            }
        )

    baseline_eta, baseline_hospital = compute_baseline_eta(incident, all_ambulances, all_hospitals)
    overload_avoided = bool(
        baseline_hospital
        and baseline_hospital["id"] != best_combo["hospital"]["id"]
        and (
            baseline_hospital["diversion_status"]
            or float(baseline_hospital["occupancy_pct"]) >= ANALYTICS_OVERLOAD_THRESHOLD
        )
    )

    explanation_text = (
        f"Selected ambulance {best_combo['ambulance']['id']} for {incident['severity']} "
        f"{incident['type']} incident in {incident['city']} based on response ETA "
        f"({best_combo['ambulance_score']['eta_minutes']} min), equipment match, crew readiness, "
        f"and destination hospital {best_combo['hospital']['id']} suitability."
    )
    return {
        "id": str(uuid4()),
        "incident_id": incident["id"],
        "patient_id": incident.get("patient_id"),
        "ambulance_id": best_combo["ambulance"]["id"],
        "hospital_id": best_combo["hospital"]["id"],
        "ambulance_score": best_combo["ambulance_score"]["score"],
        "hospital_score": best_combo["hospital_score"]["score"],
        "route_score": best_combo["route_score"],
        "final_score": best_combo["final_score"],
        "eta_minutes": best_combo["eta_minutes"],
        "distance_km": best_combo["distance_km"],
        "rejected_ambulances": rejected_ambulances,
        "rejected_hospitals": rejected_hospitals,
        "explanation_text": explanation_text,
        "fallback_hospital_id": fallback_hospital_id,
        "created_at": isoformat_utc(),
        "status": "dispatched",
        "baseline_eta_minutes": baseline_eta,
        "overload_avoided": overload_avoided,
    }
