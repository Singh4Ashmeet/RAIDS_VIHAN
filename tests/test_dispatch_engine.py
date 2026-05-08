"""Service-level tests for the AI dispatch engine facade."""

from __future__ import annotations

from services.dispatch_engine import AmbulanceAllocator, ETAPredictionService, ExplanationGenerator


def test_eta_prediction_returns_positive_float(monkeypatch):
    monkeypatch.setenv("MODEL_PATH", "missing-model.pkl")
    service = ETAPredictionService(model_path="missing-model.pkl")

    eta = service.predict_eta(
        {"location_lat": 28.6139, "location_lng": 77.2090},
        {"lat": 28.6200, "lng": 77.2200, "speed_kmh": 40},
    )

    assert isinstance(eta, float)
    assert eta > 0


def test_ambulance_allocator_returns_closest_available_unit():
    allocator = AmbulanceAllocator()
    incident = {"location_lat": 28.6139, "location_lng": 77.2090}
    fleet = [
        {"id": "far", "status": "available", "lat": 28.8000, "lng": 77.3000},
        {"id": "occupied", "status": "en_route", "lat": 28.6140, "lng": 77.2090},
        {"id": "near", "status": "available", "lat": 28.6140, "lng": 77.2090},
    ]

    selected = allocator.allocate(incident, fleet)

    assert selected["id"] == "near"
    assert selected["dispatch_tier"] == "heuristic"


def test_missing_model_uses_heuristic_fallback():
    service = ETAPredictionService(model_path="missing-model.pkl")

    eta = service.predict_eta(
        {"location_lat": 19.0760, "location_lng": 72.8777},
        {"lat": 19.0800, "lng": 72.8800},
    )

    assert eta > 0


def test_explanation_generator_returns_required_keys():
    explanation = ExplanationGenerator().explain({
        "ambulance": {"id": "AMB-001", "status": "available"},
        "hospital": {"id": "HOSP-001", "beds_available": 3},
        "score_breakdown": {"components": {"eta_score": 0.4, "capacity_score": 0.35, "specialty_score": 0.25}},
        "rejected": [{"id": "AMB-002", "reason": "occupied"}],
    })

    assert set(explanation) == {"selected_ambulance", "selected_hospital", "score_breakdown", "rejected"}
    assert explanation["selected_ambulance"]["id"] == "AMB-001"
    assert explanation["selected_hospital"]["id"] == "HOSP-001"
