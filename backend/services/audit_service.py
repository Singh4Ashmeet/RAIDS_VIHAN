"""Audit logging helpers for dispatch and override decisions."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import uuid4

from core.config import isoformat_utc, utc_now
from repositories.database import fetch_all, fetch_one, insert_record


def _incident_context(incident: dict[str, Any] | None) -> dict[str, Any]:
    incident = incident or {}
    return {
        "incident_lat": incident.get("location_lat"),
        "incident_lng": incident.get("location_lng"),
        "incident_type": incident.get("type"),
        "incident_severity": incident.get("severity"),
        "incident_city": incident.get("city"),
    }


def _score_from_dispatch(dispatch_plan: dict[str, Any]) -> float | None:
    score_breakdown = dispatch_plan.get("score_breakdown")
    if isinstance(score_breakdown, dict) and score_breakdown.get("total_score") is not None:
        return float(score_breakdown["total_score"])
    if dispatch_plan.get("final_score") is not None:
        return float(dispatch_plan["final_score"])
    return None


def _base_audit_payload(
    *,
    event_type: str,
    dispatch_plan: dict[str, Any],
    incident: dict[str, Any] | None,
    actor_id: str,
    actor_role: str,
    final_ambulance_id: str,
    final_hospital_id: str,
    final_eta_minutes: float,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "event_type": event_type,
        "dispatch_id": dispatch_plan["id"],
        "incident_id": dispatch_plan["incident_id"],
        "actor_id": actor_id,
        "actor_role": actor_role,
        "ai_ambulance_id": dispatch_plan.get("ambulance_id"),
        "ai_hospital_id": dispatch_plan.get("hospital_id"),
        "ai_eta_minutes": dispatch_plan.get("eta_minutes"),
        "ai_score": _score_from_dispatch(dispatch_plan),
        "ai_explanation": dispatch_plan.get("explanation_text"),
        "final_ambulance_id": final_ambulance_id,
        "final_hospital_id": final_hospital_id,
        "final_eta_minutes": final_eta_minutes,
        "override_reason": None,
        "override_ambulance_id": None,
        "override_hospital_id": None,
        **_incident_context(incident),
        "created_at": isoformat_utc(),
        "metadata": metadata or {},
    }


async def log_ai_dispatch(dispatch_plan: dict, incident: dict, actor_id: str) -> str:
    """Write an audit row for an AI-created dispatch plan and return its id."""

    metadata = {
        "score_breakdown": dispatch_plan.get("score_breakdown") or {},
    }
    payload = _base_audit_payload(
        event_type="ai_dispatch",
        dispatch_plan=dispatch_plan,
        incident=incident,
        actor_id=actor_id,
        actor_role="system",
        final_ambulance_id=dispatch_plan["ambulance_id"],
        final_hospital_id=dispatch_plan["hospital_id"],
        final_eta_minutes=float(dispatch_plan["eta_minutes"]),
        metadata=metadata,
    )
    await insert_record("dispatch_audit_log", payload)
    return str(payload["id"])


async def log_human_override(
    dispatch_id: str,
    override_request: dict,
    new_eta: float,
    actor_id: str,
    original_dispatch: dict | None = None,
) -> str:
    """Write an audit row for an approved human override and return its id."""

    original_dispatch = original_dispatch or await fetch_one("dispatch_plans", dispatch_id)
    if original_dispatch is None:
        raise ValueError(f"Dispatch plan {dispatch_id} was not found.")

    incident = await fetch_one("incidents", str(original_dispatch["incident_id"]))
    payload = _base_audit_payload(
        event_type="human_override",
        dispatch_plan=original_dispatch,
        incident=incident,
        actor_id=actor_id,
        actor_role="dispatcher",
        final_ambulance_id=str(override_request["proposed_ambulance_id"]),
        final_hospital_id=str(override_request["proposed_hospital_id"]),
        final_eta_minutes=float(new_eta),
        metadata={"override_request": override_request},
    )
    payload.update(
        {
            "override_reason": override_request.get("reason"),
            "override_ambulance_id": override_request.get("proposed_ambulance_id"),
            "override_hospital_id": override_request.get("proposed_hospital_id"),
        }
    )
    await insert_record("dispatch_audit_log", payload)
    return str(payload["id"])


async def log_fallback(dispatch_plan: dict, incident: dict) -> str:
    """Write an audit row for a fallback dispatch and return its id."""

    payload = _base_audit_payload(
        event_type="fallback_dispatch",
        dispatch_plan=dispatch_plan,
        incident=incident,
        actor_id="system",
        actor_role="system",
        final_ambulance_id=dispatch_plan["ambulance_id"],
        final_hospital_id=dispatch_plan["hospital_id"],
        final_eta_minutes=float(dispatch_plan["eta_minutes"]),
        metadata={"score_breakdown": dispatch_plan.get("score_breakdown") or {}},
    )
    await insert_record("dispatch_audit_log", payload)
    return str(payload["id"])


async def get_audit_trail(dispatch_id: str) -> list[dict]:
    """Return audit entries for one dispatch, ordered from oldest to newest."""

    return await fetch_all(
        "dispatch_audit_log",
        where_clause="dispatch_id = ?",
        params=(dispatch_id,),
    )


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


async def get_override_stats(city: str = None, days: int = 7) -> dict:
    """Return aggregate override metrics for a recent audit window."""

    cutoff = isoformat_utc(utc_now() - timedelta(days=max(days, 0)))
    where_parts = ["created_at >= ?"]
    params: list[Any] = [cutoff]
    if city:
        where_parts.append("incident_city = ?")
        params.append(city)

    rows = await fetch_all(
        "dispatch_audit_log",
        where_clause=" AND ".join(where_parts),
        params=tuple(params),
    )

    dispatch_events = [
        row
        for row in rows
        if row["event_type"] in {"ai_dispatch", "fallback_dispatch", "human_override"}
    ]
    override_events = [row for row in rows if row["event_type"] == "human_override"]

    overrides_by_reason: dict[str, int] = {}
    overrides_by_incident_type: dict[str, int] = {}
    for row in override_events:
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        override_request = metadata.get("override_request", {}) if isinstance(metadata, dict) else {}
        reason = str(override_request.get("reason_category") or "other")
        incident_type = str(row.get("incident_type") or "unknown")
        overrides_by_reason[reason] = overrides_by_reason.get(reason, 0) + 1
        overrides_by_incident_type[incident_type] = overrides_by_incident_type.get(incident_type, 0) + 1

    ai_etas = [
        float(row["ai_eta_minutes"])
        for row in dispatch_events
        if row.get("ai_eta_minutes") is not None
    ]
    override_etas = [
        float(row["final_eta_minutes"])
        for row in override_events
        if row.get("final_eta_minutes") is not None
    ]
    avg_eta_ai = _avg(ai_etas)
    avg_eta_override = _avg(override_etas)
    eta_change_on_override = round(avg_eta_override - avg_eta_ai, 2) if override_events and ai_etas else 0.0
    total_dispatches = len(dispatch_events)
    total_overrides = len(override_events)

    return {
        "total_dispatches": total_dispatches,
        "total_overrides": total_overrides,
        "override_rate_pct": round((total_overrides / total_dispatches) * 100, 2)
        if total_dispatches
        else 0.0,
        "overrides_by_reason": overrides_by_reason,
        "overrides_by_incident_type": overrides_by_incident_type,
        "avg_eta_ai": avg_eta_ai,
        "avg_eta_override": avg_eta_override,
        "eta_change_on_override": eta_change_on_override,
    }
