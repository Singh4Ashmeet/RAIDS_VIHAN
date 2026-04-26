"""Predict incident demand hotspots and ambulance pre-positioning targets."""

from __future__ import annotations

import asyncio
import json
import logging
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Final

try:
    from config import DATA_DIR, KOLKATA_TZ
except ModuleNotFoundError:
    from backend.config import DATA_DIR, KOLKATA_TZ

GRID_SIZE: Final[int] = 20
HOTSPOT_THRESHOLD: Final[float] = 0.15
LOOKAHEAD_STEP_MINUTES: Final[int] = 5
AMBULANCE_COVERAGE_RADIUS_KM: Final[float] = 2.0
TRAIN_INCIDENTS_PATH: Final = DATA_DIR / "train_incidents.json"

CITY_BOUNDING_BOXES: Final[dict[str, dict[str, float]]] = {
    "Delhi": {"lat_min": 28.40, "lat_max": 28.88, "lng_min": 76.84, "lng_max": 77.35},
    "Mumbai": {"lat_min": 18.89, "lat_max": 19.27, "lng_min": 72.77, "lng_max": 72.98},
    "Bengaluru": {"lat_min": 12.84, "lat_max": 13.14, "lng_min": 77.46, "lng_max": 77.74},
    "Chennai": {"lat_min": 12.95, "lat_max": 13.22, "lng_min": 80.13, "lng_max": 80.32},
    "Hyderabad": {"lat_min": 17.30, "lat_max": 17.53, "lng_min": 78.30, "lng_max": 78.59},
}

TIME_BUCKET_WEIGHTS: Final[list[tuple[range, float]]] = [
    (range(0, 6), 0.05),
    (range(6, 9), 0.08),
    (range(9, 12), 0.14),
    (range(12, 15), 0.11),
    (range(15, 18), 0.12),
    (range(18, 21), 0.18),
    (range(21, 24), 0.10),
]

CITY_TIME_BOOSTS: Final[dict[str, float]] = {
    "Delhi": 0.05,
    "Mumbai": 0.05,
    "Bengaluru": 0.08,
    "Chennai": 0.0,
    "Hyderabad": 0.0,
}

logger = logging.getLogger(__name__)

DensityGrid = dict[str, list[list[float]]]
_DENSITY_GRID_CACHE: dict[str, DensityGrid] = {}
_CITY_LOOKUP: Final[dict[str, str]] = {city.lower(): city for city in CITY_BOUNDING_BOXES}


def _canonical_city(city: str) -> str:
    normalized = str(city).strip().lower()
    if normalized not in _CITY_LOOKUP:
        raise ValueError(f"Unsupported city '{city}'. Expected one of {', '.join(CITY_BOUNDING_BOXES)}.")
    return _CITY_LOOKUP[normalized]


