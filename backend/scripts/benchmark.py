"""Benchmark RAID Nexus dispatch strategies on synthetic incidents."""

from __future__ import annotations

import argparse
import asyncio
import copy
import csv
import heapq
import json
import logging
import math
import random
import sys
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import count
from pathlib import Path
from statistics import fmean, pstdev
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Final

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import CITY_AMBULANCE_BASE_SPEED_KMH, DATA_DIR, isoformat_utc
from services.demand_predictor import build_density_grid
from services.dispatch import select_dispatch
from services.fairness import compare_fairness, compute_fairness_metrics
from services.routing import get_travel_time

ALL_INCIDENTS_PATH: Final[Path] = DATA_DIR / "synthetic_incidents.json"
TRAIN_INCIDENTS_PATH: Final[Path] = DATA_DIR / "train_incidents.json"
TEST_INCIDENTS_PATH: Final[Path] = DATA_DIR / "test_incidents.json"
HOSPITALS_PATH: Final[Path] = DATA_DIR / "hospitals.csv"
AMBULANCES_PATH: Final[Path] = DATA_DIR / "ambulances.csv"
OUTPUT_PATH: Final[Path] = DATA_DIR / "benchmark_results.json"
CROSS_CITY_OUTPUT_PATH: Final[Path] = DATA_DIR / "cross_city_results.json"

SUPPORTED_CITIES: Final[list[str]] = ["Delhi", "Mumbai", "Bengaluru", "Chennai", "Hyderabad"]

HOSPITAL_COLUMNS: Final[list[str]] = [
    "id",
    "name",
    "city",
    "lat",
    "lng",
    "total_beds",
    "occupied_beds",
    "specialties",
    "er_wait_minutes",
    "diversion_status",
]

AMBULANCE_COLUMNS: Final[list[str]] = [
    "id",
    "city",
    "lat",
    "lng",
    "status",
    "type",
    "crew_readiness",
    "driver_name",
    "paramedic_name",
]

SPECIALTY_RULES: Final[dict[str, str]] = {
    "cardiac": "cardiology",
    "respiratory": "pulmonology",
    "trauma": "surgery",
    "stroke": "neurology",
    "accident": "orthopedics",
}

