from __future__ import annotations

import asyncio
from typing import Any

import services.dispatch as dispatch_service
import services.realtime_map as realtime_map
from services.dispatch import MANUAL_ESCALATION_TEXT, predict_with_fallback, select_dispatch


INCIDENT_MUMBAI = {
    "id": "INC-MUM-001",
    "type": "cardiac",
    "severity": "critical",
    "city": "Mumbai",
    "location_lat": 19.076,
    "location_lng": 72.8777,
}


def ambulance(
    id: str,
    city: str,
    status: str = "available",
    lat: float = 19.04,
    lng: float = 72.86,
    readiness: float = 0.9,
) -> dict[str, Any]:
    return {
        "id": id,
        "city": city,
        "status": status,
        "current_lat": lat,
        "current_lng": lng,
        "crew_readiness": readiness,
    }


def hospital(
    id: str,
    city: str,
    *,
    diversion: bool = False,
    occupancy: float = 70.0,
    lat: float = 19.12,
    lng: float = 72.83,
) -> dict[str, Any]:
    return {
        "id": id,
        "name": id,
        "city": city,
        "lat": lat,
        "lng": lng,
        "occupancy_pct": occupancy,
        "er_wait_minutes": 12,
        "diversion_status": diversion,
        "specialties": ["cardiology", "surgery"],
    }


async def fake_travel_time(
    from_lat: float,
    from_lng: float,
    to_lat: float,
    to_lng: float,
    city: str | None = None,
) -> float:
    del city
    return round((abs(float(from_lat) - float(to_lat)) + abs(float(from_lng) - float(to_lng))) * 100.0 + 1.0, 2)


async def fake_route_polyline(
    from_lat: float,
    from_lng: float,
    to_lat: float,
    to_lng: float,
) -> list[tuple[float, float]]:
    return [(float(from_lat), float(from_lng)), (float(to_lat), float(to_lng))]


def test_dispatch_ignores_out_of_city_resources(monkeypatch) -> None:
    monkeypatch.setattr(dispatch_service, "get_travel_time", fake_travel_time)
    ambulances = [
        ambulance("AMB-MUM-LOCAL", "Mumbai", lat=19.2, lng=72.95, readiness=0.8),
        ambulance("AMB-HYD-FAST", "Hyderabad", lat=19.076, lng=72.8777, readiness=1.0),
    ]
    hospitals = [
        hospital("HOSP-MUM-LOCAL", "Mumbai", lat=19.22, lng=72.9, occupancy=85),
        hospital("HOSP-HYD-FAST", "Hyderabad", lat=19.076, lng=72.8777, occupancy=10),
    ]

    selection = asyncio.run(select_dispatch(INCIDENT_MUMBAI, ambulances, hospitals))

    assert selection["status"] == "success"
    assert selection["ambulance_id"] == "AMB-MUM-LOCAL"
    assert selection["hospital_id"] == "HOSP-MUM-LOCAL"
    assert selection["dispatch_tier"] == "heuristic"
    assert selection["service_city"] == "Mumbai"
    assert selection["manual_escalation"] is False


def test_dispatch_escalates_when_no_same_city_ambulance(monkeypatch) -> None:
    monkeypatch.setattr(dispatch_service, "get_travel_time", fake_travel_time)
    selection = asyncio.run(
        select_dispatch(
            INCIDENT_MUMBAI,
            [ambulance("AMB-HYD-FAST", "Hyderabad")],
            [hospital("HOSP-MUM-LOCAL", "Mumbai")],
        )
    )

    assert selection["status"] == "error"
    assert selection["ambulance_id"] == ""
    assert selection["manual_escalation"] is True
    assert MANUAL_ESCALATION_TEXT in selection["explanation_text"]


