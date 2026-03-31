"""FastAPI application entrypoint for RAID Nexus Day 1."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.ambulances import router as ambulances_router
from api.dispatch import router as dispatch_router
from api.hospitals import router as hospitals_router
from api.incidents import router as incidents_router
from api.patients import router as patients_router
from api.system import router as system_router
from api.websocket import router as websocket_router
from config import isoformat_utc
from database import initialize_database, load_seed_data
from simulation.engine import SimulationEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database state and background services for the app."""

    await initialize_database()
    inserted = await load_seed_data()
    logger.info(
        "Loaded %s ambulances, %s hospitals, %s incidents",
        inserted["ambulances"],
        inserted["hospitals"],
        inserted["incidents"],
    )
    app.state.simulation_engine = SimulationEngine()
    await app.state.simulation_engine.start()
    try:
        yield
    finally:
        await app.state.simulation_engine.stop()


app = FastAPI(title="RAID Nexus", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(websocket_router)
app.include_router(ambulances_router, prefix="/api")
app.include_router(hospitals_router, prefix="/api")
app.include_router(incidents_router, prefix="/api")
app.include_router(patients_router, prefix="/api")
app.include_router(dispatch_router, prefix="/api")
app.include_router(system_router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    """Return a simple liveness payload."""

    return {"status": "ok", "timestamp": isoformat_utc()}
