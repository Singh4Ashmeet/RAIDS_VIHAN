"""Analytics helpers for live score updates and dashboard metrics."""

from __future__ import annotations

from datetime import datetime
from statistics import mean

from core.config import KOLKATA_TZ
from repositories.dispatch_repo import DispatchRepository
from repositories.incident_repo import IncidentRepository
from repositories.notification_repo import NotificationRepository


def _is_today_local(timestamp: str) -> bool:
    parsed = datetime.fromisoformat(timestamp)
    return parsed.astimezone(KOLKATA_TZ).date() == datetime.now(tz=KOLKATA_TZ).date()


def _score_update_analytics(analytics: dict[str, float | int]) -> dict[str, float | int]:
    return {
        "avg_eta_ai": analytics["avg_eta_ai"],
        "avg_eta_baseline": analytics["avg_eta_baseline"],
        "improvement_pct": analytics["improvement_pct"],
        "dispatches_today": analytics["dispatches_today"],
        "incidents_today": analytics["incidents_today"],
        "overloads_prevented": analytics["overloads_prevented"],
    }


async def build_analytics_snapshot() -> dict[str, float | int]:
    """Return current daily analytics for the local timezone."""

    incident_repo = IncidentRepository()
    dispatch_repo = DispatchRepository()
    notification_repo = NotificationRepository()
    incidents = [item for item in await incident_repo.get_recent(500) if _is_today_local(item["created_at"])]
    dispatches = [item for item in await dispatch_repo.get_history(500) if _is_today_local(item["created_at"])]
    notifications = [item for item in await notification_repo.get_recent(500) if _is_today_local(item["created_at"])]

    ai_eta_values = [float(item["eta_minutes"]) for item in dispatches]
    baseline_values = [
        float(item["baseline_eta_minutes"])
        for item in dispatches
        if item.get("baseline_eta_minutes") is not None
    ]
    avg_eta_ai = round(mean(ai_eta_values), 2) if ai_eta_values else 0.0
    avg_eta_baseline = round(mean(baseline_values), 2) if baseline_values else 0.0
    improvement_pct = (
        round(((avg_eta_baseline - avg_eta_ai) / avg_eta_baseline) * 100.0, 2)
        if avg_eta_baseline > 0
        else 0.0
    )
    overloads_prevented = sum(1 for item in dispatches if item.get("overload_avoided"))

    return {
        "avg_eta_ai": avg_eta_ai,
        "avg_eta_baseline": avg_eta_baseline,
        "improvement_pct": improvement_pct,
        "incidents_today": len(incidents),
        "dispatches_today": len(dispatches),
        "hospitals_notified": len(notifications),
        "overloads_prevented": overloads_prevented,
    }


async def broadcast_score_update(analytics: dict[str, float | int] | None = None) -> dict[str, float | int]:
    """Broadcast the latest analytics snapshot to all live clients."""

    snapshot = analytics or await build_analytics_snapshot()

    from api.websocket import broadcast_event

    await broadcast_event(
        {
            "type": "score_update",
            "analytics": _score_update_analytics(snapshot),
        }
    )
    return snapshot