def test_dispatch_ignores_same_city_label_when_coordinates_are_outside_service_area(monkeypatch) -> None:
    monkeypatch.setattr(dispatch_service, "get_travel_time", fake_travel_time)
    selection = asyncio.run(
        select_dispatch(
            INCIDENT_MUMBAI,
            [
                ambulance(
                    "AMB-MUM-DRIFTED",
                    "Mumbai",
                    lat=17.385,
                    lng=78.4867,
                    readiness=1.0,
                ),
                ambulance("AMB-HYD-LOCAL", "Hyderabad", lat=17.39, lng=78.49),
            ],
            [hospital("HOSP-MUM-LOCAL", "Mumbai")],
        )
    )

    assert selection["status"] == "error"
    assert selection["ambulance_id"] == ""
    assert selection["manual_escalation"] is True
    assert "No usable ambulance or hospital coordinates are inside Mumbai" in selection["explanation_text"]


def test_dispatch_uses_same_city_degraded_hospital_fallback(monkeypatch) -> None:
    monkeypatch.setattr(dispatch_service, "get_travel_time", fake_travel_time)
    selection = asyncio.run(
        select_dispatch(
            INCIDENT_MUMBAI,
            [ambulance("AMB-MUM-LOCAL", "Mumbai")],
            [
                hospital("HOSP-MUM-DIVERTED", "Mumbai", diversion=True, occupancy=94),
                hospital("HOSP-HYD-OPEN", "Hyderabad", diversion=False, occupancy=5),
            ],
        )
    )

    assert selection["status"] == "fallback"
    assert selection["ambulance_id"] == "AMB-MUM-LOCAL"
    assert selection["hospital_id"] == "HOSP-MUM-DIVERTED"
    assert selection["dispatch_tier"] == "static"
    assert selection["manual_escalation"] is False


def test_predict_with_fallback_reports_heuristic_tier() -> None:
    selected, tier = predict_with_fallback(
        [ambulance("AMB-MUM-LOCAL", "Mumbai", readiness=0.8)],
        INCIDENT_MUMBAI,
        [hospital("HOSP-MUM-LOCAL", "Mumbai")],
    )

    assert selected["id"] == "AMB-MUM-LOCAL"
    assert tier == "heuristic"


def test_predict_with_fallback_reports_static_tier_when_heuristic_cannot_score() -> None:
    selected, tier = predict_with_fallback(
        [ambulance("AMB-MUM-LOCAL", "Mumbai", readiness=0.8)],
        INCIDENT_MUMBAI,
        [],
    )

    assert selected["id"] == "AMB-MUM-LOCAL"
    assert tier == "static"


def test_dispatch_escalates_when_same_city_hospitals_are_full(monkeypatch) -> None:
    monkeypatch.setattr(dispatch_service, "get_travel_time", fake_travel_time)
    selection = asyncio.run(
        select_dispatch(
            INCIDENT_MUMBAI,
            [ambulance("AMB-MUM-LOCAL", "Mumbai")],
            [
                hospital("HOSP-MUM-FULL", "Mumbai", diversion=True, occupancy=100),
                hospital("HOSP-HYD-OPEN", "Hyderabad", diversion=False, occupancy=5),
            ],
        )
    )

    assert selection["status"] == "error"
    assert selection["hospital_id"] == ""
    assert selection["manual_escalation"] is True
    assert MANUAL_ESCALATION_TEXT in selection["explanation_text"]


