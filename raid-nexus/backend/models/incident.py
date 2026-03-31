"""Pydantic models for incidents."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


IncidentTypeLiteral = Literal["cardiac", "trauma", "respiratory", "accident", "other"]
SeverityLiteral = Literal["low", "medium", "high", "critical"]
IncidentStatusLiteral = Literal["open", "dispatched", "resolved"]


class IncidentCreate(BaseModel):
    """Request payload for manual incident creation."""

    type: IncidentTypeLiteral
    severity: SeverityLiteral
    patient_count: int = Field(ge=1)
    location_lat: float
    location_lng: float
    city: str
    description: str
    patient_id: str | None = None


class Incident(BaseModel):
    """Incident record used by the dispatch engine."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: IncidentTypeLiteral
    severity: SeverityLiteral
    patient_count: int = Field(ge=1)
    location_lat: float
    location_lng: float
    city: str
    description: str
    status: IncidentStatusLiteral
    created_at: datetime
    patient_id: str | None = None
