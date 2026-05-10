"""Pydantic v2 request schemas for scenario and dispatch APIs."""

from typing import Literal

from pydantic import BaseModel, Field


class ScenarioRequest(BaseModel):
    type: Literal[
        "cardiac",
        "overload",
        "breakdown",
        "traffic",
        "mass_casualty",
        "hospital_overload",
        "traffic_surge",
        "multi_zone",
    ]
    city: str = "Delhi"
    traffic_multiplier: float = Field(default=2.5, ge=0.5, le=3.0)
    duration_seconds: int = Field(default=90, ge=10, le=600)


class TrafficOverrideRequest(BaseModel):
    city: str = "Delhi"
    multiplier: float = Field(default=1.0, ge=0.5, le=3.0)
    duration_seconds: int = Field(default=300, ge=10, le=1800)


class IncidentRequest(BaseModel):
    severity: str
    location: dict
    city: str


class DispatchRequest(BaseModel):
    incident_id: str


class PatientRequest(BaseModel):
    name: str
    age: int
    city: str
    severity: str
    location: dict
