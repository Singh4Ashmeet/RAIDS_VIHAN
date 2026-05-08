"""API contract tests for health, incident creation, and dispatch explainability."""

from __future__ import annotations


def _data(payload: dict):
    return payload.get("data", payload)


def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "timestamp" in body
    assert "version" in body


def test_create_incident_returns_created_with_dispatch(client):
    response = client.post(
        "/api/incidents",
        json={
            "type": "cardiac",
            "severity": "critical",
            "patient_count": 1,
            "location_lat": 28.6139,
            "location_lng": 77.2090,
            "city": "Delhi",
            "description": "Severe chest pain near Connaught Place",
        },
    )

    assert response.status_code == 201
    body = _data(response.json())
    assert body["incident"]["id"]
    assert body["dispatch_plan"]["id"]
    assert "explanation" in body["dispatch_plan"]


def test_get_dispatch_returns_explanation(client):
    create_response = client.post(
        "/api/incidents",
        json={
            "type": "trauma",
            "severity": "high",
            "patient_count": 1,
            "location_lat": 19.0760,
            "location_lng": 72.8777,
            "city": "Mumbai",
            "description": "Road accident with suspected fracture",
        },
    )
    assert create_response.status_code == 201
    dispatch_id = _data(create_response.json())["dispatch_plan"]["id"]

    response = client.get(f"/api/dispatch/{dispatch_id}")

    assert response.status_code == 200
    dispatch = _data(response.json())
    assert dispatch["id"] == dispatch_id
    assert "explanation" in dispatch
    assert "selected_ambulance" in dispatch["explanation"]
    assert "score_breakdown" in dispatch["explanation"]
