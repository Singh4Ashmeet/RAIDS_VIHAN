"""Ambulance movement and lifecycle helpers for simulation ticks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.config import AMBULANCE_STEP_MAX, AMBULANCE_STEP_MIN, HOSPITAL_HOLD_TICKS, SCENE_HOLD_TICKS, utc_now
from repositories.database import fetch_all, fetch_one, update_record
from services.geo_service import home_city_position, interpolate_towards, is_coordinate_in_city, same_city
from services.routing import get_travel_time

if TYPE_CHECKING:
    from simulation.engine import SimulationEngine

ARRIVAL_THRESHOLD_MINUTES = 1.5


async def advance_ambulances(engine: "SimulationEngine") -> None:
    """Advance ambulance locations and status transitions for one tick."""

    now = utc_now()
    ambulances = await fetch_all("ambulances")
    for ambulance in ambulances:
        if await _release_invalid_assignment(ambulance):
            continue
        if await _rehome_available_unit(ambulance):
            continue

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


async def _release_invalid_assignment(ambulance: dict) -> bool:
    """Stop legacy cross-city assignments from moving units across India."""

    incident = None
    hospital = None
    if ambulance.get("assigned_incident_id"):
        incident = await fetch_one("incidents", ambulance["assigned_incident_id"])
    if ambulance.get("assigned_hospital_id"):
        hospital = await fetch_one("hospitals", ambulance["assigned_hospital_id"])

    mismatched_incident = incident is not None and not same_city(ambulance.get("city"), incident.get("city"))
    mismatched_hospital = hospital is not None and not same_city(ambulance.get("city"), hospital.get("city"))
    if not (mismatched_incident or mismatched_hospital):
        return False

    home_position = home_city_position(ambulance.get("city"))
    updates = {
        "status": "available",
        "assigned_incident_id": None,
        "assigned_hospital_id": None,
    }
    if home_position is not None:
        updates["current_lat"] = round(home_position[0], 6)
        updates["current_lng"] = round(home_position[1], 6)
    await update_record("ambulances", ambulance["id"], updates)
    return True


async def _rehome_available_unit(ambulance: dict) -> bool:
    """Keep idle units inside their declared city service area."""

    if ambulance.get("status") != "available":
        return False
    if is_coordinate_in_city(
        ambulance.get("city"),
        ambulance.get("current_lat"),
        ambulance.get("current_lng"),
        margin=0.03,
    ):
        return False

    home_position = home_city_position(ambulance.get("city"))
    if home_position is None:
        return False
    await update_record(
        "ambulances",
        ambulance["id"],
        {
            "current_lat": round(home_position[0], 6),
            "current_lng": round(home_position[1], 6),
            "assigned_incident_id": None,
            "assigned_hospital_id": None,
        },
    )
    return True


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