def test_reroute_after_breakdown_stays_inside_incident_city(monkeypatch) -> None:
    monkeypatch.setattr(dispatch_service, "get_travel_time", fake_travel_time)
    monkeypatch.setattr(realtime_map, "get_travel_time", fake_travel_time)
    monkeypatch.setattr(realtime_map, "get_route_polyline", fake_route_polyline)

    dispatch_plan = {
        "id": "DISP-MUM-001",
        "incident_id": INCIDENT_MUMBAI["id"],
        "ambulance_id": "AMB-MUM-BROKEN",
        "hospital_id": "HOSP-MUM-LOCAL",
        "eta_minutes": 10,
        "status": "active",
    }
    ambulances = [
        ambulance("AMB-MUM-BROKEN", "Mumbai", status="unavailable", lat=19.05, lng=72.85),
        ambulance("AMB-MUM-BACKUP", "Mumbai", status="available", lat=19.18, lng=72.95),
        ambulance("AMB-HYD-FAST", "Hyderabad", status="available", lat=19.076, lng=72.8777),
    ]
    hospitals = [
        hospital("HOSP-MUM-LOCAL", "Mumbai"),
        hospital("HOSP-HYD-OPEN", "Hyderabad", occupancy=5),
    ]

    class FakeDispatchRepository:
        async def get_active(self) -> list[dict[str, Any]]:
            return [dispatch_plan]

    class FakeIncidentRepository:
        async def get_by_id(self, id: str) -> dict[str, Any] | None:
            return INCIDENT_MUMBAI if id == INCIDENT_MUMBAI["id"] else None

    class FakeAmbulanceRepository:
        async def get_all(self) -> list[dict[str, Any]]:
            return ambulances

        async def get_by_id(self, id: str) -> dict[str, Any] | None:
            return next((item for item in ambulances if item["id"] == id), None)

    class FakeHospitalRepository:
        async def get_all(self) -> list[dict[str, Any]]:
            return hospitals

        async def get_by_id(self, id: str) -> dict[str, Any] | None:
            return next((item for item in hospitals if item["id"] == id), None)

    monkeypatch.setattr(realtime_map, "DispatchRepository", FakeDispatchRepository)
    monkeypatch.setattr(realtime_map, "IncidentRepository", FakeIncidentRepository)
    monkeypatch.setattr(realtime_map, "AmbulanceRepository", FakeAmbulanceRepository)
    monkeypatch.setattr(realtime_map, "HospitalRepository", FakeHospitalRepository)

    event = asyncio.run(
        realtime_map.build_route_change_event(
            reason="ambulance_breakdown",
            city="Mumbai",
            affected_ambulance_id="AMB-MUM-BROKEN",
        )
    )

    assert event["type"] == "route_change"
    assert event["new_route"]["ambulance_id"] == "AMB-MUM-BACKUP"
    assert event["new_route"]["hospital_id"] == "HOSP-MUM-LOCAL"
    assert event["new_route"]["service_city"] == "Mumbai"


def test_reroute_without_local_replacement_blocks_new_route(monkeypatch) -> None:
    monkeypatch.setattr(dispatch_service, "get_travel_time", fake_travel_time)
    monkeypatch.setattr(realtime_map, "get_travel_time", fake_travel_time)
    monkeypatch.setattr(realtime_map, "get_route_polyline", fake_route_polyline)

    dispatch_plan = {
        "id": "DISP-MUM-002",
        "incident_id": INCIDENT_MUMBAI["id"],
        "ambulance_id": "AMB-MUM-BROKEN",
        "hospital_id": "HOSP-MUM-LOCAL",
        "eta_minutes": 10,
        "status": "active",
    }
    ambulances = [
        ambulance("AMB-MUM-BROKEN", "Mumbai", status="unavailable"),
        ambulance("AMB-HYD-FAST", "Hyderabad", status="available"),
    ]
    hospitals = [
        hospital("HOSP-MUM-LOCAL", "Mumbai"),
        hospital("HOSP-HYD-OPEN", "Hyderabad", occupancy=5),
    ]

    class FakeDispatchRepository:
        async def get_active(self) -> list[dict[str, Any]]:
            return [dispatch_plan]

    class FakeIncidentRepository:
        async def get_by_id(self, id: str) -> dict[str, Any] | None:
            return INCIDENT_MUMBAI if id == INCIDENT_MUMBAI["id"] else None

    class FakeAmbulanceRepository:
        async def get_all(self) -> list[dict[str, Any]]:
            return ambulances

        async def get_by_id(self, id: str) -> dict[str, Any] | None:
            return next((item for item in ambulances if item["id"] == id), None)

    class FakeHospitalRepository:
        async def get_all(self) -> list[dict[str, Any]]:
            return hospitals

        async def get_by_id(self, id: str) -> dict[str, Any] | None:
            return next((item for item in hospitals if item["id"] == id), None)

    monkeypatch.setattr(realtime_map, "DispatchRepository", FakeDispatchRepository)
    monkeypatch.setattr(realtime_map, "IncidentRepository", FakeIncidentRepository)
    monkeypatch.setattr(realtime_map, "AmbulanceRepository", FakeAmbulanceRepository)
    monkeypatch.setattr(realtime_map, "HospitalRepository", FakeHospitalRepository)

    event = asyncio.run(
        realtime_map.build_route_change_event(
            reason="ambulance_breakdown",
            city="Mumbai",
            affected_ambulance_id="AMB-MUM-BROKEN",
        )
    )

    assert event["type"] == "route_change"
    assert event["new_route"] is None
    assert event["manual_escalation"] is True
    assert event["service_city"] == "Mumbai"
    assert MANUAL_ESCALATION_TEXT in event["reroute_blocked_reason"]


