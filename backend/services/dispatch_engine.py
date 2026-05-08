"""Service-class facade for AI dispatch decisions.

These classes wrap the existing RAID Nexus scoring code so new integrations
can depend on stable service names without replacing the proven dispatch path.
"""

from __future__ import annotations

import logging
import math
import os
import random
from pathlib import Path
from typing import Any

from core.config import settings
from services.dispatch import predict_with_fallback

logger = logging.getLogger(__name__)


def _coordinate(entity: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = entity.get(key)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            return number
    return None


def _haversine_km(lat_a: float, lng_a: float, lat_b: float, lng_b: float) -> float:
    radius_km = 6371.0
    d_lat = math.radians(lat_b - lat_a)
    d_lng = math.radians(lng_b - lng_a)
    a = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(math.radians(lat_a))
        * math.cos(math.radians(lat_b))
        * math.sin(d_lng / 2.0) ** 2
    )
    return radius_km * (2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a)))


def _distance_km(origin: dict[str, Any], target: dict[str, Any]) -> float:
    origin_lat = _coordinate(origin, "location_lat", "current_lat", "lat", "latitude")
    origin_lng = _coordinate(origin, "location_lng", "current_lng", "lng", "longitude")
    target_lat = _coordinate(target, "location_lat", "current_lat", "lat", "latitude")
    target_lng = _coordinate(target, "location_lng", "current_lng", "lng", "longitude")
    if origin_lat is None or origin_lng is None or target_lat is None or target_lng is None:
        return 9999.0
    return _haversine_km(origin_lat, origin_lng, target_lat, target_lng)


class ETAPredictionService:
    """Predict travel ETA with ML when possible and heuristic fallback."""

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path or os.getenv("MODEL_PATH") or settings.MODEL_PATH
        self._model: Any | None = None
        self._model_load_attempted = False

    def predict_eta(self, incident: dict[str, Any], ambulance: dict[str, Any]) -> float:
        """Return ETA in minutes for an ambulance reaching an incident."""

        model = self._load_model()
        if model is not None:
            try:
                features = [[
                    _coordinate(incident, "location_lat", "lat") or 0.0,
                    _coordinate(incident, "location_lng", "lng") or 0.0,
                    _coordinate(ambulance, "current_lat", "lat") or 0.0,
                    _coordinate(ambulance, "current_lng", "lng") or 0.0,
                    float(ambulance.get("speed_kmh") or 40.0),
                ]]
                prediction = model.predict(features)[0]
                return round(max(0.1, float(prediction)), 2)
            except Exception as exc:
                logger.warning("ETA ML model failed, using heuristic ETA: %s", exc)

        distance = _distance_km(ambulance, incident)
        speed = max(float(ambulance.get("speed_kmh") or 40.0), 1.0)
        return round((distance / speed) * 60.0, 2)

    def _load_model(self) -> Any | None:
        if self._model_load_attempted:
            return self._model
        self._model_load_attempted = True
        if not self.model_path:
            return None
        path = Path(self.model_path)
        if not path.is_file():
            logger.warning("MODEL_PATH does not exist; using heuristic ETA: %s", path)
            return None
        try:
            import joblib

            self._model = joblib.load(path)
        except Exception as exc:
            logger.warning("Unable to load MODEL_PATH %s: %s", path, exc)
            self._model = None
        return self._model


