"""Focused API envelope tests for RAID Nexus."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi.testclient import TestClient

from api import system as system_api
from api import websocket as websocket_api
from core.config import isoformat_utc
from core.response import APIResponse, ApiResponse, error, fallback, success, unwrap_envelope
from core.security import limiter
from main import create_app
from repositories.dispatch_repo import DispatchRepository


def assert_envelope(payload: dict[str, Any], status: str) -> dict[str, Any]:
    assert set(payload) == {"status", "message", "data"}
    assert payload["status"] == status
    assert isinstance(payload["message"], str)
    return payload["data"]


def login(client: TestClient) -> str:
    limiter._storage.reset()
    response = client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "admin123"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200
    token_payload = assert_envelope(response.json(), "success")
    assert token_payload["token_type"] == "bearer"
    return token_payload["access_token"]


def test_response_helpers_use_canonical_shape() -> None:
    assert APIResponse is ApiResponse
    assert success({"ok": True}) == {
        "status": "success",
        "message": "OK",
        "data": {"ok": True},
    }
    assert fallback({"mode": "manual"}, "Fallback dispatch") == {
        "status": "fallback",
        "message": "Fallback dispatch",
        "data": {"mode": "manual"},
    }
    assert error("Failed", code=503) == {
        "status": "error",
        "message": "Failed",
        "data": None,
    }
    assert unwrap_envelope(success({"id": 1})) == ({"id": 1}, "success", "OK")


def test_auth_login_success_is_enveloped(fresh_test_database) -> None:
    with TestClient(create_app()) as client:
        limiter._storage.reset()
        response = client.post(
            "/api/auth/login",
            data={"username": "admin", "password": "admin123"},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )

    assert response.status_code == 200
    data = assert_envelope(response.json(), "success")
    assert data["access_token"]
    assert data["role"] == "admin"


def test_core_list_and_analytics_endpoints_are_enveloped(fresh_test_database) -> None:
    with TestClient(create_app()) as client:
        ambulances = client.get("/api/ambulances")
        hospitals = client.get("/api/hospitals")
        incidents = client.get("/api/incidents")
        analytics = client.get("/api/analytics")

    assert ambulances.status_code == 200
    assert hospitals.status_code == 200
    assert incidents.status_code == 200
    assert analytics.status_code == 200
    assert len(assert_envelope(ambulances.json(), "success")) == 15
    assert len(assert_envelope(hospitals.json(), "success")) == 10
    assert len(assert_envelope(incidents.json(), "success")) == 50
    assert "dispatches_today" in assert_envelope(analytics.json(), "success")


def test_analytics_uses_persisted_dispatch_records(fresh_test_database) -> None:
    async def seed_dispatches() -> None:
        repo = DispatchRepository()
        base_record = {
            "incident_id": "INC-ANALYTICS",
            "patient_id": None,
            "ambulance_id": "AMB-001",
            "hospital_id": "HOSP-001",
            "ambulance_score": 0.8,
            "hospital_score": 0.7,
            "route_score": 0.6,
            "final_score": 0.9,
            "distance_km": 5.0,
            "rejected_ambulances": [],
            "rejected_hospitals": [],
            "explanation_text": "Analytics test dispatch",
            "fallback_hospital_id": None,
            "created_at": isoformat_utc(),
            "baseline_eta_minutes": None,
            "overload_avoided": False,
            "override_id": None,
        }
        await repo.create(
            {
                **base_record,
                "id": "DISP-ML",
                "eta_minutes": 10.0,
                "status": "active",
                "dispatch_tier": "ml",
            }
        )
        await repo.create(
            {
                **base_record,
                "id": "DISP-FALLBACK",
                "eta_minutes": 20.0,
                "status": "fallback",
                "dispatch_tier": "heuristic",
            }
        )

    with TestClient(create_app()) as client:
        asyncio.run(seed_dispatches())
        response = client.get("/api/analytics")

    assert response.status_code == 200
    data = assert_envelope(response.json(), "success")
    assert data["avg_eta_ai"] == 10.0
    assert data["avg_eta_baseline"] == 21.0
    assert data["dispatches_today"] == 2
    assert data["overloads_prevented"] == 1


def test_scenario_trigger_success_is_enveloped(fresh_test_database) -> None:
    with TestClient(create_app()) as client:
        limiter._storage.reset()
        response = client.post("/api/simulate/scenario", json={"type": "traffic"})

    assert response.status_code == 200
    data = assert_envelope(response.json(), "success")
    assert data["scenario"] == "traffic"
    assert data["traffic"]["multiplier"] == 2.5


def test_cardiac_scenario_includes_structured_explanation(monkeypatch, fresh_test_database) -> None:
    dispatch_plan = {
        "id": "DISP-TEST",
        "incident_id": "INC-CARDIAC-TEST",
        "patient_id": None,
        "ambulance_id": "AMB-001",
        "hospital_id": "HOSP-001",
        "ambulance_score": 0.8,
        "hospital_score": 0.7,
        "route_score": 0.6,
        "final_score": 0.9123,
        "eta_minutes": 8.5,
        "distance_km": 5.6,
        "rejected_ambulances": [],
        "rejected_hospitals": [],
        "explanation_text": "Selected cardiac dispatch",
        "fallback_hospital_id": None,
        "created_at": isoformat_utc(),
        "status": "active",
        "baseline_eta_minutes": 12.0,
        "overload_avoided": False,
        "override_id": None,
        "city": "Delhi",
        "dispatch_tier": "heuristic",
        "score_breakdown": {
            "total_score": 0.9123,
            "components": {
                "eta_score": 0.8123,
                "capacity_score": 0.7123,
                "specialty_score": 1.0,
            },
        },
    }

    async def fake_create_incident(_incident):
        return None

    async def fake_full_dispatch_pipeline(_incident_id, **_kwargs):
        return success(dispatch_plan)

    async def fake_broadcast_event(_event):
        return None

    class FakeHospitalRepository:
        async def get_all(self, _city=None):
            return [
                {"id": "HOSP-001", "name": "Selected Hospital", "specialties": ["cardiology"]},
                {
                    "id": "HOSP-002",
                    "name": "Busy Hospital",
                    "occupancy_pct": 97,
                    "specialties": ["cardiology"],
                    "diversion_status": False,
                },
            ]

    monkeypatch.setattr(system_api, "create_incident", fake_create_incident)
    monkeypatch.setattr(system_api, "full_dispatch_pipeline", fake_full_dispatch_pipeline)
    monkeypatch.setattr(system_api, "HospitalRepository", FakeHospitalRepository)
    monkeypatch.setattr(websocket_api, "broadcast_event", fake_broadcast_event)

    with TestClient(create_app()) as client:
        limiter._storage.reset()
        response = client.post("/api/simulate/scenario", json={"type": "cardiac"})

    assert response.status_code == 200
    data = assert_envelope(response.json(), "success")
    assert data["dispatch_plan"]["dispatch_tier"] == "heuristic"
    assert data["explanation"]["selected_reason"] == "Nearest ALS unit with highest composite score"
    assert data["explanation"]["score_breakdown"]["final_score"] == 0.912
    assert data["explanation"]["rejected_hospitals"][0]["id"] == "HOSP-002"


def test_auth_failure_is_enveloped(fresh_test_database) -> None:
    with TestClient(create_app()) as client:
        limiter._storage.reset()
        response = client.post(
            "/api/auth/login",
            data={"username": "admin", "password": "wrong-password"},
            headers={"content-type": "application/x-www-form-urlencoded"},
        )

    assert response.status_code == 401
    assert assert_envelope(response.json(), "error") is None


def test_validation_failure_is_enveloped(fresh_test_database) -> None:
    with TestClient(create_app()) as client:
        limiter._storage.reset()
        response = client.post("/api/simulate/scenario", json={"type": "not-a-scenario"})

    assert response.status_code == 422
    assert assert_envelope(response.json(), "error") is None


def test_authenticated_admin_endpoint_is_enveloped(fresh_test_database) -> None:
    with TestClient(create_app()) as client:
        token = login(client)
        response = client.get(
            "/api/overrides/stats",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    data = assert_envelope(response.json(), "success")
    assert "total_overrides" in data
