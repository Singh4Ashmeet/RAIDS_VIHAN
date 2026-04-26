"""Standalone integration checks for the RAID Nexus backend."""

from __future__ import annotations

import os
from contextlib import AbstractContextManager

import httpx
from fastapi.testclient import TestClient

BASE_URL = os.getenv("RAID_NEXUS_BASE_URL")


def get_client() -> AbstractContextManager[httpx.Client | TestClient]:
    """Return either an external HTTP client or an in-process test client."""

    if BASE_URL:
        return httpx.Client(base_url=BASE_URL, timeout=10)

    from main import create_app

    return TestClient(create_app())


def unwrap_payload(payload):
    """Handle both raw and enveloped API responses."""

    if isinstance(payload, dict) and "status" in payload and "data" in payload:
        return payload["data"]
    return payload


def test_all() -> None:
    with get_client() as c:
        # 1. Frontend shell
        r = c.get("/")
        assert r.status_code == 200, "root failed"
        assert 'id="root"' in r.text, "frontend shell missing"
        print("PASS root frontend")

        # 2. Health
        r = c.get("/health")
        assert r.status_code == 200, "health failed"
        print("PASS health")

        # 3. Ambulances seeded
        r = c.get("/api/ambulances")
        assert r.status_code == 200
        ambs = unwrap_payload(r.json())
        assert len(ambs) >= 5, f"expected 5+ ambulances, got {len(ambs)}"
        print(f"PASS ambulances ({len(ambs)} seeded)")

        # 4. Hospitals seeded
        r = c.get("/api/hospitals")
        assert r.status_code == 200
        hosps = unwrap_payload(r.json())
        assert len(hosps) >= 5, f"expected 5+ hospitals, got {len(hosps)}"
        print(f"PASS hospitals ({len(hosps)} seeded)")

        # 5. Patient SOS -> dispatch
        r = c.post(
            "/api/patients",
            json={
                "name": "Integration Test",
                "age": 68,
                "gender": "male",
                "mobile": "9999000001",
                "location_lat": 28.6139,
                "location_lng": 77.2090,
                "chief_complaint": "severe chest pain radiating to arm",
                "sos_mode": True,
            },
        )
        assert r.status_code in (201, 207), f"patient POST failed: {r.text}"
        data = unwrap_payload(r.json())
        plan = data["dispatch_plan"]
        assert plan["ambulance_id"], "no ambulance selected"
        assert plan["hospital_id"], "no hospital selected"
        assert plan["eta_minutes"] > 0, "eta is zero"
        assert plan["explanation_text"], "explanation is empty"
        assert len(plan["rejected_hospitals"]) >= 0
        print(
            f"PASS patient SOS -> dispatch (amb={plan['ambulance_id']} "
            f"hosp={plan['hospital_id']} eta={plan['eta_minutes']:.1f}min)"
        )
        print(f"     explanation: {plan['explanation_text'][:80]}...")

        # 6. Scenario - cardiac
        r = c.post("/api/simulate/scenario", json={"type": "cardiac"})
        assert r.status_code in (200, 207), f"scenario failed: {r.text}"
        print(f"PASS scenario cardiac (status={r.status_code})")

        # 7. Scenario - overload
        r = c.post("/api/simulate/scenario", json={"type": "overload"})
        assert r.status_code == 200
        print("PASS scenario overload")

        # 8. Analytics
        r = c.get("/api/analytics")
        assert r.status_code == 200
        analytics = unwrap_payload(r.json())
        assert "avg_eta_ai" in analytics
        print(
            "PASS analytics "
            f"(ai_eta={analytics['avg_eta_ai']} baseline={analytics['avg_eta_baseline']})"
        )

        # 9. Age-aware check
        r1 = c.post(
            "/api/patients",
            json={
                "name": "Senior Patient",
                "age": 72,
                "gender": "female",
                "mobile": "9999000002",
                "location_lat": 28.6139,
                "location_lng": 77.2090,
                "chief_complaint": "chest pain and breathlessness",
                "sos_mode": True,
            },
        )
        r2 = c.post(
            "/api/patients",
            json={
                "name": "Young Patient",
                "age": 24,
                "gender": "male",
                "mobile": "9999000003",
                "location_lat": 28.6139,
                "location_lng": 77.2090,
                "chief_complaint": "chest pain and breathlessness",
                "sos_mode": True,
            },
        )
        p1 = unwrap_payload(r1.json())["dispatch_plan"]
        p2 = unwrap_payload(r2.json())["dispatch_plan"]
        print(f"PASS age-aware routing - senior hosp={p1['hospital_id']} young hosp={p2['hospital_id']}")

        print("\nAll integration tests passed.")


if __name__ == "__main__":
    test_all()
