"""WebSocket endpoint and broadcast manager for live RAID Nexus events."""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from database import fetch_all
from services.geo_service import get_active_traffic_multiplier

try:
    from api.auth import verify_ws_token
except ModuleNotFoundError:
    from backend.api.auth import verify_ws_token

router = APIRouter()
_connected_clients: dict[WebSocket, dict[str, Any]] = {}
_connection_lock = asyncio.Lock()


async def state_snapshot_payload() -> dict[str, Any]:
    """Build the snapshot sent immediately after a WebSocket connection opens."""

    ambulances = await fetch_all("ambulances")
    hospitals = await fetch_all("hospitals")
    traffic = {hospital["city"]: get_active_traffic_multiplier(hospital["city"]) for hospital in hospitals}
    return {
        "type": "state_snapshot",
        "ambulances": ambulances,
        "hospitals": hospitals,
        "traffic_multipliers": traffic,
    }


async def _broadcast_to_matching_clients(
    event: dict[str, Any],
    predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> None:
    async with _connection_lock:
        disconnected: list[WebSocket] = []
        for websocket, user in _connected_clients.items():
            if predicate is not None and not predicate(user):
                continue
            try:
                await websocket.send_json(event)
            except Exception:
                disconnected.append(websocket)
        for websocket in disconnected:
            _connected_clients.pop(websocket, None)


async def broadcast_event(event: dict[str, Any]) -> None:
    """Broadcast a JSON event to all connected WebSocket clients."""

    await _broadcast_to_matching_clients(event)


async def broadcast_admin_event(event: dict[str, Any]) -> None:
    """Broadcast a JSON event only to connected admin clients."""

    await _broadcast_to_matching_clients(event, predicate=lambda user: user.get("role") == "admin")


async def _send_ping_messages(websocket: WebSocket) -> None:
    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        return
    except Exception:
        return


@router.websocket("/ws/live")
async def live_feed(websocket: WebSocket, token: str | None = Query(default=None)) -> None:
    """Stream state snapshots and live simulation events to authorized clients."""

    user = await verify_ws_token(token)
    if user is None:
        await websocket.close(code=1008, reason="Unauthorized")
        return

    await websocket.accept()
    async with _connection_lock:
        _connected_clients[websocket] = user
    ping_task = asyncio.create_task(_send_ping_messages(websocket))
    try:
        await websocket.send_json(await state_snapshot_payload())
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return
    finally:
        ping_task.cancel()
        try:
            await ping_task
        except asyncio.CancelledError:
            pass
        async with _connection_lock:
            _connected_clients.pop(websocket, None)