class HospitalScoringService:
    """Score candidate hospitals using distance, availability, and specialty."""

    def score_hospitals(self, incident: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        scored: list[dict[str, Any]] = []
        incident_type = str(incident.get("type") or "").lower()
        for hospital in candidates:
            distance = _distance_km(incident, hospital)
            beds = hospital.get("beds_available", hospital.get("icu_beds_available", 0))
            try:
                bed_count = max(float(beds or 0.0), 0.0)
            except (TypeError, ValueError):
                bed_count = 0.0
            specialties = {str(item).lower() for item in hospital.get("specialties", [])}
            specialty = 1.0 if incident_type and incident_type in specialties else 0.25
            if incident_type in {"cardiac", "heart"} and "cardiology" in specialties:
                specialty = 1.0
            availability = min(1.0, bed_count / 10.0)
            distance_score = 1.0 / max(distance, 0.1)
            if hospital.get("diversion_status"):
                availability = 0.0
            score = (distance_score * 0.4) + (availability * 0.35) + (specialty * 0.25)
            scored.append({
                **hospital,
                "ai_score": round(score, 4),
                "score_breakdown": {
                    "distance": round(distance_score, 4),
                    "availability": round(availability, 4),
                    "specialty": round(specialty, 4),
                },
            })
        return sorted(scored, key=lambda item: item["ai_score"], reverse=True)


class AmbulanceAllocator:
    """Allocate an ambulance with ML, heuristic, then random-valid fallback."""

    def __init__(self, eta_service: ETAPredictionService | None = None) -> None:
        self.eta_service = eta_service or ETAPredictionService()

    def allocate(self, incident: dict[str, Any], fleet: list[dict[str, Any]]) -> dict[str, Any]:
        available = [ambulance for ambulance in fleet if ambulance.get("status") == "available"]
        try:
            ambulance = min(available, key=lambda item: self.eta_service.predict_eta(incident, item))
            return {**ambulance, "dispatch_tier": "heuristic"}
        except Exception as exc:
            logger.warning("Heuristic ambulance allocation failed: %s", exc)

        try:
            ambulance, tier = predict_with_fallback(available, incident, [])
            return {**ambulance, "dispatch_tier": tier}
        except Exception as exc:
            logger.warning("Legacy ambulance allocation fallback reached: %s", exc)

        if available:
            return {**random.choice(available), "dispatch_tier": "random"}
        raise RuntimeError("No valid ambulance assignment is available.")


class ExplanationGenerator:
    """Generate structured rule-based explanations for dispatch responses."""

    def explain(self, decision: dict[str, Any]) -> dict[str, Any]:
        ambulance = decision.get("ambulance") or {}
        hospital = decision.get("hospital") or {}
        score_breakdown = decision.get("score_breakdown") or {}
        rejected = decision.get("rejected") or []
        beds = hospital.get("beds_available", hospital.get("icu_beds_available"))
        hospital_reason = "nearest suitable receiving hospital"
        if beds is not None:
            hospital_reason = f"nearest suitable receiving hospital, {beds} beds"
        return {
            "selected_ambulance": {
                "id": ambulance.get("id") or decision.get("ambulance_id"),
                "reason": f"closest, status={ambulance.get('status', 'available')}",
            },
            "selected_hospital": {
                "id": hospital.get("id") or decision.get("hospital_id"),
                "reason": hospital_reason,
            },
            "score_breakdown": self._compact_score_breakdown(score_breakdown),
            "rejected": rejected,
        }

    @staticmethod
    def _compact_score_breakdown(score_breakdown: dict[str, Any]) -> dict[str, float]:
        components = score_breakdown.get("components") if isinstance(score_breakdown, dict) else None
        if isinstance(components, dict):
            return {
                "distance": round(float(components.get("eta_score", 0.0)), 4),
                "availability": round(float(components.get("capacity_score", 0.0)), 4),
                "specialty": round(float(components.get("specialty_score", 0.0)), 4),
            }
        return {
            "distance": 0.4,
            "availability": 0.35,
            "specialty": 0.25,
        }


class BenchmarkSimulator:
    """Run lightweight benchmark simulations without blocking app startup."""

    def run(self, n_scenarios: int) -> dict[str, Any]:
        scenario_count = max(int(n_scenarios), 0)
        return {
            "scenario_count": scenario_count,
            "avg_eta": 0.0,
            "accuracy": 0.0,
            "note": "Use backend/scripts/benchmark.py for full benchmark execution.",
        }
