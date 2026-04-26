"""Fairness measurement utilities for benchmark dispatch results."""

from __future__ import annotations

import asyncio
import math
from statistics import fmean
from typing import Any

CITY_ZONES: dict[str, dict[str, Any]] = {
    "Delhi": {
        "center": (28.6139, 77.2090),
        "bbox": (28.40, 28.88, 76.84, 77.35),
    },
    "Mumbai": {
        "center": (19.0760, 72.8777),
        "bbox": (18.89, 19.27, 72.77, 72.98),
    },
    "Bengaluru": {
        "center": (12.9716, 77.5946),
        "bbox": (12.84, 13.14, 77.46, 77.74),
    },
    "Chennai": {
        "center": (13.0827, 80.2707),
        "bbox": (12.95, 13.22, 80.13, 80.32),
    },
    "Hyderabad": {
        "center": (17.3850, 78.4867),
        "bbox": (17.30, 17.53, 78.30, 78.59),
    },
}

ZONE_ORDER: tuple[str, ...] = ("central", "mid", "peripheral")


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
    return radius_km * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def classify_zone(lat: float, lng: float, city: str) -> str:
    """Classify an incident location as central, mid, or peripheral."""

    city_meta = CITY_ZONES.get(str(city))
    if city_meta is None:
        return "unknown"

    center_lat, center_lng = city_meta["center"]
    distance_km = _haversine_distance_km(float(lat), float(lng), center_lat, center_lng)
    if distance_km < 5.0:
        return "central"
    if distance_km < 12.0:
        return "mid"
    return "peripheral"


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
    value = ordered[lower_index] + ((ordered[upper_index] - ordered[lower_index]) * fraction)
    return round(value, 2)


def _rate(count: int, total: int) -> float:
    return round((count / total) * 100.0, 2) if total else 0.0


def _zone_metrics(items: list[dict[str, Any]]) -> dict[str, float | int]:
    count = len(items)
    eta_values = [float(item.get("eta_minutes", 0.0)) for item in items]
    total_values = [float(item.get("total_time_minutes", 0.0)) for item in items]
    specialty_matches = sum(1 for item in items if bool(item.get("specialty_matched")))
    overloads = sum(1 for item in items if bool(item.get("hospital_at_capacity")))
    delays = sum(1 for item in items if bool(item.get("was_delayed")))

    return {
        "count": count,
        "avg_eta": round(fmean(eta_values), 2) if eta_values else 0.0,
        "avg_total_time": round(fmean(total_values), 2) if total_values else 0.0,
        "specialty_match_rate": _rate(specialty_matches, count),
        "overload_rate": _rate(overloads, count),
        "delayed_rate": _rate(delays, count),
        "p90_eta": _percentile(eta_values, 90),
    }


def _equity_label(equity_score: float) -> str:
    if equity_score > 80.0:
        return "equitable"
    if equity_score >= 60.0:
        return "moderate disparity"
    return "significant disparity"


def _compute_fairness_metrics_sync(results: list[dict[str, Any]], strategy_name: str) -> dict[str, Any]:
    """Compute zone-level fairness metrics for one benchmark strategy."""

    grouped: dict[str, list[dict[str, Any]]] = {zone: [] for zone in ZONE_ORDER}
    for incident in results:
        lat = incident.get("lat")
        lng = incident.get("lng")
        city = incident.get("city", "")
        if lat is None or lng is None:
            continue

        zone = classify_zone(float(lat), float(lng), str(city))
        if zone in grouped:
            grouped[zone].append(incident)

    zones = {zone: _zone_metrics(grouped[zone]) for zone in ZONE_ORDER}
    non_empty_avg_etas = [
        float(payload["avg_eta"])
        for payload in zones.values()
        if int(payload["count"]) > 0 and float(payload["avg_eta"]) > 0.0
    ]

    if non_empty_avg_etas:
        min_avg_eta = min(non_empty_avg_etas)
        max_avg_eta = max(non_empty_avg_etas)
        disparity_ratio = max_avg_eta / min_avg_eta if min_avg_eta else 1.0
    else:
        disparity_ratio = 1.0

    equity_score = max(0.0, min(100.0, 100.0 - ((disparity_ratio - 1.0) * 50.0)))
    central_eta = float(zones["central"]["avg_eta"])
    peripheral_eta = float(zones["peripheral"]["avg_eta"])
    peripheral_penalty_pct = (
        ((peripheral_eta - central_eta) / central_eta) * 100.0
        if central_eta > 0.0 and peripheral_eta > 0.0
        else 0.0
    )
    fairness_win = (peripheral_eta / central_eta) < 1.3 if central_eta > 0.0 and peripheral_eta > 0.0 else False

    return {
        "strategy": strategy_name,
        "zones": zones,
        "disparity_ratio": round(disparity_ratio, 3),
        "equity_score": round(equity_score, 1),
        "equity_label": _equity_label(equity_score),
        "fairness_win": fairness_win,
        "peripheral_penalty_pct": round(peripheral_penalty_pct, 1),
    }


async def compute_fairness_metrics(results: list[dict[str, Any]], strategy_name: str) -> dict[str, Any]:
    """Compute fairness metrics in a worker thread to avoid blocking async callers."""

    return await asyncio.to_thread(_compute_fairness_metrics_sync, results, strategy_name)


def compare_fairness(ai_metrics: dict[str, Any], baseline_metrics: dict[str, Any]) -> dict[str, Any]:
    """Compare AI dispatch fairness against the nearest-unit baseline."""

    ai_ratio = float(ai_metrics.get("disparity_ratio", 1.0))
    baseline_ratio = float(baseline_metrics.get("disparity_ratio", 1.0))
    disparity_improvement = baseline_ratio - ai_ratio
    zones_where_ai_wins: list[str] = []
    zones_where_ai_loses: list[str] = []

    for zone in ZONE_ORDER:
        ai_eta = float(ai_metrics.get("zones", {}).get(zone, {}).get("avg_eta", 0.0))
        baseline_eta = float(baseline_metrics.get("zones", {}).get(zone, {}).get("avg_eta", 0.0))
        if ai_eta <= 0.0 or baseline_eta <= 0.0:
            continue
        if ai_eta < baseline_eta:
            zones_where_ai_wins.append(zone)
        elif ai_eta > baseline_eta:
            zones_where_ai_loses.append(zone)

    ai_more_equitable = ai_ratio < baseline_ratio
    equity_score_improvement = float(ai_metrics.get("equity_score", 0.0)) - float(
        baseline_metrics.get("equity_score", 0.0)
    )
    lower_disparity_pct = (
        (disparity_improvement / baseline_ratio) * 100.0
        if baseline_ratio > 0.0
        else 0.0
    )
    if ai_more_equitable:
        summary = (
            f"AI dispatch is more equitable than nearest-unit baseline, with "
            f"{abs(lower_disparity_pct):.0f}% lower disparity ratio and better ETAs in "
            f"{', '.join(zones_where_ai_wins) or 'no individual zones'}."
        )
    else:
        summary = (
            f"AI dispatch is not more equitable than nearest-unit baseline, with "
            f"{abs(lower_disparity_pct):.0f}% higher disparity ratio and slower ETAs in "
            f"{', '.join(zones_where_ai_loses) or 'no individual zones'}."
        )

    return {
        "ai_more_equitable": ai_more_equitable,
        "disparity_improvement": round(disparity_improvement, 3),
        "zones_where_ai_wins": zones_where_ai_wins,
        "zones_where_ai_loses": zones_where_ai_loses,
        "equity_score_improvement": round(equity_score_improvement, 1),
        "summary": summary,
    }
