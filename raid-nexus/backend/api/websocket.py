"""WebSocket endpoint and broadcast manager for live RAID Nexus events."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from database import fetch_all
from services.geo_service import get_active_traffic_multiplier

router = APIRouter()
_active_connections: set[WebSocket] = set()
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


async def broadcast_event(event: dict[str, Any]) -> None:
    """Broadcast a JSON event to all connected WebSocket clients."""

    async with _connection_lock:
        disconnected: list[WebSocket] = []
        for websocket in _active_connections:
            try:
                await websocket.send_json(event)
            except Exception:
                disconnected.append(websocket)
        for websocket in disconnected:
            _active_connections.discard(websocket)


@router.websocket("/ws/live")
async def live_feed(websocket: WebSocket) -> None:
    """Stream state snapshots and live simulation events to clients."""

    await websocket.accept()
    async with _connection_lock:
        _active_connections.add(websocket)
    await websocket.send_json(await state_snapshot_payload())
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        async with _connection_lock:
            _active_connections.discard(websocket)
