"""Traffic congestion helpers using TomTom with an India-focused heuristic fallback."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime
from typing import Final

import httpx

from config import KOLKATA_TZ

logger = logging.getLogger("raid.traffic")

_TOMTOM_FLOW_URL: Final[str] = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
_TOMTOM_TIMEOUT_SECONDS: Final[float] = 4.0
_TOMTOM_CACHE_TTL_SECONDS: Final[float] = 180.0
_HEURISTIC_CACHE_TTL_SECONDS: Final[float] = 60.0
_MAX_MULTIPLIER: Final[float] = 4.0

_CITY_BOOSTS: Final[dict[str, float]] = {
    "mumbai": 0.20,
    "delhi": 0.15,
    "new delhi": 0.15,
    "bengaluru": 0.25,
    "bangalore": 0.25,
    "chennai": 0.10,
    "hyderabad": 0.05,
}

_TomTomCacheKey = tuple[float, float]

_tomtom_cache: dict[_TomTomCacheKey, tuple[float, float]] = {}
_heuristic_cache: dict[str, tuple[float, float]] = {}

_tomtom_locks: dict[_TomTomCacheKey, asyncio.Lock] = {}
_heuristic_locks: dict[str, asyncio.Lock] = {}
_cache_guard = asyncio.Lock()


def _cache_key(lat: float, lng: float) -> _TomTomCacheKey:
    return (round(lat, 2), round(lng, 2))


def _city_cache_key(city: str | None) -> str:
    normalized = str(city or "").strip().lower()
    return normalized or "__default__"


def _cap_multiplier(value: float) -> float:
    return max(1.0, min(float(value), _MAX_MULTIPLIER))


def _get_cached(cache: dict, key: object, ttl_seconds: float) -> float | None:
    cached = cache.get(key)
    if cached is None:
        return None

    value, cached_at = cached
    if (time.monotonic() - cached_at) < ttl_seconds:
        return float(value)

    cache.pop(key, None)
    return None


def _store_cached(cache: dict, key: object, value: float) -> None:
    cache[key] = (float(value), time.monotonic())


async def _lock_for_key(lock_map: dict[object, asyncio.Lock], key: object) -> asyncio.Lock:
    async with _cache_guard:
        lock = lock_map.get(key)
        if lock is None:
            lock = asyncio.Lock()
            lock_map[key] = lock
        return lock


def _heuristic_window_multiplier(now_ist: datetime) -> float:
    minutes = (now_ist.hour * 60) + now_ist.minute

    if 450 <= minutes < 630:
        return 1.9
    if 630 <= minutes < 720:
        return 1.3
    if 720 <= minutes < 840:
        return 1.4
    if 840 <= minutes < 1020:
        return 1.1
    if 1020 <= minutes < 1260:
        return 2.1
    if 1260 <= minutes < 1380:
        return 1.4
    if minutes >= 1380 or minutes < 360:
        return 1.0
    return 1.3


def _heuristic_multiplier(city: str | None) -> float:
    now_ist = datetime.now(KOLKATA_TZ)
    base_multiplier = _heuristic_window_multiplier(now_ist)
    city_boost = _CITY_BOOSTS.get(_city_cache_key(city), 0.0)
    return _cap_multiplier(base_multiplier + city_boost)


async def _fetch_tomtom_multiplier(lat: float, lng: float) -> float | None:
    api_key = os.getenv("TOMTOM_API_KEY")
    if not api_key:
        return None

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(_TOMTOM_TIMEOUT_SECONDS)) as client:
            response = await client.get(
                _TOMTOM_FLOW_URL,
                params={
                    "point": f"{lat},{lng}",
                    "key": api_key,
                    "unit": "KMPH",
                },
            )
            response.raise_for_status()
            payload = response.json()

        flow = payload["flowSegmentData"]
        current_speed = max(float(flow["currentSpeed"]), 1.0)
        free_flow_speed = max(float(flow["freeFlowSpeed"]), 1.0)
        return _cap_multiplier(free_flow_speed / current_speed)
    except (
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.HTTPError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        logger.warning("TomTom traffic lookup failed for %.5f, %.5f: %s", lat, lng, exc)
        return None


async def _get_tomtom_cached_multiplier(lat: float, lng: float) -> float | None:
    api_key = os.getenv("TOMTOM_API_KEY")
    if not api_key:
        return None

    key = _cache_key(lat, lng)
    cached = _get_cached(_tomtom_cache, key, _TOMTOM_CACHE_TTL_SECONDS)
    if cached is not None:
        return cached

    key_lock = await _lock_for_key(_tomtom_locks, key)
    async with key_lock:
        cached = _get_cached(_tomtom_cache, key, _TOMTOM_CACHE_TTL_SECONDS)
        if cached is not None:
            return cached

        multiplier = await _fetch_tomtom_multiplier(lat, lng)
        if multiplier is None:
            return None

        _store_cached(_tomtom_cache, key, multiplier)
        return multiplier


async def _get_cached_heuristic_multiplier(city: str | None) -> float:
    key = _city_cache_key(city)
    cached = _get_cached(_heuristic_cache, key, _HEURISTIC_CACHE_TTL_SECONDS)
    if cached is not None:
        return cached

    key_lock = await _lock_for_key(_heuristic_locks, key)
    async with key_lock:
        cached = _get_cached(_heuristic_cache, key, _HEURISTIC_CACHE_TTL_SECONDS)
        if cached is not None:
            return cached

        multiplier = _heuristic_multiplier(city)
        _store_cached(_heuristic_cache, key, multiplier)
        return multiplier


async def get_traffic_multiplier(lat: float, lng: float, city: str | None = None) -> float:
    """Return a traffic congestion multiplier for a coordinate pair in India."""

    tomtom_multiplier = await _get_tomtom_cached_multiplier(lat, lng)
    if tomtom_multiplier is not None:
        return tomtom_multiplier

    return await _get_cached_heuristic_multiplier(city)
