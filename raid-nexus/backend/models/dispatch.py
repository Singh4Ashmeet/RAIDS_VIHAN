"""Pydantic models for dispatch decisions and score explainability."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScoreBreakdown(BaseModel):
    """Generic score breakdown object stored for explainability."""

    component_scores: dict[str, float] = Field(default_factory=dict)
    weighted_score: float


class DispatchPlan(BaseModel):
    """Full dispatch plan returned by the routing and scoring engine."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    incident_id: str
    patient_id: str | None = None
    ambulance_id: str
    hospital_id: str
    ambulance_score: float
    hospital_score: float
    route_score: float
    final_score: float
    eta_minutes: float
    distance_km: float
    rejected_ambulances: list[dict[str, Any]]
    rejected_hospitals: list[dict[str, Any]]
    explanation_text: str
    fallback_hospital_id: str | None = None
    created_at: datetime
    status: str
