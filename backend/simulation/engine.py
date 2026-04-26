"""Async simulation engine for live ambulance and hospital updates."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from datetime import timedelta
from typing import Any

from config import AUTO_BREAKDOWN_INTERVAL, AUTO_BREAKDOWN_TICKS, INCIDENT_GENERATION_INTERVAL, SIMULATION_TICK_SECONDS, TRAFFIC_STATE, isoformat_utc, utc_now
from database import fetch_all, fetch_one, update_record
from services.dispatch_service import full_dispatch_pipeline
from simulation.ambulance_sim import advance_ambulances
from simulation.hospital_sim import fluctuate_hospitals
from simulation.incident_sim import generate_random_incident

logger = logging.getLogger(__name__)


class SimulationEngine:
    """Run background simulation ticks without blocking FastAPI endpoints."""

    def __init__(self) -> None:
        self.task: asyncio.Task | None = None
        self.stop_event = asyncio.Event()
        self.tick_count = 0
        self.random_source = random.Random(42)
        self.hold_ticks: dict[str, int] = {}
        self.ambulance_outages: dict[str, Any] = {}

    async def start(self) -> None:
        """Start the simulation task if it is not already running."""

        if self.task is None or self.task.done():
            self.stop_event = asyncio.Event()
            self.task = asyncio.create_task(self.run(), name="raid-nexus-simulation")
            logger.info("Simulation engine started")

    async def stop(self) -> None:
        """Cancel the simulation task and wait for cleanup."""

        if self.task is None:
            return
        self.stop_event.set()
        with contextlib.suppress(asyncio.CancelledError):
            await self.task
        self.task = None

    async def run(self) -> None:
        """Execute simulation ticks until cancellation."""

        while not self.stop_event.is_set():
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=SIMULATION_TICK_SECONDS)
            except asyncio.TimeoutError:
                await self.tick()

    async def tick(self) -> None:
        """Perform a single simulation tick."""

        self.tick_count += 1
        self._clear_expired_traffic()
        await advance_ambulances(self)
        await fluctuate_hospitals(self.random_source)

        if self.tick_count % INCIDENT_GENERATION_INTERVAL == 0:
            incident = await generate_random_incident(self.random_source)
            try:
                await full_dispatch_pipeline(str(incident["id"]), str(incident.get("patient_id")) if incident.get("patient_id") else None)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("Auto-dispatch failed for simulated incident %s: %s", incident["id"], exc)

        if self.tick_count % AUTO_BREAKDOWN_INTERVAL == 0:
            await self._trigger_random_breakdown()

        from api.websocket import broadcast_event

        await broadcast_event(await self.snapshot_payload())

    async def snapshot_payload(self) -> dict[str, Any]:
        """Return the current state snapshot payload."""

        ambulances = await fetch_all("ambulances")
        hospitals = await fetch_all("hospitals")
        return {
            "type": "simulation_tick",
            "ambulances": ambulances,
            "hospitals": hospitals,
            "timestamp": isoformat_utc(),
        }

    async def apply_traffic_override(self, city: str, multiplier: float, seconds: int) -> dict[str, Any]:
        """Apply a temporary city-level traffic override."""

        expires_at = utc_now() + timedelta(seconds=seconds)
        TRAFFIC_STATE[city] = {"multiplier": multiplier, "expires_at": expires_at}
        return {"city": city, "multiplier": multiplier, "expires_at": expires_at.isoformat()}

    async def apply_ambulance_outage(self, ambulance_id: str, seconds: int) -> dict[str, Any]:
        """Mark an ambulance unavailable for a fixed duration."""

        expires_at = utc_now() + timedelta(seconds=seconds)
        ambulance = await fetch_one("ambulances", ambulance_id)
        if ambulance is None:
            raise ValueError(f"Ambulance {ambulance_id} was not found.")
        self.ambulance_outages[ambulance_id] = expires_at
        await update_record("ambulances", ambulance_id, {"status": "unavailable"})
        return {"ambulance_id": ambulance_id, "expires_at": expires_at.isoformat()}

    async def apply_hospital_overload(self, hospital_id: str) -> dict[str, Any]:
        """Set a hospital into overload mode for demonstration."""

        hospital = await fetch_one("hospitals", hospital_id)
        if hospital is None:
            raise ValueError(f"Hospital {hospital_id} was not found.")
        await update_record(
            "hospitals",
            hospital_id,
            {
                "occupancy_pct": 95.0,
                "diversion_status": True,
                "acceptance_score": 0.1,
            },
        )
        return {"hospital_id": hospital_id, "occupancy_pct": 95.0, "diversion_status": True}

    def _clear_expired_traffic(self) -> None:
        """Reset expired traffic overrides back to default."""

        now = utc_now()
        for city, state in TRAFFIC_STATE.items():
            expires_at = state.get("expires_at")
            if expires_at is not None and expires_at <= now:
                state["multiplier"] = 1.0
                state["expires_at"] = None

    async def _trigger_random_breakdown(self) -> None:
        """Temporarily take one available ambulance out of service."""

        ambulances = await fetch_all("ambulances")
        available = [ambulance for ambulance in ambulances if ambulance["status"] == "available"]
        if not available:
            return
        selected = self.random_source.choice(available)
        await self.apply_ambulance_outage(selected["id"], AUTO_BREAKDOWN_TICKS * SIMULATION_TICK_SECONDS)
