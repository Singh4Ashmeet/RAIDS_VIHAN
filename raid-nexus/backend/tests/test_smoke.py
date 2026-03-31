"""Smoke tests for the RAID Nexus Day 1 backend."""

from __future__ import annotations

import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from config import DB_PATH
from main import app
from ml.synthetic_generator import OUTPUT_PATH, generate_training_data


class RaidNexusSmokeTests(unittest.TestCase):
    """Verify core startup, dispatch, scenario, and ML generation flows."""

    def setUp(self) -> None:
        if DB_PATH.exists():
            DB_PATH.unlink()
        if OUTPUT_PATH.exists():
            OUTPUT_PATH.unlink()

    def test_health_and_seed_counts(self) -> None:
        with TestClient(app) as client:
            health = client.get("/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["status"], "ok")

            ambulances = client.get("/api/ambulances")
            hospitals = client.get("/api/hospitals")
            incidents = client.get("/api/incidents")

            self.assertEqual(ambulances.status_code, 200)
            self.assertEqual(hospitals.status_code, 200)
            self.assertEqual(incidents.status_code, 200)
            self.assertEqual(len(ambulances.json()), 15)
            self.assertEqual(len(hospitals.json()), 10)
            self.assertEqual(len(incidents.json()), 50)

    def test_patient_dispatch_flow(self) -> None:
        with TestClient(app) as client:
            response = client.post(
                "/api/patients",
                json={
                    "name": "Rajesh Kumar",
                    "age": 58,
                    "gender": "male",
                    "mobile": "9876543210",
                    "location_lat": 28.6139,
                    "location_lng": 77.209,
                    "chief_complaint": "severe chest pain and palpitations",
                    "sos_mode": False,
                },
            )
            self.assertEqual(response.status_code, 201)
            body = response.json()
            self.assertTrue(body["notification_sent"])
            self.assertIsNotNone(body["dispatch_plan"]["ambulance_id"])
            self.assertIsNotNone(body["dispatch_plan"]["hospital_id"])
            self.assertIn("rejected_ambulances", body["dispatch_plan"])
            self.assertIn("rejected_hospitals", body["dispatch_plan"])

            patient_id = body["patient"]["id"]
            dispatch_id = body["dispatch_plan"]["id"]
            patient_details = client.get(f"/api/patients/{patient_id}")
            dispatch_details = client.get(f"/api/dispatch/{dispatch_id}")
            analytics = client.get("/api/analytics")

            self.assertEqual(patient_details.status_code, 200)
            self.assertEqual(dispatch_details.status_code, 200)
            self.assertEqual(analytics.status_code, 200)
            self.assertIsNotNone(patient_details.json()["assigned_hospital"])
            self.assertGreaterEqual(analytics.json()["dispatches_today"], 1)
            self.assertGreaterEqual(analytics.json()["hospitals_notified"], 1)

    def test_scenarios_and_generator(self) -> None:
        with TestClient(app) as client:
            traffic = client.post("/api/simulate/scenario", json={"type": "traffic"})
            breakdown = client.post("/api/simulate/scenario", json={"type": "breakdown"})
            overload = client.post("/api/simulate/scenario", json={"type": "overload"})

            self.assertEqual(traffic.status_code, 200)
            self.assertEqual(breakdown.status_code, 200)
            self.assertEqual(overload.status_code, 200)
            self.assertEqual(traffic.json()["traffic"]["multiplier"], 2.5)
            self.assertEqual(breakdown.json()["breakdown"]["ambulance_id"], "AMB-007")
            self.assertEqual(overload.json()["overload"]["hospital_id"], "HOSP-005")

        dataset = generate_training_data()
        self.assertEqual(len(dataset), 10000)
        self.assertTrue(OUTPUT_PATH.exists())
        with OUTPUT_PATH.open("r", encoding="utf-8") as handle:
            line_count = sum(1 for _ in handle)
        self.assertEqual(line_count, 10001)


if __name__ == "__main__":
    unittest.main()
