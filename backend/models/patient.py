"""Pydantic models for patient intake and retrieval."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .ambulance import Ambulance
from .hospital import Hospital


GenderLiteral = Literal["male", "female", "other"]
SeverityLiteral = Literal["low", "medium", "high", "critical"]
PatientStatusLiteral = Literal["waiting", "dispatched", "arrived", "admitted"]


class PatientCreate(BaseModel):
    """Request payload for patient intake."""

    name: str
    age: int = Field(ge=0)
    gender: GenderLiteral
    mobile: str
    location_lat: float
    location_lng: float
    chief_complaint: str
    sos_mode: bool = False


class Patient(BaseModel):
    """Patient record tracked through dispatch and admission."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    age: int = Field(ge=0)
    gender: GenderLiteral
    mobile: str
    location_lat: float
    location_lng: float
    chief_complaint: str
    severity: SeverityLiteral
    sos_mode: bool
    created_at: datetime
    assigned_ambulance_id: str | None = None
    assigned_hospital_id: str | None = None
    status: PatientStatusLiteral


class PatientCreateResponse(BaseModel):
    """Response returned after patient intake triggers dispatch."""

    patient: Patient
    dispatch_plan: Any
    notification_sent: bool


class PatientDetailResponse(BaseModel):
    """Detailed patient view for the patient dashboard."""

    patient: Patient
    assigned_ambulance: Ambulance | None = None
    assigned_hospital: Hospital | None = None
