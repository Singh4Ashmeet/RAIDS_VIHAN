"""Ambulance movement and lifecycle helpers for simulation ticks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config import AMBULANCE_STEP_MAX, AMBULANCE_STEP_MIN, HOSPITAL_HOLD_TICKS, SCENE_HOLD_TICKS, utc_now
from repositories.database import fetch_all, fetch_one, update_record
from services.geo_service import interpolate_towards
from services.routing import get_travel_time

if TYPE_CHECKING:
    from simulation.engine import SimulationEngine

ARRIVAL_THRESHOLD_MINUTES = 1.5


async def advance_ambulances(engine: "SimulationEngine") -> None:
    """Advance ambulance locations and status transitions for one tick."""

    now = utc_now()
    ambulances = await fetch_all("ambulances")
    for ambulance in ambulances:
        outage_until = engine.ambulance_outages.get(ambulance["id"])
        if outage_until is not None and outage_until > now:
            if ambulance["status"] != "unavailable":
                await update_record("ambulances", ambulance["id"], {"status": "unavailable"})
            continue
        if outage_until is not None and outage_until <= now:
            engine.ambulance_outages.pop(ambulance["id"], None)
            if ambulance["status"] == "unavailable" and not ambulance["assigned_incident_id"]:
                await update_record("ambulances", ambulance["id"], {"status": "available"})
                ambulance["status"] = "available"

        hold_ticks = engine.hold_ticks.get(ambulance["id"], 0)
        if hold_ticks > 0:
            engine.hold_ticks[ambulance["id"]] = hold_ticks - 1
            if engine.hold_ticks[ambulance["id"]] == 0:
                if ambulance["status"] == "at_scene":
                    await update_record("ambulances", ambulance["id"], {"status": "transporting"})
                elif ambulance["status"] == "at_hospital":
                    await update_record(
                        "ambulances",
                        ambulance["id"],
                        {
                            "status": "available",
                            "assigned_incident_id": None,
                            "assigned_hospital_id": None,
                        },
                    )
                engine.hold_ticks.pop(ambulance["id"], None)
            continue

        if ambulance["status"] == "en_route" and ambulance["assigned_incident_id"]:
            incident = await fetch_one("incidents", ambulance["assigned_incident_id"])
            if incident is None:
                continue
            await _move_towards_incident(engine, ambulance, incident)
        elif ambulance["status"] == "transporting" and ambulance["assigned_hospital_id"]:
            hospital = await fetch_one("hospitals", ambulance["assigned_hospital_id"])
            incident = await fetch_one("incidents", ambulance["assigned_incident_id"]) if ambulance["assigned_incident_id"] else None
            if hospital is None:
                continue
            await _move_towards_hospital(engine, ambulance, hospital, incident)


async def _move_towards_incident(
    engine: "SimulationEngine",
    ambulance: dict,
    incident: dict,
) -> None:
    fraction = engine.random_source.uniform(AMBULANCE_STEP_MIN, AMBULANCE_STEP_MAX)
    next_lat, next_lng = interpolate_towards(
        ambulance["current_lat"],
        ambulance["current_lng"],
        incident["location_lat"],
        incident["location_lng"],
        fraction,
    )
    remaining_minutes = await get_travel_time(
        next_lat,
        next_lng,
        incident["location_lat"],
        incident["location_lng"],
        city=incident.get("city"),
    )
    updates = {"current_lat": round(next_lat, 6), "current_lng": round(next_lng, 6)}
    if remaining_minutes <= ARRIVAL_THRESHOLD_MINUTES:
        updates["status"] = "at_scene"
        engine.hold_ticks[ambulance["id"]] = SCENE_HOLD_TICKS
        if incident.get("patient_id"):
            await update_record("patients", incident["patient_id"], {"status": "arrived"})
    await update_record("ambulances", ambulance["id"], updates)


async def _move_towards_hospital(
    engine: "SimulationEngine",
    ambulance: dict,
    hospital: dict,
    incident: dict | None,
) -> None:
    fraction = engine.random_source.uniform(AMBULANCE_STEP_MIN, AMBULANCE_STEP_MAX)
    next_lat, next_lng = interpolate_towards(
        ambulance["current_lat"],
        ambulance["current_lng"],
        hospital["lat"],
        hospital["lng"],
        fraction,
    )
    remaining_minutes = await get_travel_time(
        next_lat,
        next_lng,
        hospital["lat"],
        hospital["lng"],
        city=(incident or {}).get("city") or hospital.get("city"),
    )
    updates = {"current_lat": round(next_lat, 6), "current_lng": round(next_lng, 6)}
    if remaining_minutes <= ARRIVAL_THRESHOLD_MINUTES:
        updates["status"] = "at_hospital"
        engine.hold_ticks[ambulance["id"]] = HOSPITAL_HOLD_TICKS
        patient_token = incident.get("patient_id") if incident else None
        incoming_patients = list(hospital["incoming_patients"])
        for token in filter(None, [patient_token, incident["id"] if incident else None]):
            if token in incoming_patients:
                incoming_patients.remove(token)
        await update_record("hospitals", hospital["id"], {"incoming_patients": incoming_patients})
        if incident is not None:
            await update_record("incidents", incident["id"], {"status": "resolved"})
            if incident.get("patient_id"):
                await update_record("patients", incident["patient_id"], {"status": "admitted"})
    await update_record("ambulances", ambulance["id"], updates)
