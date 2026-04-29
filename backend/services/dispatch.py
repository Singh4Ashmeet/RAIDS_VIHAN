"""Formal multi-objective dispatch scoring for ambulance and hospital selection."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from typing import Any, Optional

from services.routing import get_travel_time


@dataclass(slots=True)
class DispatchWeights:
    w1: float = 0.40
    w2: float = 0.25
    w3: float = 0.15
    w4: float = 0.10
    w5: float = 0.10


_SPECIALTY_RULES: dict[str, tuple[str, float]] = {
    "cardiac": ("cardiology", 0.5),
    "respiratory": ("pulmonology", 0.5),
    "trauma": ("surgery", 0.5),
    "stroke": ("neurology", 0.5),
    "accident": ("orthopedics", 0.6),
}

_SPECIALTY_ALIASES: dict[str, str] = {
    "cardiac": "cardiology",
    "cardiology": "cardiology",
    "respiratory": "pulmonology",
    "pulmonology": "pulmonology",
    "trauma": "surgery",
    "surgery": "surgery",
    "neuro": "neurology",
    "neurology": "neurology",
    "ortho": "orthopedics",
    "orthopedics": "orthopedics",
    "orthopaedics": "orthopedics",
}


def _inverse_score(value: float, minimum: float) -> float:
    return 1.0 / max(float(value), minimum)


def _normalize_specialties(hospital: dict[str, Any]) -> set[str]:
    normalized: set[str] = set()
    for item in hospital.get("specialties", []):
        label = str(item).strip().lower()
        normalized.add(_SPECIALTY_ALIASES.get(label, label))
    return normalized


def specialty_match(hospital: dict[str, Any], incident_type: str) -> float:
    """Return the hospital specialty score for an incident type."""

    if hospital.get("diversion_status"):
        return 0.0

    normalized_type = str(incident_type).strip().lower()
    if normalized_type not in _SPECIALTY_RULES:
        return 0.8

    required_specialty, fallback_score = _SPECIALTY_RULES[normalized_type]
    return 1.0 if required_specialty in _normalize_specialties(hospital) else fallback_score


def _evaluate_pair(
    incident: dict[str, Any],
    ambulance: dict[str, Any],
    hospital: dict[str, Any],
    weights: DispatchWeights,
    eta_to_scene: float,
    eta_to_hospital: float,
) -> dict[str, Any]:
    components = {
        "eta_score": _inverse_score(eta_to_scene, 0.1),
        "specialty_score": specialty_match(hospital, incident.get("type", "")),
        "crew_readiness_score": float(ambulance.get("crew_readiness", 0.0)),
        "capacity_score": max(0.0, 1.0 - (float(hospital.get("occupancy_pct", 100.0)) / 100.0)),
        "er_wait_score": _inverse_score(float(hospital.get("er_wait_minutes", 0.0)), 1.0),
    }
    total_score = (
        (weights.w1 * components["eta_score"])
        + (weights.w2 * components["specialty_score"])
        + (weights.w3 * components["crew_readiness_score"])
        + (weights.w4 * components["capacity_score"])
        + (weights.w5 * components["er_wait_score"])
    )
    if hospital.get("diversion_status"):
        total_score *= 0.0

    return {
        "ambulance": ambulance,
        "hospital": hospital,
        "components": components,
        "total_score": total_score,
        "eta_to_scene_minutes": eta_to_scene,
        "eta_to_hospital_minutes": eta_to_hospital,
        "total_eta_minutes": eta_to_scene + eta_to_hospital,
    }


def _score_all_pairs(
    incident: dict[str, Any],
    ambulances: list[dict[str, Any]],
    hospitals: list[dict[str, Any]],
    scene_eta_by_ambulance: dict[str, float],
    hospital_eta_by_hospital: dict[str, float],
    weights: DispatchWeights,
) -> list[dict[str, Any]]:
    return [
        _evaluate_pair(
            incident,
            ambulance,
            hospital,
            weights,
            scene_eta_by_ambulance[ambulance["id"]],
            hospital_eta_by_hospital[hospital["id"]],
        )
        for ambulance in ambulances
        for hospital in hospitals
    ]


async def _precompute_scene_etas(
    incident: dict[str, Any],
    ambulances: list[dict[str, Any]],
) -> dict[str, float]:
    if not ambulances:
        return {}

    eta_values = await asyncio.gather(
        *[
            get_travel_time(
                ambulance["current_lat"],
                ambulance["current_lng"],
                incident["location_lat"],
                incident["location_lng"],
                city=incident.get("city"),
            )
            for ambulance in ambulances
        ]
    )
    return {
        ambulance["id"]: eta
        for ambulance, eta in zip(ambulances, eta_values, strict=False)
    }


async def _precompute_hospital_etas(
    incident: dict[str, Any],
    hospitals: list[dict[str, Any]],
) -> dict[str, float]:
    if not hospitals:
        return {}

    eta_values = await asyncio.gather(
        *[
            get_travel_time(
                incident["location_lat"],
                incident["location_lng"],
                hospital["lat"],
                hospital["lng"],
                city=incident.get("city"),
            )
            for hospital in hospitals
        ]
    )
    return {
        hospital["id"]: eta
        for hospital, eta in zip(hospitals, eta_values, strict=False)
    }


async def _compute_baseline_eta(
    available_ambulances: list[dict[str, Any]],
    hospitals: list[dict[str, Any]],
    scene_eta_by_ambulance: dict[str, float],
    hospital_eta_by_hospital: dict[str, float],
) -> float | None:
    if not available_ambulances or not hospitals:
        return None

    nearest_ambulance = min(
        available_ambulances,
        key=lambda ambulance: scene_eta_by_ambulance[ambulance["id"]],
    )
    nearest_hospital = min(
        hospitals,
        key=lambda hospital: hospital_eta_by_hospital[hospital["id"]],
    )
    return round(
        scene_eta_by_ambulance[nearest_ambulance["id"]] + hospital_eta_by_hospital[nearest_hospital["id"]],
        2,
    )


def _weights_used(weights: DispatchWeights) -> dict[str, float]:
    return asdict(weights)


def _required_specialty_label(incident_type: str) -> str:
    return _SPECIALTY_RULES.get(str(incident_type).strip().lower(), ("general care", 0.8))[0]


def _reason_texts(pair_result: dict[str, Any], incident_type: str) -> dict[str, str]:
    ambulance = pair_result["ambulance"]
    hospital = pair_result["hospital"]
    components = pair_result["components"]
    required_specialty = _required_specialty_label(incident_type)
    specialty_score = components["specialty_score"]
    occupancy_pct = float(hospital.get("occupancy_pct", 100.0))
    er_wait_minutes = float(hospital.get("er_wait_minutes", 0.0))

    if str(incident_type).strip().lower() in _SPECIALTY_RULES:
        if specialty_score >= 1.0:
            specialty_reason = f"{hospital['id']} has {required_specialty} coverage"
        else:
            specialty_reason = f"{hospital['id']} is the best available {required_specialty} fallback"
    else:
        specialty_reason = f"{hospital['id']} is a strong general-purpose match ({specialty_score:.1f})"

    return {
        "eta_score": f"fastest scene ETA ({pair_result['eta_to_scene_minutes']:.1f} min)",
        "specialty_score": specialty_reason,
        "crew_readiness_score": (
            f"{ambulance['id']} crew readiness is {float(ambulance.get('crew_readiness', 0.0)) * 100:.0f}%"
        ),
        "capacity_score": f"{hospital['id']} has {max(0.0, 100.0 - occupancy_pct):.0f}% capacity headroom",
        "er_wait_score": f"{hospital['id']} ER wait is {er_wait_minutes:.0f} min",
    }


def _build_explanation_text(
    pair_result: dict[str, Any],
    incident_type: str,
    weights: DispatchWeights,
) -> str:
    weight_order = [
        ("eta_score", weights.w1),
        ("specialty_score", weights.w2),
        ("crew_readiness_score", weights.w3),
        ("capacity_score", weights.w4),
        ("er_wait_score", weights.w5),
    ]
    ordered_components = [name for name, _ in sorted(weight_order, key=lambda item: item[1], reverse=True)[:3]]
    reasons = _reason_texts(pair_result, incident_type)
    top_reasons = [reasons[name] for name in ordered_components]
    return f"{pair_result['ambulance']['id']} selected: {top_reasons[0]}, {top_reasons[1]}, {top_reasons[2]}."


def _choose_fallback_ambulance(
    ambulances: list[dict[str, Any]],
    available_ambulances: list[dict[str, Any]],
) -> dict[str, Any] | None:
    pool = available_ambulances or ambulances
    if not pool:
        return None
    return min(pool, key=lambda ambulance: float(ambulance.get("crew_readiness", 1.0)))


def _choose_fallback_hospital(hospitals: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not hospitals:
        return None

    non_full_hospitals = [hospital for hospital in hospitals if float(hospital.get("occupancy_pct", 100.0)) < 100.0]
    pool = non_full_hospitals or hospitals
    return min(pool, key=lambda hospital: (float(hospital.get("occupancy_pct", 100.0)), float(hospital.get("er_wait_minutes", 999.0))))


async def select_dispatch(
    incident: dict,
    ambulances: list[dict],
    hospitals: list[dict],
    weights: Optional[DispatchWeights] = None,
) -> dict:
    """Select the best ambulance and hospital pair for an incident."""

    active_weights = weights or DispatchWeights()
    available_ambulances = [ambulance for ambulance in ambulances if ambulance.get("status") == "available"]
    eligible_hospitals = [hospital for hospital in hospitals if not hospital.get("diversion_status")]
    scene_eta_by_ambulance = await _precompute_scene_etas(incident, available_ambulances)
    hospital_eta_by_hospital = await _precompute_hospital_etas(incident, hospitals)
    baseline_eta_minutes = await _compute_baseline_eta(
        available_ambulances,
        hospitals,
        scene_eta_by_ambulance,
        hospital_eta_by_hospital,
    )

    if not ambulances or not hospitals:
        return {
            "status": "error",
            "ambulance_id": "",
            "hospital_id": "",
            "eta_minutes": 0.0,
            "score_breakdown": None,
            "baseline_eta_minutes": baseline_eta_minutes,
            "explanation_text": "No ambulance or hospital records are available for dispatch.",
        }

    if not available_ambulances or not eligible_hospitals:
        fallback_ambulance = _choose_fallback_ambulance(ambulances, available_ambulances)
        fallback_hospital = _choose_fallback_hospital(hospitals)
        if fallback_ambulance is None or fallback_hospital is None:
            return {
                "status": "error",
                "ambulance_id": "",
                "hospital_id": "",
                "eta_minutes": 0.0,
                "score_breakdown": None,
                "baseline_eta_minutes": baseline_eta_minutes,
                "explanation_text": "Fallback dispatch could not find a usable ambulance or hospital.",
            }

        eta_to_scene = scene_eta_by_ambulance.get(fallback_ambulance["id"])
        if eta_to_scene is None:
            eta_to_scene = await get_travel_time(
                fallback_ambulance["current_lat"],
                fallback_ambulance["current_lng"],
                incident["location_lat"],
                incident["location_lng"],
                city=incident.get("city"),
            )

        eta_to_hospital = hospital_eta_by_hospital.get(fallback_hospital["id"])
        if eta_to_hospital is None:
            eta_to_hospital = await get_travel_time(
                incident["location_lat"],
                incident["location_lng"],
                fallback_hospital["lat"],
                fallback_hospital["lng"],
                city=incident.get("city"),
            )
        return {
            "status": "fallback",
            "ambulance_id": fallback_ambulance["id"],
            "hospital_id": fallback_hospital["id"],
            "eta_minutes": round(eta_to_scene + eta_to_hospital, 2),
            "score_breakdown": None,
            "baseline_eta_minutes": baseline_eta_minutes,
            "explanation_text": (
                f"{fallback_ambulance['id']} selected: last-resort fallback dispatch, "
                f"{fallback_hospital['id']} chosen as the available non-full hospital, "
                f"total ETA {eta_to_scene + eta_to_hospital:.1f} min."
            ),
        }

    pair_results = await asyncio.to_thread(
        _score_all_pairs,
        incident,
        available_ambulances,
        eligible_hospitals,
        scene_eta_by_ambulance,
        hospital_eta_by_hospital,
        active_weights,
    )
    best_pair = max(
        pair_results,
        key=lambda item: (item["total_score"], -item["total_eta_minutes"]),
    )

    score_breakdown = {
        "ambulance_id": best_pair["ambulance"]["id"],
        "hospital_id": best_pair["hospital"]["id"],
        "total_score": round(best_pair["total_score"], 4),
        "components": {
            "eta_score": round(best_pair["components"]["eta_score"], 4),
            "specialty_score": round(best_pair["components"]["specialty_score"], 4),
            "crew_readiness_score": round(best_pair["components"]["crew_readiness_score"], 4),
            "capacity_score": round(best_pair["components"]["capacity_score"], 4),
            "er_wait_score": round(best_pair["components"]["er_wait_score"], 4),
        },
        "weights_used": _weights_used(active_weights),
        "eta_to_scene_minutes": round(best_pair["eta_to_scene_minutes"], 2),
        "eta_to_hospital_minutes": round(best_pair["eta_to_hospital_minutes"], 2),
        "total_eta_minutes": round(best_pair["total_eta_minutes"], 2),
    }
    return {
        "status": "success",
        "ambulance_id": best_pair["ambulance"]["id"],
        "hospital_id": best_pair["hospital"]["id"],
        "eta_minutes": round(best_pair["total_eta_minutes"], 2),
        "score_breakdown": score_breakdown,
        "baseline_eta_minutes": baseline_eta_minutes,
        "explanation_text": _build_explanation_text(best_pair, incident.get("type", ""), active_weights),
    }
