"""Smoke tests for the RAID Nexus Day 1 backend."""

from __future__ import annotations

import os
import tempfile
import unittest
import warnings
from pathlib import Path

from fastapi.testclient import TestClient

from config import get_db_path
from main import create_app
from ml.synthetic_generator import generate_training_data, get_output_path
from security import limiter

warnings.simplefilter("ignore", ResourceWarning)


class RaidNexusSmokeTests(unittest.TestCase):
    """Verify core startup, dispatch, scenario, and ML generation flows."""

    @staticmethod
    def _unwrap_payload(payload):
        """Handle both raw and enveloped API responses in tests."""

        if isinstance(payload, dict) and "status" in payload and "data" in payload:
            return payload["data"]
        return payload

    def _close_responses(self, *responses) -> None:
        """Explicitly close httpx responses to avoid leaked in-memory streams."""

        for response in responses:
            response.close()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_root = Path(self.temp_dir.name)
        os.environ["RAID_NEXUS_DB_PATH"] = str(temp_root / "raid_nexus.db")
        os.environ["RAID_NEXUS_TRAINING_DATA_PATH"] = str(temp_root / "training_data.csv")

        db_path = get_db_path()
        output_path = get_output_path()
        if db_path.exists():
            db_path.unlink()
        if output_path.exists():
            output_path.unlink()

    def tearDown(self) -> None:
        os.environ.pop("RAID_NEXUS_DB_PATH", None)
        os.environ.pop("RAID_NEXUS_TRAINING_DATA_PATH", None)
        self.temp_dir.cleanup()

    def test_health_and_seed_counts(self) -> None:
        with TestClient(create_app()) as client:
            root = client.get("/", follow_redirects=False)
            spa_route = client.get("/dashboard", follow_redirects=False)
            docs = client.get("/docs", follow_redirects=False)
            favicon = client.get("/favicon.ico")
            health = client.get("/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["status"], "ok")
            self.assertEqual(root.status_code, 200)
            self.assertEqual(root.headers["content-type"], "text/html; charset=utf-8")
            self.assertIn('<div id="root"></div>', root.text)
            self.assertEqual(spa_route.status_code, 200)
            self.assertEqual(spa_route.headers["content-type"], "text/html; charset=utf-8")
            self.assertEqual(docs.status_code, 200)
            self.assertEqual(favicon.status_code, 200)
            self.assertEqual(favicon.headers["content-type"], "image/svg+xml")

            ambulances = client.get("/api/ambulances")
            hospitals = client.get("/api/hospitals")
            incidents = client.get("/api/incidents")

            self.assertEqual(ambulances.status_code, 200)
            self.assertEqual(hospitals.status_code, 200)
            self.assertEqual(incidents.status_code, 200)
            self.assertEqual(len(self._unwrap_payload(ambulances.json())), 15)
            self.assertEqual(len(self._unwrap_payload(hospitals.json())), 10)
            self.assertEqual(len(self._unwrap_payload(incidents.json())), 50)
            self._close_responses(root, spa_route, docs, favicon, health, ambulances, hospitals, incidents)

    def test_patient_dispatch_flow(self) -> None:
        with TestClient(create_app()) as client:
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
            body = self._unwrap_payload(response.json())
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
            self._close_responses(response, patient_details, dispatch_details, analytics)

    def test_scenarios_and_generator(self) -> None:
        with TestClient(create_app()) as client:
            limiter._storage.reset()
            traffic = client.post("/api/simulate/scenario", json={"type": "traffic"})
            limiter._storage.reset()
            breakdown = client.post("/api/simulate/scenario", json={"type": "breakdown"})
            limiter._storage.reset()
            overload = client.post("/api/simulate/scenario", json={"type": "overload"})

            self.assertEqual(traffic.status_code, 200)
            self.assertEqual(breakdown.status_code, 200)
            self.assertEqual(overload.status_code, 200)
            self.assertEqual(traffic.json()["traffic"]["multiplier"], 2.5)
            self.assertEqual(breakdown.json()["breakdown"]["ambulance_id"], "AMB-007")
            self.assertEqual(overload.json()["overload"]["hospital_id"], "HOSP-005")
            self._close_responses(traffic, breakdown, overload)

        dataset = generate_training_data()
        self.assertEqual(len(dataset), 10000)
        output_path = get_output_path()
        self.assertTrue(output_path.exists())
        with output_path.open("r", encoding="utf-8") as handle:
            line_count = sum(1 for _ in handle)
        self.assertEqual(line_count, 10001)


if __name__ == "__main__":
    unittest.main()
