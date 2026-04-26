"""Pydantic models for ambulance state."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AmbulanceStatusLiteral = Literal[
    "available",
    "en_route",
    "at_scene",
    "transporting",
    "at_hospital",
    "unavailable",
]

AmbulanceTypeLiteral = Literal["BLS", "ALS"]


class Ambulance(BaseModel):
    """Ambulance record used across API, DB, and simulation flows."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(pattern=r"^AMB(?:-[A-Z]{3})?-\d{3}$")
    city: str
    current_lat: float
    current_lng: float
    status: AmbulanceStatusLiteral
    type: AmbulanceTypeLiteral
    equipment: list[str]
    speed_kmh: float
    crew_readiness: float = Field(ge=0.0, le=1.0)
    assigned_incident_id: str | None = None
    assigned_hospital_id: str | None = None
    zone: str


class AmbulanceStatus(BaseModel):
    """Live ambulance projection used in state snapshots."""

    id: str
    city: str
    current_lat: float
    current_lng: float
    status: AmbulanceStatusLiteral
    assigned_incident_id: str | None = None
    assigned_hospital_id: str | None = None
