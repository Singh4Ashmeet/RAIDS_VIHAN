"""Geospatial helpers for routing, ETA, and city matching."""

from __future__ import annotations

import heapq
import math
from typing import Any

from geopy.distance import geodesic

from config import CITY_AMBULANCE_BASE_SPEED_KMH, CITY_BOUNDS, CITY_CENTERS, TRAFFIC_STATE, utc_now


def haversine_km(from_lat: float, from_lng: float, to_lat: float, to_lng: float) -> float:
    """Return the Haversine distance in kilometers between two points."""

    radius_km = 6371.0
    lat1 = math.radians(from_lat)
    lng1 = math.radians(from_lng)
    lat2 = math.radians(to_lat)
    lng2 = math.radians(to_lng)
    delta_lat = lat2 - lat1
    delta_lng = lng2 - lng1

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


def geodesic_km(from_lat: float, from_lng: float, to_lat: float, to_lng: float) -> float:
    """Return geodesic distance in kilometers using geopy."""

    return float(geodesic((from_lat, from_lng), (to_lat, to_lng)).km)


def _cell_for_point(city: str, lat: float, lng: float, grid_size: int = 6) -> tuple[int, int]:
    bounds = CITY_BOUNDS[city]
    row = int(
        max(
            0,
            min(
                grid_size - 1,
                ((lat - bounds["lat_min"]) / max(bounds["lat_max"] - bounds["lat_min"], 1e-9)) * grid_size,
            ),
        )
    )
    col = int(
        max(
            0,
            min(
                grid_size - 1,
                ((lng - bounds["lng_min"]) / max(bounds["lng_max"] - bounds["lng_min"], 1e-9)) * grid_size,
            ),
        )
    )
    return row, col


def _grid_astar_steps(start: tuple[int, int], goal: tuple[int, int], grid_size: int = 6) -> int:
    """Run a lightweight A* search on a synthetic city grid."""

    frontier: list[tuple[int, tuple[int, int]]] = []
    heapq.heappush(frontier, (0, start))
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    cost_so_far: dict[tuple[int, int], int] = {start: 0}

    while frontier:
        _, current = heapq.heappop(frontier)
        if current == goal:
            break
        row, col = current
        for next_node in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
            next_row, next_col = next_node
            if not (0 <= next_row < grid_size and 0 <= next_col < grid_size):
                continue
            new_cost = cost_so_far[current] + 1
            if next_node not in cost_so_far or new_cost < cost_so_far[next_node]:
                cost_so_far[next_node] = new_cost
                heuristic = abs(goal[0] - next_row) + abs(goal[1] - next_col)
                heapq.heappush(frontier, (new_cost + heuristic, next_node))
                came_from[next_node] = current

    return cost_so_far.get(goal, 0)


def grid_adjusted_distance_km(
    from_lat: float,
    from_lng: float,
    to_lat: float,
    to_lng: float,
    city: str,
) -> float:
    """Approximate road-inflated distance using a simple city grid A* search."""

    straight_line = geodesic_km(from_lat, from_lng, to_lat, to_lng)
    start = _cell_for_point(city, from_lat, from_lng)
    goal = _cell_for_point(city, to_lat, to_lng)
    steps = _grid_astar_steps(start, goal)
    bounds = CITY_BOUNDS[city]
    lat_span_km = geodesic_km(bounds["lat_min"], CITY_CENTERS[city][1], bounds["lat_max"], CITY_CENTERS[city][1])
    lng_span_km = geodesic_km(CITY_CENTERS[city][0], bounds["lng_min"], CITY_CENTERS[city][0], bounds["lng_max"])
    cell_km = ((lat_span_km / 6.0) + (lng_span_km / 6.0)) / 2.0
    grid_distance = max(straight_line, (steps * cell_km * 1.05))
    return round(grid_distance, 3)


def get_active_traffic_multiplier(city: str) -> float:
    """Return the active traffic multiplier, clearing expired overrides."""

    state = TRAFFIC_STATE.setdefault(city, {"multiplier": 1.0, "expires_at": None})
    expires_at = state.get("expires_at")
    if expires_at is not None and expires_at <= utc_now():
        state["multiplier"] = 1.0
        state["expires_at"] = None
    return float(state["multiplier"])


def route_travel_minutes(distance_km: float, traffic_multiplier: float, speed_kmh: float | None = None) -> float:
    """Convert distance into travel minutes using city traffic assumptions."""

    effective_speed = max(speed_kmh or CITY_AMBULANCE_BASE_SPEED_KMH, 5.0)
    base_minutes = (distance_km / effective_speed) * 60.0
    return round(base_minutes * traffic_multiplier, 2)


def score_route(
    from_lat: float,
    from_lng: float,
    to_lat: float,
    to_lng: float,
    traffic_multiplier: float,
    city: str,
) -> dict[str, Any]:
    """Score a route segment using Haversine plus a lightweight grid adjustment."""

    straight_line = haversine_km(from_lat, from_lng, to_lat, to_lng)
    distance_km = max(straight_line, grid_adjusted_distance_km(from_lat, from_lng, to_lat, to_lng, city))
    travel_time_minutes = route_travel_minutes(distance_km, traffic_multiplier)
    score = max(0.0, 1.0 - (travel_time_minutes / 45.0))
    if traffic_multiplier < 1.3:
        congestion_level = "low"
    elif traffic_multiplier < 1.8:
        congestion_level = "medium"
    else:
        congestion_level = "high"
    confidence = round(max(0.35, 0.95 - ((traffic_multiplier - 1.0) * 0.2)), 3)
    return {
        "score": round(score, 3),
        "travel_time_minutes": round(travel_time_minutes, 2),
        "distance_km": round(distance_km, 3),
        "congestion_level": congestion_level,
        "confidence": confidence,
    }


def interpolate_towards(
    current_lat: float,
    current_lng: float,
    target_lat: float,
    target_lng: float,
    fraction: float,
) -> tuple[float, float]:
    """Move a point a fraction closer to its target."""

    return (
        current_lat + ((target_lat - current_lat) * fraction),
        current_lng + ((target_lng - current_lng) * fraction),
    )


def nearest_city(lat: float, lng: float) -> str:
    """Resolve a coordinate pair to the nearest configured city center."""

    return min(
        CITY_CENTERS,
        key=lambda city: geodesic_km(lat, lng, CITY_CENTERS[city][0], CITY_CENTERS[city][1]),
    )