def _empty_grid() -> list[list[float]]:
    return [[0.0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]


def _resolve_incidents_file(incidents_file: str | None = None) -> str:
    resolved_path = Path(incidents_file).expanduser().resolve() if incidents_file else TRAIN_INCIDENTS_PATH.resolve()
    return str(resolved_path)


def _load_synthetic_incidents(incidents_file: str | None = None) -> list[dict[str, Any]]:
    source_path = Path(_resolve_incidents_file(incidents_file))
    if not source_path.is_file():
        logger.warning("Synthetic incidents file not found at %s; demand grid will be empty.", source_path)
        return []
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return list(payload.get("incidents", []))
    return list(payload)


def _cell_indices(lat: float, lng: float, bounds: dict[str, float]) -> tuple[int, int]:
    lat_step = (bounds["lat_max"] - bounds["lat_min"]) / GRID_SIZE
    lng_step = (bounds["lng_max"] - bounds["lng_min"]) / GRID_SIZE

    row = int((lat - bounds["lat_min"]) / lat_step) if lat_step else 0
    col = int((lng - bounds["lng_min"]) / lng_step) if lng_step else 0
    return max(0, min(row, GRID_SIZE - 1)), max(0, min(col, GRID_SIZE - 1))


def _cell_center(bounds: dict[str, float], row: int, col: int) -> tuple[float, float]:
    lat_step = (bounds["lat_max"] - bounds["lat_min"]) / GRID_SIZE
    lng_step = (bounds["lng_max"] - bounds["lng_min"]) / GRID_SIZE
    center_lat = bounds["lat_min"] + ((row + 0.5) * lat_step)
    center_lng = bounds["lng_min"] + ((col + 0.5) * lng_step)
    return center_lat, center_lng


def _normalize_grid(count_grid: list[list[int]]) -> list[list[float]]:
    max_count = max((count for row in count_grid for count in row), default=0)
    if max_count <= 0:
        return _empty_grid()
    return [[round(cell / max_count, 4) for cell in row] for row in count_grid]


def build_density_grid(
    incidents_file: str | None = None,
    force_rebuild: bool = False,
) -> DensityGrid:
    """Build and cache per-city normalized 20x20 incident density grids."""

    source_path = _resolve_incidents_file(incidents_file)
    if not force_rebuild and source_path in _DENSITY_GRID_CACHE:
        return _DENSITY_GRID_CACHE[source_path]

    logger.info(
        "Building density grid from: %s (training set only - test set held out)",
        source_path,
    )

    count_grids: dict[str, list[list[int]]] = {
        city: [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
        for city in CITY_BOUNDING_BOXES
    }

    for incident in _load_synthetic_incidents(source_path):
        city = str(incident.get("city", "")).strip()
        bounds = CITY_BOUNDING_BOXES.get(city)
        if bounds is None:
            continue

        lat = float(incident.get("lat", 0.0))
        lng = float(incident.get("lng", 0.0))
        row, col = _cell_indices(lat, lng, bounds)
        count_grids[city][row][col] += 1

    density_grid = {
        city: _normalize_grid(grid)
        for city, grid in count_grids.items()
    }
    _DENSITY_GRID_CACHE[source_path] = density_grid
    return density_grid


def get_time_weight(hour: int, city: str) -> float:
    """Return the incident likelihood weight for an IST hour and city."""

    canonical_city = _canonical_city(city)
    normalized_hour = int(hour) % 24
    base_weight = next((weight for hours, weight in TIME_BUCKET_WEIGHTS if normalized_hour in hours), 0.10)
    return round(base_weight + CITY_TIME_BOOSTS.get(canonical_city, 0.0), 4)


def _lookahead_factor(lookahead_minutes: int) -> float:
    return 1.0 + (0.02 * (max(lookahead_minutes, 0) / LOOKAHEAD_STEP_MINUTES))


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
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


def _compute_hotspots(
    density_grid: DensityGrid,
    city: str,
    lookahead_minutes: int,
    current_hour: int,
) -> list[dict[str, Any]]:
    canonical_city = _canonical_city(city)
    city_grid = density_grid.get(canonical_city, _empty_grid())
    bounds = CITY_BOUNDING_BOXES[canonical_city]
    time_weight = get_time_weight(current_hour, canonical_city)
    lookahead_multiplier = _lookahead_factor(lookahead_minutes)

    hotspots: list[dict[str, Any]] = []
    for row_index, row in enumerate(city_grid):
        for col_index, base_score in enumerate(row):
            adjusted_score = min(float(base_score) * lookahead_multiplier, 1.0)
            combined_score = adjusted_score * time_weight
            if combined_score <= HOTSPOT_THRESHOLD:
                continue

            center_lat, center_lng = _cell_center(bounds, row_index, col_index)
            hotspots.append(
                {
                    "lat": round(center_lat, 4),
                    "lng": round(center_lng, 4),
                    "demand_score": round(adjusted_score, 4),
                    "predicted_incidents": int(round(adjusted_score * time_weight * 3)),
                    "cell_row": row_index,
                    "cell_col": col_index,
                }
            )

    hotspots.sort(
        key=lambda hotspot: (
            -float(hotspot["demand_score"]),
            -int(hotspot["predicted_incidents"]),
            int(hotspot["cell_row"]),
            int(hotspot["cell_col"]),
        )
    )
    return hotspots


async def predict_demand(
    city: str,
    lookahead_minutes: int = 30,
    density_grid: DensityGrid | None = None,
) -> list[dict[str, Any]]:
    """Return predicted demand hotspots for the requested city."""

    canonical_city = _canonical_city(city)
    grid = density_grid or await asyncio.to_thread(build_density_grid)
    current_hour = datetime.now(KOLKATA_TZ).hour
    return await asyncio.to_thread(
        _compute_hotspots,
        grid,
        canonical_city,
        lookahead_minutes,
        current_hour,
    )


def _is_hotspot_covered(
    hotspot: dict[str, Any],
    positions: list[tuple[float, float]],
    coverage_radius_km: float = AMBULANCE_COVERAGE_RADIUS_KM,
) -> bool:
    return any(
        _haversine_km(lat, lng, float(hotspot["lat"]), float(hotspot["lng"])) <= coverage_radius_km
        for lat, lng in positions
    )


def _compute_preposition_recommendations(
    city: str,
    ambulances: list[dict[str, Any]],
    city_hotspots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    canonical_city = _canonical_city(city)
    available_ambulances = [
        ambulance
        for ambulance in ambulances
        if ambulance.get("status") == "available" and ambulance.get("city", canonical_city) == canonical_city
    ]
    covered_positions = [
        (float(ambulance["current_lat"]), float(ambulance["current_lng"]))
        for ambulance in available_ambulances
    ]

    recommendations: list[dict[str, Any]] = []
    for ambulance in available_ambulances:
        ambulance_lat = float(ambulance["current_lat"])
        ambulance_lng = float(ambulance["current_lng"])
        candidate_hotspots = sorted(
            city_hotspots,
            key=lambda hotspot: _haversine_km(ambulance_lat, ambulance_lng, float(hotspot["lat"]), float(hotspot["lng"])),
        )

        chosen_hotspot: dict[str, Any] | None = None
        distance_to_hotspot_km = 0.0
        for hotspot in candidate_hotspots:
            if _is_hotspot_covered(hotspot, covered_positions):
                continue
            chosen_hotspot = hotspot
            distance_to_hotspot_km = _haversine_km(
                ambulance_lat,
                ambulance_lng,
                float(hotspot["lat"]),
                float(hotspot["lng"]),
            )
            break

        if chosen_hotspot is None:
            continue

        covered_positions.append((float(chosen_hotspot["lat"]), float(chosen_hotspot["lng"])))
        recommendations.append(
            {
                "ambulance_id": str(ambulance["id"]),
                "move_to_lat": float(chosen_hotspot["lat"]),
                "move_to_lng": float(chosen_hotspot["lng"]),
                "hotspot_demand_score": float(chosen_hotspot["demand_score"]),
                "reason": (
                    f"Reposition toward a predicted {canonical_city} hotspot "
                    f"({distance_to_hotspot_km:.1f} km away, demand {float(chosen_hotspot['demand_score']):.2f}) "
                    "with no other ambulance coverage within 2 km."
                ),
            }
        )

    return recommendations


async def recommend_preposition(
    city: str,
    ambulances: list[dict[str, Any]],
    density_grid: DensityGrid | None = None,
    lookahead_minutes: int = 30,
    hotspots: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Recommend hotspot moves for currently available ambulances."""

    canonical_city = _canonical_city(city)
    city_hotspots = hotspots if hotspots is not None else await predict_demand(
        canonical_city,
        lookahead_minutes=lookahead_minutes,
        density_grid=density_grid,
    )
    if not city_hotspots:
        return []
    return await asyncio.to_thread(
        _compute_preposition_recommendations,
        canonical_city,
        ambulances,
        city_hotspots,
    )