SPECIALTY_ALIASES: Final[dict[str, str]] = {
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

TREATMENT_TIME_MINUTES: Final[float] = 15.0
AVERAGE_STAY_MINUTES: Final[float] = 120.0
DELAY_PENALTY_MINUTES: Final[float] = 20.0
OVERLOAD_THRESHOLD_PCT: Final[float] = 90.0

STRATEGY_METADATA: Final[OrderedDict[str, dict[str, Any]]] = OrderedDict(
    [
        ("ai_dispatch", {"flag": "ai", "label": "AI Dispatch", "seed": 1101}),
        ("nearest_unit", {"flag": "nearest", "label": "Nearest Unit", "seed": 2202}),
        ("random_dispatch", {"flag": "random", "label": "Random", "seed": 3303}),
    ]
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

logging.getLogger("raid.routing").setLevel(logging.ERROR)
logging.getLogger("raid.traffic").setLevel(logging.ERROR)


@dataclass
class CityState:
    """Mutable simulation state for one city during one benchmark strategy."""

    ambulances_by_id: dict[str, dict[str, Any]]
    hospitals_by_id: dict[str, dict[str, Any]]
    hospital_events: list[tuple[datetime, int, str, str]]
    event_counter: count


@dataclass
class DispatchSelection:
    """Normalized dispatch decision returned by each strategy implementation."""

    ambulance: dict[str, Any]
    hospital: dict[str, Any]
    eta_to_scene_minutes: float
    eta_to_hospital_minutes: float
    wait_minutes: float
    was_delayed: bool


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description="Benchmark RAID Nexus dispatch strategies.")
    parser.add_argument(
        "--strategy",
        choices=["ai", "nearest", "random"],
        help="Run only one strategy instead of all three.",
    )
    parser.add_argument(
        "--incidents",
        type=int,
        help="Limit the number of incidents processed.",
    )
    parser.add_argument(
        "--split",
        choices=["train", "test", "all"],
        default="all",
        help="Evaluation split for standard benchmark mode.",
    )
    parser.add_argument(
        "--mode",
        choices=["standard", "cross_city"],
        default="standard",
        help="Benchmark mode.",
    )
    args = parser.parse_args()
    if args.mode == "cross_city" and args.strategy is not None:
        parser.error("--strategy cannot be used with --mode cross_city.")
    return args


def _load_csv_rows(path: Path, expected_columns: list[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Required input file not found: {path}")

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        actual_columns = reader.fieldnames or []
        if actual_columns != expected_columns:
            raise ValueError(
                f"{path.name} columns do not match expected order. "
                f"Expected {expected_columns}, got {actual_columns}."
            )
        return list(reader)


def _normalize_specialties(specialties: list[str]) -> set[str]:
    normalized: set[str] = set()
    for specialty in specialties:
        label = specialty.strip().lower()
        normalized.add(SPECIALTY_ALIASES.get(label, label))
    return normalized


def _specialty_matched(incident_type: str, hospital: dict[str, Any]) -> bool:
    required_specialty = SPECIALTY_RULES.get(str(incident_type).strip().lower())
    if required_specialty is None:
        return True
    return required_specialty in _normalize_specialties(hospital.get("specialties", []))


def _build_hospital_record(row: dict[str, str]) -> dict[str, Any]:
    total_beds = int(row["total_beds"])
    occupied_beds = int(row["occupied_beds"])
    specialties = [item.strip() for item in row["specialties"].split("|") if item.strip()]
    occupancy_pct = round((occupied_beds / total_beds) * 100.0, 2) if total_beds else 0.0
    return {
        "id": row["id"].strip(),
        "name": row["name"].strip(),
        "city": row["city"].strip(),
        "lat": float(row["lat"]),
        "lng": float(row["lng"]),
        "total_beds": total_beds,
        "occupied_beds": occupied_beds,
        "occupancy_pct": occupancy_pct,
        "specialties": specialties,
        "er_wait_minutes": int(row["er_wait_minutes"]),
        "diversion_status": str(row["diversion_status"]).strip().lower() == "true",
    }


def _build_ambulance_record(row: dict[str, str]) -> dict[str, Any]:
    return {
        "id": row["id"].strip(),
        "city": row["city"].strip(),
        "current_lat": float(row["lat"]),
        "current_lng": float(row["lng"]),
        "status": row["status"].strip(),
        "type": row["type"].strip(),
        "crew_readiness": float(row["crew_readiness"]),
        "driver_name": row["driver_name"].strip(),
        "paramedic_name": row["paramedic_name"].strip(),
        "busy_until": None,
        "pending_lat": None,
        "pending_lng": None,
    }


def load_hospitals(path: Path = HOSPITALS_PATH) -> list[dict[str, Any]]:
    """Load and normalize hospital benchmark inputs."""

    return [_build_hospital_record(row) for row in _load_csv_rows(path, HOSPITAL_COLUMNS)]


def load_ambulances(path: Path = AMBULANCES_PATH) -> list[dict[str, Any]]:
    """Load and normalize ambulance benchmark inputs."""

    return [_build_ambulance_record(row) for row in _load_csv_rows(path, AMBULANCE_COLUMNS)]


def _dataset_path_for_split(split: str) -> Path:
    if split == "train":
        return TRAIN_INCIDENTS_PATH
    if split == "test":
        return TEST_INCIDENTS_PATH
    return ALL_INCIDENTS_PATH


def load_incidents(path: Path, limit: int | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Load synthetic incidents and sort them by timestamp."""

    if not path.is_file():
        raise FileNotFoundError(f"Synthetic incident file not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    metadata = dict(payload.get("metadata", {})) if isinstance(payload, dict) else {}
    incidents = list(payload.get("incidents", [])) if isinstance(payload, dict) else list(payload)
    incidents.sort(key=lambda incident: datetime.fromisoformat(incident["timestamp"]))
    if limit is not None:
        if limit <= 0:
            raise ValueError("--incidents must be a positive integer.")
        incidents = incidents[:limit]
    return metadata, incidents


def _group_by_city(records: list[dict[str, Any]]) -> OrderedDict[str, list[dict[str, Any]]]:
    grouped: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for record in records:
        grouped.setdefault(record["city"], []).append(record)
    return grouped


def _build_strategy_state(
    ambulances_by_city: OrderedDict[str, list[dict[str, Any]]],
    hospitals_by_city: OrderedDict[str, list[dict[str, Any]]],
) -> dict[str, CityState]:
    state: dict[str, CityState] = {}
    for city in hospitals_by_city.keys():
        ambulance_records = [copy.deepcopy(item) for item in ambulances_by_city.get(city, [])]
        hospital_records = [copy.deepcopy(item) for item in hospitals_by_city.get(city, [])]
        state[city] = CityState(
            ambulances_by_id={item["id"]: item for item in ambulance_records},
            hospitals_by_id={item["id"]: item for item in hospital_records},
            hospital_events=[],
            event_counter=count(),
        )
    return state


def _refresh_hospital_occupancy(hospital: dict[str, Any]) -> None:
    total_beds = max(int(hospital["total_beds"]), 1)
    hospital["occupied_beds"] = max(0, min(int(hospital["occupied_beds"]), total_beds))
    hospital["occupancy_pct"] = round((hospital["occupied_beds"] / total_beds) * 100.0, 2)


def _advance_city_state(city_state: CityState, current_time: datetime) -> None:
    for ambulance in city_state.ambulances_by_id.values():
        busy_until = ambulance.get("busy_until")
        if busy_until is not None and busy_until <= current_time:
            if ambulance.get("pending_lat") is not None:
                ambulance["current_lat"] = float(ambulance["pending_lat"])
                ambulance["current_lng"] = float(ambulance["pending_lng"])
            ambulance["pending_lat"] = None
            ambulance["pending_lng"] = None
            ambulance["busy_until"] = None
            ambulance["status"] = "available"

    while city_state.hospital_events and city_state.hospital_events[0][0] <= current_time:
        _, _, event_type, hospital_id = heapq.heappop(city_state.hospital_events)
        hospital = city_state.hospitals_by_id[hospital_id]
        if event_type == "admit":
            hospital["occupied_beds"] += 1
        elif event_type == "discharge":
            hospital["occupied_beds"] = max(0, hospital["occupied_beds"] - 1)
        _refresh_hospital_occupancy(hospital)


def _schedule_hospital_events(city_state: CityState, hospital_id: str, arrival_time: datetime) -> None:
    admission_counter = next(city_state.event_counter)
    discharge_counter = next(city_state.event_counter)
    discharge_time = arrival_time + timedelta(minutes=AVERAGE_STAY_MINUTES)
    heapq.heappush(city_state.hospital_events, (arrival_time, admission_counter, "admit", hospital_id))
    heapq.heappush(city_state.hospital_events, (discharge_time, discharge_counter, "discharge", hospital_id))


def _minutes_until(reference_time: datetime, future_time: datetime | None) -> float:
    if future_time is None:
        return 0.0
    return max(0.0, (future_time - reference_time).total_seconds() / 60.0)


def _haversine_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius_km = 6371.0
    lat1_rad = math.radians(lat1)
    lng1_rad = math.radians(lng1)
    lat2_rad = math.radians(lat2)
    lng2_rad = math.radians(lng2)
    delta_lat = lat2_rad - lat1_rad
    delta_lng = lng2_rad - lng1_rad
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


def _distance_minutes(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    distance_km = _haversine_distance_km(lat1, lng1, lat2, lng2)
    return round((distance_km / CITY_AMBULANCE_BASE_SPEED_KMH) * 60.0, 2)


def _incident_time(incident: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(str(incident["timestamp"]))


def _normalize_incident_for_ai(incident: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": incident["id"],
        "type": incident["type"],
        "severity": incident["severity"],
        "location_lat": float(incident["lat"]),
        "location_lng": float(incident["lng"]),
        "city": incident["city"],
        "description": incident["description"],
    }


def _available_ambulances(city_state: CityState) -> list[dict[str, Any]]:
    return [ambulance for ambulance in city_state.ambulances_by_id.values() if ambulance["status"] == "available"]


def _eligible_random_hospitals(city_state: CityState) -> list[dict[str, Any]]:
    eligible = [hospital for hospital in city_state.hospitals_by_id.values() if not hospital["diversion_status"]]
    return eligible or list(city_state.hospitals_by_id.values())


def _earliest_release_ambulance(city_state: CityState, current_time: datetime) -> dict[str, Any]:
    ambulances = list(city_state.ambulances_by_id.values())
    if not ambulances:
        raise RuntimeError("No ambulances configured for this city.")
    return min(
        ambulances,
        key=lambda ambulance: (
            ambulance.get("busy_until") or current_time,
            ambulance["id"],
        ),
    )


def _materialize_future_ambulance(ambulance: dict[str, Any]) -> dict[str, Any]:
    candidate = copy.deepcopy(ambulance)
    if ambulance.get("pending_lat") is not None:
        candidate["current_lat"] = float(ambulance["pending_lat"])
        candidate["current_lng"] = float(ambulance["pending_lng"])
    candidate["status"] = "available"
    candidate["busy_until"] = None
    candidate["pending_lat"] = None
    candidate["pending_lng"] = None
    return candidate


async def _resolve_ai_route_legs(
    selection: dict[str, Any],
    incident: dict[str, Any],
    hospital: dict[str, Any],
    candidate_lookup: dict[str, dict[str, Any]],
) -> tuple[float, float]:
    score_breakdown = selection.get("score_breakdown") or {}
    eta_to_scene = score_breakdown.get("eta_to_scene_minutes")
    eta_to_hospital = score_breakdown.get("eta_to_hospital_minutes")
    if eta_to_scene is not None and eta_to_hospital is not None:
        return float(eta_to_scene), float(eta_to_hospital)

    candidate = candidate_lookup[selection["ambulance_id"]]
    incident_lat = float(incident["lat"])
    incident_lng = float(incident["lng"])
    eta_to_scene = await get_travel_time(
        float(candidate["current_lat"]),
        float(candidate["current_lng"]),
        incident_lat,
        incident_lng,
        city=incident["city"],
    )
    eta_to_hospital = await get_travel_time(
        incident_lat,
        incident_lng,
        float(hospital["lat"]),
        float(hospital["lng"]),
        city=incident["city"],
    )
    return float(eta_to_scene), float(eta_to_hospital)


async def run_ai_dispatch(city_state: CityState, incident: dict[str, Any], rng: random.Random) -> DispatchSelection:
    """Evaluate the AI dispatch scorer on the current city state."""

    _ = rng
    current_time = _incident_time(incident)
    available = _available_ambulances(city_state)
    wait_minutes = 0.0
    was_delayed = False

    if available:
        ambulance_pool = [copy.deepcopy(ambulance) for ambulance in available]
    else:
        actual_ambulance = _earliest_release_ambulance(city_state, current_time)
        wait_minutes = max(DELAY_PENALTY_MINUTES, _minutes_until(current_time, actual_ambulance.get("busy_until")))
        was_delayed = True
        ambulance_pool = [_materialize_future_ambulance(actual_ambulance)]

    candidate_lookup = {ambulance["id"]: ambulance for ambulance in ambulance_pool}
    hospital_pool = [copy.deepcopy(hospital) for hospital in city_state.hospitals_by_id.values()]
    selection = await select_dispatch(_normalize_incident_for_ai(incident), ambulance_pool, hospital_pool)
    if selection["status"] == "error":
        raise RuntimeError(f"AI dispatch failed for {incident['id']}: {selection['explanation_text']}")

    ambulance = city_state.ambulances_by_id[selection["ambulance_id"]]
    hospital = city_state.hospitals_by_id[selection["hospital_id"]]
    eta_to_scene, eta_to_hospital = await _resolve_ai_route_legs(selection, incident, hospital, candidate_lookup)
    return DispatchSelection(
        ambulance=ambulance,
        hospital=hospital,
        eta_to_scene_minutes=round(eta_to_scene, 2),
        eta_to_hospital_minutes=round(eta_to_hospital, 2),
        wait_minutes=round(wait_minutes, 2),
        was_delayed=was_delayed,
    )


async def run_nearest_unit(city_state: CityState, incident: dict[str, Any], rng: random.Random) -> DispatchSelection:
    """Select the nearest ambulance and nearest hospital by Haversine distance."""

    _ = rng
    current_time = _incident_time(incident)
    incident_lat = float(incident["lat"])
    incident_lng = float(incident["lng"])
    available = _available_ambulances(city_state)

    if available:
        ambulance = min(
            available,
            key=lambda candidate: _haversine_distance_km(
                float(candidate["current_lat"]),
                float(candidate["current_lng"]),
                incident_lat,
                incident_lng,
            ),
        )
        candidate = ambulance
        wait_minutes = 0.0
        was_delayed = False
    else:
        ambulance = _earliest_release_ambulance(city_state, current_time)
        candidate = _materialize_future_ambulance(ambulance)
        wait_minutes = max(DELAY_PENALTY_MINUTES, _minutes_until(current_time, ambulance.get("busy_until")))
        was_delayed = True

    hospital = min(
        city_state.hospitals_by_id.values(),
        key=lambda item: _haversine_distance_km(incident_lat, incident_lng, float(item["lat"]), float(item["lng"])),
    )
    eta_to_scene = _distance_minutes(float(candidate["current_lat"]), float(candidate["current_lng"]), incident_lat, incident_lng)
    eta_to_hospital = _distance_minutes(incident_lat, incident_lng, float(hospital["lat"]), float(hospital["lng"]))
    return DispatchSelection(
        ambulance=ambulance,
        hospital=hospital,
        eta_to_scene_minutes=eta_to_scene,
        eta_to_hospital_minutes=eta_to_hospital,
        wait_minutes=round(wait_minutes, 2),
        was_delayed=was_delayed,
    )


async def run_random_dispatch(city_state: CityState, incident: dict[str, Any], rng: random.Random) -> DispatchSelection:
    """Select a random available ambulance and a random non-diversion hospital."""

    current_time = _incident_time(incident)
    incident_lat = float(incident["lat"])
    incident_lng = float(incident["lng"])
    available = _available_ambulances(city_state)

    if available:
        ambulance = rng.choice(available)
        candidate = ambulance
        wait_minutes = 0.0
        was_delayed = False
    else:
        ambulance = _earliest_release_ambulance(city_state, current_time)
        candidate = _materialize_future_ambulance(ambulance)
        wait_minutes = max(DELAY_PENALTY_MINUTES, _minutes_until(current_time, ambulance.get("busy_until")))
        was_delayed = True

    hospital = rng.choice(_eligible_random_hospitals(city_state))
    eta_to_scene = _distance_minutes(float(candidate["current_lat"]), float(candidate["current_lng"]), incident_lat, incident_lng)
    eta_to_hospital = _distance_minutes(incident_lat, incident_lng, float(hospital["lat"]), float(hospital["lng"]))
    return DispatchSelection(
        ambulance=ambulance,
        hospital=hospital,
        eta_to_scene_minutes=eta_to_scene,
        eta_to_hospital_minutes=eta_to_hospital,
        wait_minutes=round(wait_minutes, 2),
        was_delayed=was_delayed,
    )


def _build_per_incident_record(
    incident: dict[str, Any],
    strategy_key: str,
    selection: DispatchSelection,
) -> dict[str, Any]:
    hospital_capacity_pct = (float(selection.hospital["occupied_beds"]) / max(int(selection.hospital["total_beds"]), 1)) * 100.0
    eta_minutes = round(selection.eta_to_scene_minutes + selection.wait_minutes, 2)
    total_time_minutes = round(selection.eta_to_scene_minutes + selection.eta_to_hospital_minutes + selection.wait_minutes, 2)
    return {
        "incident_id": incident["id"],
        "city": incident["city"],
        "lat": float(incident["lat"]),
        "lng": float(incident["lng"]),
        "incident_type": incident["type"],
        "type": incident["type"],
        "severity": incident["severity"],
        "timestamp": incident["timestamp"],
        "eta_minutes": eta_minutes,
        "total_time_minutes": total_time_minutes,
        "hospital_selected": selection.hospital["id"],
        "ambulance_selected": selection.ambulance["id"],
        "specialty_matched": _specialty_matched(incident["type"], selection.hospital),
        "hospital_at_capacity": hospital_capacity_pct > OVERLOAD_THRESHOLD_PCT,
        "was_delayed": selection.was_delayed,
        "strategy": strategy_key,
    }


def _apply_dispatch_to_state(city_state: CityState, incident_time: datetime, selection: DispatchSelection) -> None:
    dispatch_start = incident_time + timedelta(minutes=selection.wait_minutes)
    route_minutes = selection.eta_to_scene_minutes + selection.eta_to_hospital_minutes
    arrival_time = dispatch_start + timedelta(minutes=route_minutes)
    busy_until = dispatch_start + timedelta(minutes=route_minutes + TREATMENT_TIME_MINUTES)

    ambulance = selection.ambulance
    ambulance["status"] = "en_route"
    ambulance["busy_until"] = busy_until
    ambulance["pending_lat"] = float(selection.hospital["lat"])
    ambulance["pending_lng"] = float(selection.hospital["lng"])

    _schedule_hospital_events(city_state, selection.hospital["id"], arrival_time)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return round(values[0], 2)

    ordered = sorted(values)
    rank = (len(ordered) - 1) * (percentile / 100.0)
    lower_index = math.floor(rank)
    upper_index = math.ceil(rank)
    if lower_index == upper_index:
        return round(ordered[lower_index], 2)
    fraction = rank - lower_index
    interpolated = ordered[lower_index] + ((ordered[upper_index] - ordered[lower_index]) * fraction)
    return round(interpolated, 2)


def _aggregate_metrics(per_incident: list[dict[str, Any]]) -> dict[str, Any]:
    eta_values = [float(item["eta_minutes"]) for item in per_incident]
    total_values = [float(item["total_time_minutes"]) for item in per_incident]
    specialty_matches = sum(1 for item in per_incident if item["specialty_matched"])
    overload_events = sum(1 for item in per_incident if item["hospital_at_capacity"])
    delayed_incidents = sum(1 for item in per_incident if item["was_delayed"])
    total = len(per_incident)

    return {
        "avg_eta_minutes": round(fmean(eta_values), 2) if eta_values else 0.0,
        "avg_total_time_minutes": round(fmean(total_values), 2) if total_values else 0.0,
        "specialty_match_rate": round((specialty_matches / total) * 100.0, 2) if total else 0.0,
        "overload_events": overload_events,
        "delayed_incidents": delayed_incidents,
        "p50_eta": _percentile(eta_values, 50),
        "p90_eta": _percentile(eta_values, 90),
        "p95_eta": _percentile(eta_values, 95),
        "per_incident": per_incident,
    }


def _relative_improvement(baseline_value: float, candidate_value: float) -> float:
    if baseline_value == 0:
        return 0.0
    return round(((baseline_value - candidate_value) / baseline_value) * 100.0, 2)


def _relative_lift(baseline_value: float, candidate_value: float) -> float:
    if baseline_value == 0:
        return 0.0 if candidate_value == 0 else 100.0
    return round(((candidate_value - baseline_value) / baseline_value) * 100.0, 2)


def _generalization_gap_pct(held_out_value: float, cross_city_value: float) -> float:
    if held_out_value == 0:
        return 0.0
    return round(abs(held_out_value - cross_city_value) / abs(held_out_value) * 100.0, 2)


def build_comparison(strategies: dict[str, dict[str, Any]]) -> dict[str, float | None]:
    """Build the top-line comparison metrics across strategies."""

    ai = strategies.get("ai_dispatch")
    nearest = strategies.get("nearest_unit")
    random_strategy = strategies.get("random_dispatch")
    return {
        "ai_vs_nearest_eta_improvement_pct": (
            _relative_improvement(nearest["avg_eta_minutes"], ai["avg_eta_minutes"])
            if ai and nearest
            else None
        ),
        "ai_vs_nearest_specialty_improvement_pct": (
            _relative_lift(nearest["specialty_match_rate"], ai["specialty_match_rate"])
            if ai and nearest
            else None
        ),
        "ai_vs_nearest_overload_reduction_pct": (
            _relative_improvement(float(nearest["overload_events"]), float(ai["overload_events"]))
            if ai and nearest
            else None
        ),
        "ai_vs_random_eta_improvement_pct": (
            _relative_improvement(random_strategy["avg_eta_minutes"], ai["avg_eta_minutes"])
            if ai and random_strategy
            else None
        ),
    }


async def build_fairness_report(strategies: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build fairness metrics for each benchmark strategy."""

    strategy_items = list(strategies.items())
    metric_values = await asyncio.gather(
        *[
            compute_fairness_metrics(payload.get("per_incident", []), strategy_key)
            for strategy_key, payload in strategy_items
        ]
    )
    fairness = {
        strategy_key: metric_value
        for (strategy_key, _), metric_value in zip(strategy_items, metric_values, strict=False)
    }

    ai_metrics = fairness.get("ai_dispatch")
    nearest_metrics = fairness.get("nearest_unit")
    fairness["comparison"] = (
        await asyncio.to_thread(compare_fairness, ai_metrics, nearest_metrics)
        if ai_metrics and nearest_metrics
        else {}
    )
    return fairness


def _format_metric_value(metric_key: str, value: Any) -> str:
    if metric_key in {"overload_events", "delayed_incidents"}:
        return f"{int(value)}"
    if metric_key == "specialty_match_rate":
        return f"{float(value):.1f}%"
    return f"{float(value):.1f}"


def _build_border(column_widths: list[int], left: str, middle: str, right: str) -> str:
    return left + middle.join("─" * (width + 2) for width in column_widths) + right


def _build_row(column_widths: list[int], values: list[str]) -> str:
    cells = [f" {value.ljust(column_widths[index])} " for index, value in enumerate(values)]
    return "│" + "│".join(cells) + "│"


def print_evaluation_header(evaluation: dict[str, Any]) -> None:
    """Print the benchmark dataset header."""

    evaluation_file = evaluation["evaluation_dataset"]
    evaluation_count = int(evaluation["evaluation_count"])
    if evaluation.get("held_out"):
        print(f"Evaluation dataset: {evaluation_file} (held-out, N={evaluation_count})")
    else:
        print(f"Evaluation dataset: {evaluation_file} (N={evaluation_count})")
    print(
        f"Training dataset:   {evaluation['training_dataset']} (N={int(evaluation['training_count'])})"
    )
    print(f"Split method: {evaluation['split_method']}")
    print()


def print_results_table(strategies: dict[str, dict[str, Any]]) -> None:
    """Print a compact benchmark summary table to stdout."""

    metric_rows = [
        ("Avg ETA (min)", "avg_eta_minutes"),
        ("Avg Total Time (min)", "avg_total_time_minutes"),
        ("Specialty Match Rate", "specialty_match_rate"),
        ("Overload Events", "overload_events"),
        ("Delayed Incidents", "delayed_incidents"),
        ("P50 ETA", "p50_eta"),
        ("P90 ETA", "p90_eta"),
        ("P95 ETA", "p95_eta"),
    ]

    strategy_items = list(strategies.items())
    headers = ["Metric"] + [STRATEGY_METADATA[key]["label"] for key, _ in strategy_items]
    rows = []
    for label, metric_key in metric_rows:
        row = [label]
        for _, payload in strategy_items:
            row.append(_format_metric_value(metric_key, payload[metric_key]))
        rows.append(row)

    column_widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]

    print(_build_border(column_widths, "┌", "┬", "┐"))
    print(_build_row(column_widths, headers))
    print(_build_border(column_widths, "├", "┼", "┤"))
    for row in rows:
        print(_build_row(column_widths, row))
    print(_build_border(column_widths, "└", "┴", "┘"))


def print_fairness_table(fairness: dict[str, Any]) -> None:
    """Print a compact fairness summary table to stdout."""

    ai = fairness.get("ai_dispatch")
    nearest = fairness.get("nearest_unit")
    if not ai or not nearest:
        return

    rows = [
        ("Equity Score", f"{float(ai['equity_score']):.1f}", f"{float(nearest['equity_score']):.1f}"),
        ("Disparity Ratio", f"{float(ai['disparity_ratio']):.2f}", f"{float(nearest['disparity_ratio']):.2f}"),
        (
            "Peripheral Penalty %",
            f"{float(ai['peripheral_penalty_pct']):.1f}%",
            f"{float(nearest['peripheral_penalty_pct']):.1f}%",
        ),
        ("Fairness Win", "✓" if ai["fairness_win"] else "✗", "✓" if nearest["fairness_win"] else "✗"),
    ]
    headers = ["Fairness Metric", "AI Dispatch", "Nearest Unit"]
    column_widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]

    print()
    print(_build_border(column_widths, "┌", "┬", "┐"))
    print(_build_row(column_widths, headers))
    print(_build_border(column_widths, "├", "┼", "┤"))
    for row in rows:
        print(_build_row(column_widths, list(row)))
    print(_build_border(column_widths, "└", "┴", "┘"))


def print_cross_city_table(cities_payload: OrderedDict[str, dict[str, Any]], summary: dict[str, Any]) -> None:
    """Print the cross-city generalization table."""

    rows: list[list[str]] = []
    ai_avg_values: list[float] = []
    nearest_avg_values: list[float] = []
    improvement_values: list[float] = []

    for city, metrics in cities_payload.items():
        ai_avg = float(metrics["ai_avg_eta"])
        nearest_avg = float(metrics["nearest_avg_eta"])
        improvement = float(metrics["ai_improvement_pct"])
        ai_avg_values.append(ai_avg)
        nearest_avg_values.append(nearest_avg)
        improvement_values.append(improvement)
        rows.append(
            [
                city,
                f"{ai_avg:.1f} min",
                f"{nearest_avg:.1f} min",
                f"{improvement:+.1f}%",
            ]
        )

    mean_ai = fmean(ai_avg_values) if ai_avg_values else 0.0
    mean_nearest = fmean(nearest_avg_values) if nearest_avg_values else 0.0
    mean_improvement = fmean(improvement_values) if improvement_values else 0.0
    std_ai = pstdev(ai_avg_values) if len(ai_avg_values) > 1 else 0.0
    std_nearest = pstdev(nearest_avg_values) if len(nearest_avg_values) > 1 else 0.0
    std_improvement = pstdev(improvement_values) if len(improvement_values) > 1 else 0.0

    rows.extend(
        [
            ["MEAN", f"{mean_ai:.1f} min", f"{mean_nearest:.1f} min", f"{mean_improvement:+.1f}%"],
            ["STD DEV", f"±{std_ai:.1f} min", f"±{std_nearest:.1f} min", f"±{std_improvement:.1f}%"],
        ]
    )

    headers = ["Test City", "AI Avg ETA", "Nearest ETA", "AI Improve"]
    column_widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]

    print()
    print(_build_border(column_widths, "┌", "┬", "┐"))
    print(_build_row(column_widths, headers))
    print(_build_border(column_widths, "├", "┼", "┤"))
    for index, row in enumerate(rows):
        if index == len(rows) - 2:
            print(_build_border(column_widths, "├", "┼", "┤"))
        print(_build_row(column_widths, row))
    print(_build_border(column_widths, "└", "┴", "┘"))
    print(f"Generalization: {summary['generalization_assessment']} (std < 3% = Strong, 3-8% = Moderate, > 8% = Weak)")


async def evaluate_strategy(
    strategy_key: str,
    incidents: list[dict[str, Any]],
    initial_ambulances_by_city: OrderedDict[str, list[dict[str, Any]]],
    initial_hospitals_by_city: OrderedDict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Run one dispatch strategy over the benchmark incident set."""

    rng = random.Random(STRATEGY_METADATA[strategy_key]["seed"])
    strategy_state = await asyncio.to_thread(
        _build_strategy_state,
        initial_ambulances_by_city,
        initial_hospitals_by_city,
    )
    runner_map: dict[str, Callable[[CityState, dict[str, Any], random.Random], Any]] = {
        "ai_dispatch": run_ai_dispatch,
        "nearest_unit": run_nearest_unit,
        "random_dispatch": run_random_dispatch,
    }
    runner = runner_map[strategy_key]

    per_incident: list[dict[str, Any]] = []
    for incident in incidents:
        city = incident["city"]
        city_state = strategy_state[city]
        incident_time = _incident_time(incident)
        await asyncio.to_thread(_advance_city_state, city_state, incident_time)
        selection = await runner(city_state, incident, rng)
        per_incident_record = await asyncio.to_thread(
            _build_per_incident_record,
            incident,
            strategy_key,
            selection,
        )
        per_incident.append(per_incident_record)
        await asyncio.to_thread(_apply_dispatch_to_state, city_state, incident_time, selection)

    return await asyncio.to_thread(_aggregate_metrics, per_incident)


async def evaluate_strategies(
    incidents: list[dict[str, Any]],
    ambulances_by_city: OrderedDict[str, list[dict[str, Any]]],
    hospitals_by_city: OrderedDict[str, list[dict[str, Any]]],
    *,
    strategy_filter: str | None = None,
) -> OrderedDict[str, dict[str, Any]]:
    """Evaluate one or more strategies on the provided incidents."""

    selected_strategies = OrderedDict(
        (key, meta)
        for key, meta in STRATEGY_METADATA.items()
        if strategy_filter is None or meta["flag"] == strategy_filter
    )

    strategy_results: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for strategy_key in selected_strategies.keys():
        strategy_results[strategy_key] = await evaluate_strategy(
            strategy_key,
            incidents,
            ambulances_by_city,
            hospitals_by_city,
        )
    return strategy_results


def save_results(payload: dict[str, Any], output_path: Path) -> None:
    """Persist a JSON results payload."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def _training_reference_metadata() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return load_incidents(TRAIN_INCIDENTS_PATH)


def _build_standard_evaluation_block(
    split: str,
    evaluation_path: Path,
    evaluation_metadata: dict[str, Any],
    incidents: list[dict[str, Any]],
    training_metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "mode": "standard",
        "split": split,
        "evaluation_dataset": evaluation_path.name,
        "evaluation_count": len(incidents),
        "training_dataset": TRAIN_INCIDENTS_PATH.name,
        "training_count": int(training_metadata.get("total_incidents", 0)),
        "split_method": "chronological (test = last 200 generated)",
        "held_out": split == "test",
        "evaluation_generated_at": evaluation_metadata.get("generated_at"),
    }


def _build_cross_city_temp_payload(
    base_metadata: dict[str, Any],
    incidents: list[dict[str, Any]],
    held_out_city: str,
) -> dict[str, Any]:
    metadata = dict(base_metadata)
    metadata["total_incidents"] = len(incidents)
    metadata["split"] = f"cross_city_train_excluding_{held_out_city.lower()}"
    metadata["split_note"] = (
        f"Cross-city calibration set excluding {held_out_city}. "
        "Used to rebuild the demand grid for methodological separation."
    )
    return {
        "metadata": metadata,
        "incidents": incidents,
    }


async def _build_cross_city_density_grid(base_metadata: dict[str, Any], incidents: list[dict[str, Any]], held_out_city: str) -> None:
    temp_path: str | None = None
    try:
        payload = _build_cross_city_temp_payload(base_metadata, incidents, held_out_city)
        with NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=True)
            temp_path = handle.name
        await asyncio.to_thread(build_density_grid, temp_path, True)
    finally:
        if temp_path is not None:
            Path(temp_path).unlink(missing_ok=True)


def _generalization_assessment(std_improvement_pct: float) -> str:
    if std_improvement_pct < 3.0:
        return "Strong"
    if std_improvement_pct <= 8.0:
        return "Moderate"
    return "Weak"


async def run_standard_mode(args: argparse.Namespace) -> dict[str, Any]:
    """Run the split-aware standard benchmark and persist benchmark_results.json."""

    evaluation_path = _dataset_path_for_split(args.split)
    training_metadata, _ = await asyncio.to_thread(_training_reference_metadata)
    evaluation_metadata, incidents = await asyncio.to_thread(load_incidents, evaluation_path, args.incidents)
    hospitals = await asyncio.to_thread(load_hospitals)
    ambulances = await asyncio.to_thread(load_ambulances)
    hospitals_by_city = await asyncio.to_thread(_group_by_city, hospitals)
    ambulances_by_city = await asyncio.to_thread(_group_by_city, ambulances)

    strategy_results = await evaluate_strategies(
        incidents,
        ambulances_by_city,
        hospitals_by_city,
        strategy_filter=args.strategy,
    )
    evaluation_block = _build_standard_evaluation_block(
        args.split,
        evaluation_path,
        evaluation_metadata,
        incidents,
        training_metadata,
    )
    payload = {
        "generated_at": isoformat_utc(),
        "total_incidents": len(incidents),
        "evaluation": evaluation_block,
        "strategies": strategy_results,
        "comparison": await asyncio.to_thread(build_comparison, strategy_results),
        "fairness": await build_fairness_report(strategy_results),
    }
    await asyncio.to_thread(save_results, payload, OUTPUT_PATH)
    await asyncio.to_thread(print_evaluation_header, evaluation_block)
    await asyncio.to_thread(print_results_table, strategy_results)
    await asyncio.to_thread(print_fairness_table, payload["fairness"])
    return payload


async def run_cross_city_mode(args: argparse.Namespace) -> dict[str, Any]:
    """Run leave-one-city-out cross-city evaluation and persist cross_city_results.json."""

    train_metadata, train_incidents = await asyncio.to_thread(load_incidents, TRAIN_INCIDENTS_PATH, None)
    _, test_incidents_all = await asyncio.to_thread(load_incidents, TEST_INCIDENTS_PATH, None)
    hospitals = await asyncio.to_thread(load_hospitals)
    ambulances = await asyncio.to_thread(load_ambulances)
    hospitals_by_city = await asyncio.to_thread(_group_by_city, hospitals)
    ambulances_by_city = await asyncio.to_thread(_group_by_city, ambulances)

    held_out_reference_incidents = (
        test_incidents_all[: args.incidents]
        if args.incidents is not None
        else test_incidents_all
    )

    held_out_reference_results = await evaluate_strategies(
        held_out_reference_incidents,
        ambulances_by_city,
        hospitals_by_city,
        strategy_filter=None,
    )
    held_out_ai = held_out_reference_results["ai_dispatch"]
    held_out_nearest = held_out_reference_results["nearest_unit"]
    held_out_improvement = _relative_improvement(
        held_out_nearest["avg_eta_minutes"],
        held_out_ai["avg_eta_minutes"],
    )

    city_results: OrderedDict[str, dict[str, Any]] = OrderedDict()
    ai_improvements: list[float] = []
    ai_avg_etas: list[float] = []
    nearest_avg_etas: list[float] = []
    specialty_match_rates: list[float] = []

    for city in SUPPORTED_CITIES:
        training_cities = [candidate for candidate in SUPPORTED_CITIES if candidate != city]
        filtered_train = [incident for incident in train_incidents if incident["city"] != city]
        filtered_test = [incident for incident in test_incidents_all if incident["city"] == city]
        if args.incidents is not None:
            filtered_test = filtered_test[: args.incidents]

        await _build_cross_city_density_grid(train_metadata, filtered_train, city)
        strategy_results = await evaluate_strategies(
            filtered_test,
            ambulances_by_city,
            hospitals_by_city,
            strategy_filter=None,
        )
        ai_metrics = strategy_results["ai_dispatch"]
        nearest_metrics = strategy_results["nearest_unit"]
        ai_improvement = _relative_improvement(
            nearest_metrics["avg_eta_minutes"],
            ai_metrics["avg_eta_minutes"],
        )

        city_results[city] = {
            "trained_on": training_cities,
            "ai_avg_eta": ai_metrics["avg_eta_minutes"],
            "nearest_avg_eta": nearest_metrics["avg_eta_minutes"],
            "ai_improvement_pct": ai_improvement,
            "specialty_match_rate": ai_metrics["specialty_match_rate"],
            "n_incidents": len(filtered_test),
        }
        ai_improvements.append(ai_improvement)
        ai_avg_etas.append(ai_metrics["avg_eta_minutes"])
        nearest_avg_etas.append(nearest_metrics["avg_eta_minutes"])
        specialty_match_rates.append(ai_metrics["specialty_match_rate"])

    mean_ai_improvement = round(fmean(ai_improvements), 2) if ai_improvements else 0.0
    std_ai_improvement = round(pstdev(ai_improvements), 2) if len(ai_improvements) > 1 else 0.0
    mean_ai_eta = round(fmean(ai_avg_etas), 2) if ai_avg_etas else 0.0
    mean_nearest_eta = round(fmean(nearest_avg_etas), 2) if nearest_avg_etas else 0.0
    mean_specialty_match = round(fmean(specialty_match_rates), 2) if specialty_match_rates else 0.0

    best_city = max(city_results.items(), key=lambda item: item[1]["ai_improvement_pct"])[0] if city_results else ""
    worst_city = min(city_results.items(), key=lambda item: item[1]["ai_improvement_pct"])[0] if city_results else ""

    summary = {
        "mean_ai_improvement_across_cities": mean_ai_improvement,
        "std_ai_improvement_across_cities": std_ai_improvement,
        "worst_city": worst_city,
        "best_city": best_city,
        "generalization_assessment": _generalization_assessment(std_ai_improvement),
        "generalization_gap": {
            "ai_avg_eta_pct": _generalization_gap_pct(held_out_ai["avg_eta_minutes"], mean_ai_eta),
            "nearest_avg_eta_pct": _generalization_gap_pct(held_out_nearest["avg_eta_minutes"], mean_nearest_eta),
            "ai_improvement_pct": _generalization_gap_pct(held_out_improvement, mean_ai_improvement),
            "specialty_match_rate_pct": _generalization_gap_pct(
                held_out_ai["specialty_match_rate"],
                mean_specialty_match,
            ),
        },
    }
    payload = {
        "generated_at": isoformat_utc(),
        "evaluation_type": "cross_city_leave_one_out",
        "training_dataset": TRAIN_INCIDENTS_PATH.name,
        "evaluation_dataset": TEST_INCIDENTS_PATH.name,
        "split_method": "chronological (test = last 200 generated)",
        "cities": city_results,
        "summary": summary,
        "held_out_reference_incidents": len(held_out_reference_incidents),
    }
    await asyncio.to_thread(save_results, payload, CROSS_CITY_OUTPUT_PATH)
    await asyncio.to_thread(print_cross_city_table, city_results, summary)
    return payload


async def main() -> None:
    args = parse_args()
    if args.mode == "cross_city":
        await run_cross_city_mode(args)
        return
    await run_standard_mode(args)


if __name__ == "__main__":
    asyncio.run(main())