def test_reroute_skips_stale_cross_city_dispatch_before_valid_local_one(monkeypatch) -> None:
    monkeypatch.setattr(dispatch_service, "get_travel_time", fake_travel_time)
    monkeypatch.setattr(realtime_map, "get_travel_time", fake_travel_time)
    monkeypatch.setattr(realtime_map, "get_route_polyline", fake_route_polyline)

    stale_dispatch = {
        "id": "DISP-MUM-STALE",
        "incident_id": INCIDENT_MUMBAI["id"],
        "ambulance_id": "AMB-HYD-LEGACY",
        "hospital_id": "HOSP-MUM-LOCAL",
        "eta_minutes": 10,
        "status": "active",
    }
    valid_dispatch = {
        "id": "DISP-MUM-VALID",
        "incident_id": INCIDENT_MUMBAI["id"],
        "ambulance_id": "AMB-MUM-ACTIVE",
        "hospital_id": "HOSP-MUM-LOCAL",
        "eta_minutes": 12,
        "status": "active",
    }
    ambulances = [
        ambulance("AMB-HYD-LEGACY", "Hyderabad", status="en_route", lat=17.385, lng=78.4867),
        ambulance("AMB-MUM-ACTIVE", "Mumbai", status="en_route", lat=19.05, lng=72.85),
        ambulance("AMB-MUM-BACKUP", "Mumbai", status="available", lat=19.18, lng=72.95),
    ]
    hospitals = [
        hospital("HOSP-MUM-LOCAL", "Mumbai"),
        hospital("HOSP-HYD-OPEN", "Hyderabad", occupancy=5),
    ]

    class FakeDispatchRepository:
        async def get_active(self) -> list[dict[str, Any]]:
            return [stale_dispatch, valid_dispatch]

    class FakeIncidentRepository:
        async def get_by_id(self, id: str) -> dict[str, Any] | None:
            return INCIDENT_MUMBAI if id == INCIDENT_MUMBAI["id"] else None

    class FakeAmbulanceRepository:
        async def get_all(self) -> list[dict[str, Any]]:
            return ambulances

        async def get_by_id(self, id: str) -> dict[str, Any] | None:
            return next((item for item in ambulances if item["id"] == id), None)

    class FakeHospitalRepository:
        async def get_all(self) -> list[dict[str, Any]]:
            return hospitals

        async def get_by_id(self, id: str) -> dict[str, Any] | None:
            return next((item for item in hospitals if item["id"] == id), None)

    monkeypatch.setattr(realtime_map, "DispatchRepository", FakeDispatchRepository)
    monkeypatch.setattr(realtime_map, "IncidentRepository", FakeIncidentRepository)
    monkeypatch.setattr(realtime_map, "AmbulanceRepository", FakeAmbulanceRepository)
    monkeypatch.setattr(realtime_map, "HospitalRepository", FakeHospitalRepository)

    event = asyncio.run(realtime_map.build_route_change_event(reason="traffic", city="Mumbai"))

    assert event["dispatch_id"] == "DISP-MUM-VALID"
    assert event["new_route"]["ambulance_id"] == "AMB-MUM-BACKUP"
    assert event["new_route"]["service_city"] == "Mumbai"
    assert event["manual_escalation"] is False
