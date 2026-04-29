"""Lightweight anomaly detection for suspicious incident patterns."""

from __future__ import annotations

import asyncio
import logging
import math
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any

try:
    from core.config import settings
except ModuleNotFoundError:
    from backend.core.config import settings

logger = logging.getLogger(__name__)

recent_incidents: deque[dict[str, Any]] = deque(maxlen=200)
anomaly_log: deque[dict[str, Any]] = deque(maxlen=50)
ip_submissions: dict[str, deque[datetime]] = defaultdict(lambda: deque(maxlen=50))
_lock = Lock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat(value: datetime | None = None) -> str:
    return (value or _utc_now()).isoformat()


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius_km * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def record_incident(incident: dict[str, Any]) -> None:
    """Record an incident in the in-memory anomaly monitoring window."""

    with _lock:
        recent_incidents.append(
            {
                "id": incident.get("id"),
                "lat": float(incident["location_lat"]),
                "lng": float(incident["location_lng"]),
                "city": incident.get("city"),
                "type": incident.get("type"),
                "severity": incident.get("severity"),
                "timestamp": _utc_now(),
            }
        )


def check_geographic_cluster(
    new_incident: dict[str, Any],
    radius_km: float = 0.5,
    time_window_minutes: int = 10,
    threshold: int = 3,
) -> dict[str, Any] | None:
    """Detect bursts of same-type incidents in a very small geographic radius."""

    cutoff = _utc_now() - timedelta(minutes=time_window_minutes)
    count = 1
    with _lock:
        for incident in recent_incidents:
            if incident["timestamp"] < cutoff:
                continue
            if incident.get("type") != new_incident.get("type"):
                continue
            distance = _haversine_km(
                float(new_incident["location_lat"]),
                float(new_incident["location_lng"]),
                float(incident["lat"]),
                float(incident["lng"]),
            )
            if distance <= radius_km:
                count += 1

    if count >= threshold:
        incident_type = str(new_incident.get("type") or "unknown")
        return {
            "anomaly_type": "geographic_cluster",
            "severity": "high",
            "description": (
                f"{count} {incident_type} incidents within {radius_km}km in the last "
                f"{time_window_minutes} minutes. Possible duplicate submissions or coordinated false reports."
            ),
            "incident_count": count,
            "location": {
                "lat": float(new_incident["location_lat"]),
                "lng": float(new_incident["location_lng"]),
            },
            "city": new_incident.get("city"),
            "detected_at": _isoformat(),
        }
    return None


def check_severity_spike(
    city: str,
    time_window_minutes: int = 30,
    threshold: int = 5,
) -> dict[str, Any] | None:
    """Detect sudden surges of critical incidents within one city."""

    cutoff = _utc_now() - timedelta(minutes=time_window_minutes)
    with _lock:
        count = sum(
            1
            for incident in recent_incidents
            if incident["timestamp"] >= cutoff
            and incident.get("city") == city
            and incident.get("severity") == "critical"
        )

    if count >= threshold:
        return {
            "anomaly_type": "severity_spike",
            "severity": "medium",
            "description": (
                f"{count} critical incidents in {city} within {time_window_minutes} minutes. "
                "Possible mass casualty event or coordinated false reports."
            ),
            "incident_count": count,
            "city": city,
            "detected_at": _isoformat(),
        }
    return None


def check_rapid_submitter(
    submitter_ip: str,
    time_window_minutes: int = 5,
    threshold: int = 3,
) -> dict[str, Any] | None:
    """Track rapid repeat submissions from one IP."""

    now = _utc_now()
    cutoff = now - timedelta(minutes=time_window_minutes)
    with _lock:
        submissions = ip_submissions[submitter_ip]
        submissions.append(now)
        count = sum(1 for timestamp in submissions if timestamp >= cutoff)

    if count >= threshold:
        prefix = submitter_ip[:12]
        return {
            "anomaly_type": "rapid_submitter",
            "severity": "medium",
            "description": (
                f"IP {prefix}... submitted {count} incidents in {time_window_minutes} minutes. "
                "Rate limiting applied."
            ),
            "ip_prefix": prefix,
            "incident_count": count,
            "detected_at": _isoformat(),
        }
    return None


async def analyze_incident(incident: dict[str, Any], submitter_ip: str) -> list[dict[str, Any]]:
    """Run all anomaly checks and record any detections."""

    if not settings.ENABLE_ANOMALY_DETECTION:
        return []

    results = await asyncio.gather(
        asyncio.to_thread(check_geographic_cluster, incident),
        asyncio.to_thread(check_severity_spike, str(incident.get("city") or "")),
        asyncio.to_thread(check_rapid_submitter, submitter_ip),
    )
    anomalies = [result for result in results if result is not None]
    if not anomalies:
        return []

    with _lock:
        for anomaly in anomalies:
            anomaly_log.append(anomaly)
            logger.warning("ANOMALY: %s - %s", anomaly["anomaly_type"], anomaly["description"])
    return anomalies


def get_recent_anomalies(limit: int = 20) -> list[dict[str, Any]]:
    """Return the most recent anomaly detections, newest first."""

    with _lock:
        return list(reversed(list(anomaly_log)[-limit:]))


def get_total_detected() -> int:
    """Return the retained anomaly count."""

    with _lock:
        return len(anomaly_log)
