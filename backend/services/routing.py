"""Async OSRM routing helpers with traffic-aware ETAs and a Haversine fallback."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import time

import httpx

from core.config import settings
from services.traffic import get_traffic_multiplier

logger = logging.getLogger("raid.routing")

_DEFAULT_OSRM_URL = "http://router.project-osrm.org"
_OSRM_TIMEOUT_SECONDS = 4.0
_ROUTE_GEOMETRY_TIMEOUT_SECONDS = 2.0
_CACHE_TTL_SECONDS = 300.0

_CacheKey = tuple[float, float, float, float]
_travel_time_cache: dict[_CacheKey, tuple[float, float]] = {}
_polyline_cache: dict[_CacheKey, tuple[list[list[float]], float]] = {}
_route_locks: dict[_CacheKey, asyncio.Lock] = {}
_route_locks_guard = asyncio.Lock()


def _cache_key(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> _CacheKey:
    return (
        round(origin_lat, 3),
        round(origin_lng, 3),
        round(dest_lat, 3),
        round(dest_lng, 3),
    )


def _route_url(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> str:
    return f"{_osrm_route_base_url()}/{origin_lng},{origin_lat};{dest_lng},{dest_lat}"


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _external_routing_disabled() -> bool:
    return settings.RAID_DISABLE_EXTERNAL_ROUTING or _env_flag("RAID_DISABLE_EXTERNAL_ROUTING")


def _route_geometry_disabled() -> bool:
    return settings.RAID_DISABLE_ROUTE_GEOMETRY or _env_flag("RAID_DISABLE_ROUTE_GEOMETRY")


def _osrm_route_base_url() -> str:
    base_url = (os.getenv("OSRM_URL") or settings.OSRM_URL or _DEFAULT_OSRM_URL).rstrip("/")
    if base_url.endswith("/route/v1/driving"):
        return base_url
    return f"{base_url}/route/v1/driving"


def _midpoint(origin_value: float, dest_value: float) -> float:
    return (origin_value + dest_value) / 2.0


def _get_cached_result(key: _CacheKey, now: float) -> float | None:
    cached = _travel_time_cache.get(key)
    if cached is None:
        return None

    value, cached_at = cached
    if (now - cached_at) < _CACHE_TTL_SECONDS:
        return value

    _travel_time_cache.pop(key, None)
    return None


def _get_cached_polyline(key: _CacheKey, now: float) -> list[list[float]] | None:
    cached = _polyline_cache.get(key)
    if cached is None:
        return None

    value, cached_at = cached
    if (now - cached_at) < _CACHE_TTL_SECONDS:
        return value

    _polyline_cache.pop(key, None)
    return None


def _store_cached_result(key: _CacheKey, value: float) -> None:
    _travel_time_cache[key] = (value, time.monotonic())


def _store_cached_polyline(key: _CacheKey, value: list[list[float]]) -> None:
    _polyline_cache[key] = (value, time.monotonic())


async def _lock_for_key(key: _CacheKey) -> asyncio.Lock:
    async with _route_locks_guard:
        lock = _route_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _route_locks[key] = lock
        return lock


async def _fetch_route_json(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    *,
    params: dict[str, str],
    timeout_seconds: float = _OSRM_TIMEOUT_SECONDS,
) -> dict:
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds)) as client:
        response = await client.get(
            _route_url(origin_lat, origin_lng, dest_lat, dest_lng),
            params=params,
        )
        response.raise_for_status()
        return response.json()


def _parse_duration_minutes(payload: dict) -> float:
    return float(payload["routes"][0]["duration"]) / 60.0


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


def _haversine_fallback(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Estimate travel time in minutes from straight-line distance."""

    distance_km = _haversine_distance_km(lat1, lng1, lat2, lng2)
    road_distance_km = distance_km * 2.5
    return (road_distance_km / 40.0) * 60.0


async def get_travel_time(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    city: str | None = None,
) -> float:
    """Return travel time in minutes between two coordinates."""

    key = _cache_key(origin_lat, origin_lng, dest_lat, dest_lng)
    base_travel_time_minutes = _get_cached_result(key, time.monotonic())

    if base_travel_time_minutes is None:
        key_lock = await _lock_for_key(key)
        async with key_lock:
            base_travel_time_minutes = _get_cached_result(key, time.monotonic())
            if base_travel_time_minutes is None:
                if _external_routing_disabled():
                    base_travel_time_minutes = _haversine_fallback(
                        origin_lat,
                        origin_lng,
                        dest_lat,
                        dest_lng,
                    )
                else:
                    try:
                        payload = await _fetch_route_json(
                            origin_lat,
                            origin_lng,
                            dest_lat,
                            dest_lng,
                            params={"overview": "false", "annotations": "false"},
                        )
                        base_travel_time_minutes = _parse_duration_minutes(payload)
                    except (
                        httpx.TimeoutException,
                        httpx.ConnectError,
                        httpx.HTTPError,
                        json.JSONDecodeError,
                        KeyError,
                        IndexError,
                        TypeError,
                        ValueError,
                    ) as exc:
                        logger.warning(
                            "OSRM travel-time lookup failed for %s, using fallback: %s",
                            key,
                            exc,
                        )
                        base_travel_time_minutes = _haversine_fallback(
                            origin_lat,
                            origin_lng,
                            dest_lat,
                            dest_lng,
                        )

                _store_cached_result(key, base_travel_time_minutes)

    midpoint_lat = _midpoint(origin_lat, dest_lat)
    midpoint_lng = _midpoint(origin_lng, dest_lng)
    traffic_multiplier = await get_traffic_multiplier(midpoint_lat, midpoint_lng, city=city)
    return round(base_travel_time_minutes * traffic_multiplier, 2)


async def get_route_polyline(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
) -> list[list[float]]:
    """Return a route polyline as [[lat, lng], ...] for map display."""

    if _route_geometry_disabled():
        return []

    key = _cache_key(origin_lat, origin_lng, dest_lat, dest_lng)
    cached = _get_cached_polyline(key, time.monotonic())
    if cached is not None:
        return cached

    try:
        payload = await _fetch_route_json(
            origin_lat,
            origin_lng,
            dest_lat,
            dest_lng,
            params={"overview": "full", "geometries": "geojson", "annotations": "false"},
            timeout_seconds=_ROUTE_GEOMETRY_TIMEOUT_SECONDS,
        )
        coordinates = payload["routes"][0]["geometry"]["coordinates"]
        route = [[float(lat), float(lng)] for lng, lat in coordinates]
        _store_cached_polyline(key, route)
        return route
    except (
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.HTTPError,
        json.JSONDecodeError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
    ) as exc:
        logger.warning("OSRM polyline lookup failed: %s", exc)
        return []
