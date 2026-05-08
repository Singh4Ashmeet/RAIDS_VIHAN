"""Connection manager for typed RAID Nexus WebSocket events."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import WebSocket

logger = logging.getLogger(__name__)

STANDARD_EVENT_ALIASES = {
    "incident_created": "INCIDENT_CREATED",
    "new_incident": "INCIDENT_CREATED",
    "dispatch_created": "DISPATCH_ASSIGNED",
    "dispatch_update": "DISPATCH_ASSIGNED",
    "dispatch_overridden": "DISPATCH_ASSIGNED",
    "ambulance_location_update": "AMBULANCE_UPDATED",
    "simulation_tick": "AMBULANCE_UPDATED",
    "route_change": "AMBULANCE_UPDATED",
    "hospital_notification": "HOSPITAL_UPDATED",
    "score_update": "BENCHMARK_UPDATED",
    "benchmark_updated": "BENCHMARK_UPDATED",
    "ping": "HEARTBEAT",
    "heartbeat": "HEARTBEAT",
}


def standard_event_name(event_name: str | None) -> str:
    """Return the standardized uppercase event name for a legacy event type."""

    raw = str(event_name or "message").strip()
    if not raw:
        return "MESSAGE"
    if raw.isupper():
        return raw
    return STANDARD_EVENT_ALIASES.get(raw.lower(), raw.upper())


def _utc_timestamp() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class ConnectionManager:
    """Track WebSocket clients and send normalized event payloads."""

    def __init__(self) -> None:
        self._clients: dict[str, WebSocket] = {}
        self._metadata: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        websocket: WebSocket,
        client_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Accept and register a WebSocket connection."""

        await websocket.accept()
        async with self._lock:
            self._clients[client_id] = websocket
            self._metadata[client_id] = dict(metadata or {})

    async def disconnect(self, client_id: str) -> None:
        """Forget a WebSocket client without assuming the socket is still open."""

        async with self._lock:
            self._clients.pop(client_id, None)
            self._metadata.pop(client_id, None)

    async def broadcast(self, event_name: str, payload: dict[str, Any]) -> None:
        """Broadcast an event to every connected client."""

        await self.broadcast_where(event_name, payload)

    async def broadcast_where(
        self,
        event_name: str,
        payload: dict[str, Any],
        predicate: Callable[[dict[str, Any]], bool] | None = None,
    ) -> None:
        """Broadcast an event to clients whose metadata matches a predicate."""

        event_payload = self._normalize_payload(event_name, payload)
        async with self._lock:
            recipients = [
                (client_id, websocket)
                for client_id, websocket in self._clients.items()
                if predicate is None or predicate(self._metadata.get(client_id, {}))
            ]

        disconnected: list[str] = []
        for client_id, websocket in recipients:
            try:
                await websocket.send_json(event_payload)
            except Exception as exc:
                logger.debug("WebSocket send failed for %s: %s", client_id, exc)
                disconnected.append(client_id)

        if disconnected:
            async with self._lock:
                for client_id in disconnected:
                    self._clients.pop(client_id, None)
                    self._metadata.pop(client_id, None)

    async def send_personal(self, client_id: str, event_name: str, payload: dict[str, Any]) -> None:
        """Send a typed event to one connected client."""

        event_payload = self._normalize_payload(event_name, payload)
        async with self._lock:
            websocket = self._clients.get(client_id)
        if websocket is not None:
            await websocket.send_json(event_payload)

    async def ping_all(self) -> None:
        """Send a heartbeat event to all connected clients."""

        await self.broadcast(
            "HEARTBEAT",
            {
                "type": "ping",
                "timestamp": _utc_timestamp(),
            },
        )

    def client_count(self) -> int:
        """Return the number of registered WebSocket clients."""

        return len(self._clients)

    @staticmethod
    def _normalize_payload(event_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        event = standard_event_name(event_name)
        body = dict(payload or {})
        body.setdefault("event", event)
        body.setdefault("timestamp", _utc_timestamp())
        return body
