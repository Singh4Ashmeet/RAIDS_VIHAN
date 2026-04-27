"""Human override API routes for active dispatch plans."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from api.auth import get_current_admin
from core.config import isoformat_utc, utc_now
from repositories.database import fetch_all, fetch_one, get_connection, insert_record, update_record
from services.audit_service import get_audit_trail, get_override_stats, log_human_override
from services.routing import get_travel_time

router = APIRouter(tags=["overrides"])

ReasonCategory = Literal[
    "ambulance_closer",
    "hospital_specialty",
    "local_knowledge",
    "ai_error",
    "resource_conflict",
    "other",
]


class OverrideRequest(BaseModel):
    dispatch_id: str
    proposed_ambulance_id: str
    proposed_hospital_id: str
    reason: str
    reason_category: ReasonCategory


class OverrideResponse(BaseModel):
    override_id: str
    dispatch_id: str
    status: Literal["approved"]
    new_ambulance_id: str
    new_hospital_id: str
    new_eta_minutes: float
    audit_id: str
    created_at: str


def _bad_request(message: str) -> None:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


async def _fetch_active_dispatch(dispatch_id: str) -> dict:
    dispatches = await fetch_all(
        "dispatch_plans",
        where_clause="id = ? AND status = ?",
        params=(dispatch_id, "active"),
    )
    if not dispatches:
        _bad_request("No active dispatch found with that ID")
    return dispatches[0]


async def _fetch_available_ambulance(ambulance_id: str) -> dict:
    ambulances = await fetch_all(
        "ambulances",
        where_clause="id = ? AND status = ?",
        params=(ambulance_id, "available"),
    )
    if not ambulances:
        _bad_request("Selected ambulance is not currently available")
    return ambulances[0]


async def _fetch_open_hospital(hospital_id: str) -> dict:
    hospital = await fetch_one("hospitals", hospital_id)
    if hospital is None or hospital.get("diversion_status"):
        _bad_request("Selected hospital is on diversion")
    return hospital


def _patient_token(dispatch: dict) -> str:
    return str(dispatch.get("patient_id") or dispatch["incident_id"])


async def _move_hospital_patient_token(old_hospital_id: str, new_hospital_id: str, token: str) -> None:
    old_hospital = await fetch_one("hospitals", old_hospital_id)
    new_hospital = await fetch_one("hospitals", new_hospital_id)

    if old_hospital is not None:
        incoming = [item for item in list(old_hospital.get("incoming_patients", [])) if item != token]
        await update_record("hospitals", old_hospital_id, {"incoming_patients": incoming})

    if new_hospital is not None:
        incoming = list(new_hospital.get("incoming_patients", []))
        if token not in incoming:
            incoming.append(token)
        await update_record("hospitals", new_hospital_id, {"incoming_patients": incoming})


async def _eta_to_scene(ambulance: dict, incident: dict) -> float:
    return await get_travel_time(
        float(ambulance["current_lat"]),
        float(ambulance["current_lng"]),
        float(incident["location_lat"]),
        float(incident["location_lng"]),
        city=incident.get("city"),
    )


@router.post("/overrides/request", response_model=OverrideResponse)
async def request_override(
    payload: OverrideRequest,
    current_user: dict = Depends(get_current_admin),
) -> OverrideResponse:
    reason = payload.reason.strip()
    if len(reason) < 20:
        _bad_request("Please provide a detailed reason (minimum 20 characters)")
    if len(reason) > 500:
        _bad_request("Reason must be 500 characters or fewer")

    original_dispatch = await _fetch_active_dispatch(payload.dispatch_id)
    new_ambulance = await _fetch_available_ambulance(payload.proposed_ambulance_id)
    await _fetch_open_hospital(payload.proposed_hospital_id)

    same_ambulance = payload.proposed_ambulance_id == original_dispatch["ambulance_id"]
    same_hospital = payload.proposed_hospital_id == original_dispatch["hospital_id"]
    if same_ambulance and same_hospital:
        _bad_request("Override must select a different ambulance or hospital")

    incident = await fetch_one("incidents", str(original_dispatch["incident_id"]))
    if incident is None:
        _bad_request("Dispatch incident could not be found")

    override_id = str(uuid4())
    requested_at = isoformat_utc()
    override_record = {
        "id": override_id,
        "dispatch_id": original_dispatch["id"],
        "requested_by": current_user["id"],
        "requested_at": requested_at,
        "original_ambulance_id": original_dispatch["ambulance_id"],
        "original_hospital_id": original_dispatch["hospital_id"],
        "proposed_ambulance_id": payload.proposed_ambulance_id,
        "proposed_hospital_id": payload.proposed_hospital_id,
        "reason": reason,
        "reason_category": payload.reason_category,
        "status": "pending",
        "reviewed_by": None,
        "reviewed_at": None,
        "rejection_reason": None,
        "audit_log_id": None,
    }
    await insert_record("override_requests", override_record)

    new_eta_minutes = await _eta_to_scene(new_ambulance, incident)
    audit_id = await log_human_override(
        original_dispatch["id"],
        override_record,
        new_eta_minutes,
        current_user["id"],
        original_dispatch=original_dispatch,
    )
    reviewed_at = isoformat_utc()

    await update_record(
        "override_requests",
        override_id,
        {
            "status": "approved",
            "reviewed_by": current_user["id"],
            "reviewed_at": reviewed_at,
            "audit_log_id": audit_id,
        },
    )
    await update_record(
        "dispatch_plans",
        original_dispatch["id"],
        {
            "ambulance_id": payload.proposed_ambulance_id,
            "hospital_id": payload.proposed_hospital_id,
            "eta_minutes": new_eta_minutes,
            "status": "overridden",
            "override_id": override_id,
        },
    )
    await update_record(
        "ambulances",
        str(original_dispatch["ambulance_id"]),
        {
            "status": "available",
            "assigned_incident_id": None,
            "assigned_hospital_id": None,
        },
    )
    await update_record(
        "ambulances",
        payload.proposed_ambulance_id,
        {
            "status": "en_route",
            "assigned_incident_id": original_dispatch["incident_id"],
            "assigned_hospital_id": payload.proposed_hospital_id,
        },
    )
    await _move_hospital_patient_token(
        str(original_dispatch["hospital_id"]),
        payload.proposed_hospital_id,
        _patient_token(original_dispatch),
    )

    from api.websocket import broadcast_event

    await broadcast_event(
        {
            "type": "dispatch_overridden",
            "dispatch_id": original_dispatch["id"],
            "override_id": override_id,
            "overridden_by": current_user["id"],
            "original_ambulance_id": original_dispatch["ambulance_id"],
            "new_ambulance_id": payload.proposed_ambulance_id,
            "original_hospital_id": original_dispatch["hospital_id"],
            "new_hospital_id": payload.proposed_hospital_id,
            "new_eta_minutes": new_eta_minutes,
            "reason": reason,
            "reason_category": payload.reason_category,
            "audit_id": audit_id,
            "timestamp": reviewed_at,
        }
    )

    return OverrideResponse(
        override_id=override_id,
        dispatch_id=original_dispatch["id"],
        status="approved",
        new_ambulance_id=payload.proposed_ambulance_id,
        new_hospital_id=payload.proposed_hospital_id,
        new_eta_minutes=new_eta_minutes,
        audit_id=audit_id,
        created_at=requested_at,
    )


@router.get("/overrides/history")
async def override_history(
    city: str | None = None,
    days: int = Query(default=7, ge=1, le=30),
    incident_type: str | None = None,
    reason_category: ReasonCategory | None = None,
    _admin: dict = Depends(get_current_admin),
) -> list[dict]:
    cutoff = isoformat_utc(utc_now() - timedelta(days=days))
    where_parts = ["override_requests.requested_at >= ?"]
    params: list[object] = [cutoff]
    if city:
        where_parts.append("dispatch_audit_log.incident_city = ?")
        params.append(city)
    if incident_type:
        where_parts.append("dispatch_audit_log.incident_type = ?")
        params.append(incident_type)
    if reason_category:
        where_parts.append("override_requests.reason_category = ?")
        params.append(reason_category)

    async with get_connection() as connection:
        cursor = await connection.execute(
            f"""
            SELECT
                override_requests.*,
                dispatch_audit_log.ai_eta_minutes,
                dispatch_audit_log.final_eta_minutes,
                dispatch_audit_log.incident_city,
                dispatch_audit_log.incident_type
            FROM override_requests
            LEFT JOIN dispatch_audit_log
                ON override_requests.audit_log_id = dispatch_audit_log.id
            WHERE {' AND '.join(where_parts)}
            ORDER BY override_requests.requested_at DESC
            LIMIT 100
            """,
            tuple(params),
        )
        rows = [dict(row) for row in await cursor.fetchall()]

    for row in rows:
        ai_eta = row.get("ai_eta_minutes")
        final_eta = row.get("final_eta_minutes")
        row["eta_delta"] = round(float(final_eta) - float(ai_eta), 2) if ai_eta is not None and final_eta is not None else None
    return rows


@router.get("/overrides/stats")
async def override_stats(
    city: str | None = None,
    days: int = Query(default=7, ge=1, le=30),
    _admin: dict = Depends(get_current_admin),
) -> dict:
    stats = await get_override_stats(city=city, days=days)
    reasons = stats.get("overrides_by_reason", {})
    most_common = max(reasons, key=reasons.get) if reasons else ""
    return {**stats, "most_common_override_reason": most_common}


@router.get("/dispatches/{dispatch_id}/audit")
async def dispatch_audit(
    dispatch_id: str,
    _admin: dict = Depends(get_current_admin),
) -> list[dict]:
    audit_trail = await get_audit_trail(dispatch_id)
    if not audit_trail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No audit records found for this dispatch")
    return audit_trail


@router.get("/overrides/available-units")
async def available_units(
    city: str,
    incident_lat: float | None = None,
    incident_lng: float | None = None,
    _admin: dict = Depends(get_current_admin),
) -> dict:
    ambulances = await fetch_all("ambulances", where_clause="city = ?", params=(city,))
    hospitals = await fetch_all("hospitals", where_clause="city = ?", params=(city,))

    eta_by_ambulance: dict[str, float | None] = {ambulance["id"]: None for ambulance in ambulances}
    if incident_lat is not None and incident_lng is not None:
        available_ambulances = [ambulance for ambulance in ambulances if ambulance.get("status") == "available"]
        eta_values = await asyncio.gather(
            *[
                get_travel_time(
                    float(ambulance["current_lat"]),
                    float(ambulance["current_lng"]),
                    incident_lat,
                    incident_lng,
                    city=city,
                )
                for ambulance in available_ambulances
            ]
        )
        eta_by_ambulance.update(
            {
                ambulance["id"]: eta
                for ambulance, eta in zip(available_ambulances, eta_values, strict=False)
            }
        )

    return {
        "ambulances": [
            {
                "id": ambulance["id"],
                "status": ambulance["status"],
                "type": ambulance["type"],
                "crew_readiness": ambulance["crew_readiness"],
                "lat": ambulance["current_lat"],
                "lng": ambulance["current_lng"],
                "eta_to_scene": eta_by_ambulance[ambulance["id"]],
            }
            for ambulance in ambulances
        ],
        "hospitals": [
            {
                "id": hospital["id"],
                "name": hospital["name"],
                "occupancy_pct": hospital["occupancy_pct"],
                "er_wait_minutes": hospital["er_wait_minutes"],
                "diversion_status": hospital["diversion_status"],
                "specialties": hospital["specialties"],
            }
            for hospital in hospitals
        ],
    }
