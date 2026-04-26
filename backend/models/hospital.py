"""Pydantic models for hospital state."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


HospitalTypeLiteral = Literal["general", "trauma", "cardiac", "multi-specialty"]


class Hospital(BaseModel):
    """Hospital record stored in SQLite and returned by API endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(pattern=r"^HOSP(?:-[A-Z]{3})?-\d{3}$")
    name: str
    city: str
    lat: float
    lng: float
    type: HospitalTypeLiteral
    specialties: list[str]
    occupancy_pct: float = Field(ge=0.0, le=100.0)
    er_wait_minutes: int = Field(ge=0)
    icu_beds_available: int = Field(ge=0)
    total_icu_beds: int = Field(ge=0)
    trauma_support: bool
    acceptance_score: float = Field(ge=0.0, le=1.0)
    diversion_status: bool
    incoming_patients: list[str]


class HospitalStatus(BaseModel):
    """Hospital view used for live monitoring and WebSocket updates."""

    id: str
    city: str
    occupancy_pct: float
    er_wait_minutes: int
    icu_beds_available: int
    diversion_status: bool
    incoming_patients: list[str]
