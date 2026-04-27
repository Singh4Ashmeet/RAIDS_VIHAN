"""Incident generation helpers for simulations and manual scenarios."""

from __future__ import annotations

import random
from uuid import uuid4

from core.config import CITY_BOUNDS, isoformat_utc
from repositories.database import insert_record

INCIDENT_DESCRIPTIONS: dict[str, tuple[str, ...]] = {
    "cardiac": (
        "severe chest pain and palpitations",
        "suspected heart attack with sweating",
        "cardiac distress and collapse",
    ),
    "trauma": (
        "construction injury with active bleeding",
        "fall with possible fracture",
        "roadside trauma with severe pain",
    ),
    "respiratory": (
        "acute breathing difficulty and wheezing",
        "oxygen drop and respiratory distress",
        "asthma attack with low response",
    ),
    "accident": (
        "multi-vehicle collision with trapped rider",
        "high-speed accident near junction",
        "two-wheeler crash with head injury",
    ),
    "other": (
        "high fever with sudden weakness",
        "loss of consciousness of unknown cause",
        "medical emergency requiring transport",
    ),
}


def build_incident_payload(
    *,
    city: str,
    incident_type: str,
    severity: str,
    patient_count: int,
    location_lat: float,
    location_lng: float,
    description: str,
    patient_id: str | None = None,
    triage_confidence: float | None = None,
    requires_human_review: bool = False,
    review_reason: str | None = None,
    triage_version: str | None = None,
    language_detected: str | None = None,
    language_name: str | None = None,
    original_complaint: str | None = None,
    translated_complaint: str | None = None,
    translation_model: str | None = None,
    has_anomaly: bool = False,
    anomaly_flags: list[str] | None = None,
) -> dict[str, object]:
    """Create a normalized incident payload ready for persistence."""

    return {
        "id": str(uuid4()),
        "type": incident_type,
        "severity": severity,
        "patient_count": patient_count,
        "location_lat": round(location_lat, 6),
        "location_lng": round(location_lng, 6),
        "city": city,
        "description": description,
        "status": "open",
        "created_at": isoformat_utc(),
        "patient_id": patient_id,
        "triage_confidence": triage_confidence,
        "requires_human_review": requires_human_review,
        "review_reason": review_reason,
        "triage_version": triage_version,
        "language_detected": language_detected,
        "language_name": language_name,
        "original_complaint": original_complaint,
        "translated_complaint": translated_complaint,
        "translation_model": translation_model,
        "has_anomaly": has_anomaly,
        "anomaly_flags": list(anomaly_flags or []),
    }


async def create_incident(payload: dict[str, object]) -> dict[str, object]:
    """Persist a new incident payload."""

    await insert_record("incidents", payload)
    try:
        from api.websocket import broadcast_event

        await broadcast_event(
            {
                "type": "incident_created",
                "incident": payload,
                "requires_human_review": bool(payload.get("requires_human_review", False)),
                "review_reason": payload.get("review_reason"),
            }
        )
    except Exception:
        pass
    return payload


async def generate_random_incident(random_source: random.Random) -> dict[str, object]:
    """Generate and persist a random open incident inside configured city bounds."""

    city = random_source.choice(list(CITY_BOUNDS))
    bounds = CITY_BOUNDS[city]
    incident_type = random_source.choices(
        population=["cardiac", "accident", "trauma", "respiratory", "other"],
        weights=[30, 25, 20, 15, 10],
        k=1,
    )[0]
    severity = random_source.choices(
        population=["critical", "high", "medium", "low"],
        weights=[20, 30, 35, 15],
        k=1,
    )[0]
    description = random_source.choice(INCIDENT_DESCRIPTIONS[incident_type])
    payload = build_incident_payload(
        city=city,
        incident_type=incident_type,
        severity=severity,
        patient_count=random_source.randint(1, 4),
        location_lat=random_source.uniform(bounds["lat_min"], bounds["lat_max"]),
        location_lng=random_source.uniform(bounds["lng_min"], bounds["lng_max"]),
        description=description,
    )
    await create_incident(payload)
    return payload
