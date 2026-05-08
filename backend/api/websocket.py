"""WebSocket endpoint and broadcast manager for live RAID Nexus events."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from repositories.ambulance_repo import AmbulanceRepository
from repositories.dispatch_repo import DispatchRepository
from repositories.hospital_repo import HospitalRepository
from repositories.incident_repo import IncidentRepository
from services.geo_service import get_active_traffic_multiplier
from services.realtime_map import build_dispatch_map_context
from websocket.manager import ConnectionManager, standard_event_name

try:
    from api.auth import verify_ws_token
except ModuleNotFoundError:
    from backend.api.auth import verify_ws_token

router = APIRouter()
websocket_manager = ConnectionManager()


async def state_snapshot_payload() -> dict[str, Any]:
    """Build the snapshot sent immediately after a WebSocket connection opens."""

    ambulances = await AmbulanceRepository().get_all()
    hospitals = await HospitalRepository().get_all()
    incidents = await IncidentRepository().get_recent(100)
    active_dispatches = await DispatchRepository().get_active()
    traffic = {hospital["city"]: get_active_traffic_multiplier(hospital["city"]) for hospital in hospitals}
    payload = {
        "type": "state_snapshot",
        "ambulances": ambulances,
        "hospitals": hospitals,
        "incidents": incidents,
        "active_dispatches": active_dispatches,
        "traffic_multipliers": traffic,
    }
    if active_dispatches:
        fallback_context = None
        for dispatch_plan in active_dispatches:
            try:
                map_context = await build_dispatch_map_context(dispatch_plan)
            except Exception:
                continue
            if map_context.get("route"):
                payload["map_context"] = map_context
                break
            fallback_context = fallback_context or map_context
        else:
            payload["map_context"] = fallback_context
    return payload


async def _broadcast_to_matching_clients(
    event: dict[str, Any],
    predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> None:
    event_name = standard_event_name(str(event.get("event") or event.get("type") or "message"))
    await websocket_manager.broadcast_where(event_name, event, predicate=predicate)


async def broadcast_event(event: dict[str, Any]) -> None:
    """Broadcast a JSON event to all connected WebSocket clients."""

    await _broadcast_to_matching_clients(event)


async def broadcast_admin_event(event: dict[str, Any]) -> None:
    """Broadcast a JSON event only to connected admin clients."""

    await _broadcast_to_matching_clients(event, predicate=lambda user: user.get("role") == "admin")


@router.get("/ws/live", include_in_schema=False)
async def live_feed_info() -> dict[str, Any]:
    """Explain how to connect to the live WebSocket from a normal browser tab."""

    return {
        "status": "ok",
        "message": "This is a WebSocket endpoint, not a normal web page.",
        "connect": "Login at /api/auth/login, then connect to /ws/live?token=<access_token> using a WebSocket client.",
    }


@router.websocket("/ws/live")
async def live_feed(websocket: WebSocket, token: str | None = Query(default=None)) -> None:
    """Stream state snapshots and live simulation events to authorized clients."""

    user = await verify_ws_token(token)
    if user is None:
        await websocket.close(code=1008, reason="Unauthorized")
        return

    client_id = f"{user.get('username') or user.get('sub') or 'client'}:{id(websocket)}"
    await websocket_manager.connect(websocket, client_id, user)
    try:
        await websocket_manager.send_personal(client_id, "STATE_SNAPSHOT", await state_snapshot_payload())
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return
    finally:
        await websocket_manager.disconnect(client_id)
