"""Pydantic v2 request schemas for scenario and dispatch APIs."""

from typing import Literal

from pydantic import BaseModel


class ScenarioRequest(BaseModel):
    type: Literal["cardiac", "overload", "breakdown", "traffic"]


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
