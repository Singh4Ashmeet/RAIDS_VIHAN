"""Geospatial helpers for traffic, routing, and city matching."""

from __future__ import annotations

import asyncio
from typing import Any

from core.config import CITY_AMBULANCE_BASE_SPEED_KMH, CITY_CENTERS, TRAFFIC_STATE, utc_now
from services.routing import get_travel_time


def get_active_traffic_multiplier(city: str) -> float:
    """Return the active traffic multiplier, clearing expired overrides."""

    state = TRAFFIC_STATE.setdefault(city, {"multiplier": 1.0, "expires_at": None})
    expires_at = state.get("expires_at")
    if expires_at is not None and expires_at <= utc_now():
        state["multiplier"] = 1.0
        state["expires_at"] = None
    return float(state["multiplier"])


async def score_route(
    from_lat: float,
    from_lng: float,
    to_lat: float,
    to_lng: float,
    traffic_multiplier: float,
    city: str,
) -> dict[str, Any]:
    """Score a route segment using OSRM travel time plus traffic adjustments."""

    base_travel_time_minutes = await get_travel_time(from_lat, from_lng, to_lat, to_lng, city=city)
    travel_time_minutes = round(base_travel_time_minutes * traffic_multiplier, 2)
    distance_km = round((base_travel_time_minutes / 60.0) * CITY_AMBULANCE_BASE_SPEED_KMH, 3)
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
        "distance_km": distance_km,
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


async def nearest_city(lat: float, lng: float) -> str:
    """Resolve a coordinate pair to the nearest configured city center by route time."""

    city_names = list(CITY_CENTERS)
    travel_times = await asyncio.gather(
        *[
            get_travel_time(lat, lng, CITY_CENTERS[city][0], CITY_CENTERS[city][1])
            for city in city_names
        ]
    )
    return min(zip(city_names, travel_times, strict=False), key=lambda item: item[1])[0]
