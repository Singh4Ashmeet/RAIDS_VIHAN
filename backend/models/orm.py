"""SQLAlchemy ORM models for RAID Nexus persistence."""

from sqlalchemy import Boolean, Float, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for SQLAlchemy async ORM models."""


class Ambulance(Base):
    __tablename__ = "ambulances"
    __table_args__ = (
        Index("ix_ambulances_city_status", "city", "status"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    city: Mapped[str] = mapped_column(String, index=True)
    current_lat: Mapped[float] = mapped_column(Float)
    current_lng: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, index=True)
    type: Mapped[str] = mapped_column(String)
    equipment: Mapped[str] = mapped_column(Text)
    speed_kmh: Mapped[float] = mapped_column(Float)
    crew_readiness: Mapped[float] = mapped_column(Float)
    assigned_incident_id: Mapped[str] = mapped_column(String, nullable=True)
    assigned_hospital_id: Mapped[str] = mapped_column(String, nullable=True)
    zone: Mapped[str] = mapped_column(String)


class Hospital(Base):
    __tablename__ = "hospitals"
    __table_args__ = (
        Index("ix_hospitals_diversion_status", "diversion_status"),
        Index("ix_hospitals_city_diversion", "city", "diversion_status"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String, index=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    type: Mapped[str] = mapped_column(String)
    specialties: Mapped[str] = mapped_column(Text)
    occupancy_pct: Mapped[float] = mapped_column(Float)
    er_wait_minutes: Mapped[int] = mapped_column(Integer)
    icu_beds_available: Mapped[int] = mapped_column(Integer)
    total_icu_beds: Mapped[int] = mapped_column(Integer)
    trauma_support: Mapped[bool] = mapped_column(Boolean)
    acceptance_score: Mapped[float] = mapped_column(Float)
    diversion_status: Mapped[bool] = mapped_column(Boolean, default=False)
    incoming_patients: Mapped[str] = mapped_column(Text)


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("ix_incidents_city_status", "city", "status"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String, index=True)
    patient_count: Mapped[int] = mapped_column(Integer)
    location_lat: Mapped[float] = mapped_column(Float)
    location_lng: Mapped[float] = mapped_column(Float)
    city: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[str] = mapped_column(String, index=True)
    patient_id: Mapped[str] = mapped_column(String, nullable=True)
    triage_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False)
    review_reason: Mapped[str] = mapped_column(Text, nullable=True)
    triage_version: Mapped[str] = mapped_column(String, nullable=True)
    language_detected: Mapped[str] = mapped_column(String, nullable=True)
    language_name: Mapped[str] = mapped_column(String, nullable=True)
    original_complaint: Mapped[str] = mapped_column(Text, nullable=True)
    translated_complaint: Mapped[str] = mapped_column(Text, nullable=True)
    translation_model: Mapped[str] = mapped_column(String, nullable=True)
    has_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
    anomaly_flags: Mapped[str] = mapped_column(Text, nullable=True)


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (
        Index("ix_patients_status", "status"),
        Index("ix_patients_created_at", "created_at"),
        Index("ix_patients_assigned_ambulance_id", "assigned_ambulance_id"),
        Index("ix_patients_assigned_hospital_id", "assigned_hospital_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[str] = mapped_column(String)
    mobile: Mapped[str] = mapped_column(String)
    location_lat: Mapped[float] = mapped_column(Float)
    location_lng: Mapped[float] = mapped_column(Float)
    chief_complaint: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String)
    sos_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(String)
    assigned_ambulance_id: Mapped[str] = mapped_column(String, nullable=True)
    assigned_hospital_id: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String)


class DispatchPlan(Base):
    __tablename__ = "dispatch_plans"
    __table_args__ = (
        Index("ix_dispatch_plans_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    incident_id: Mapped[str] = mapped_column(String, index=True)
    patient_id: Mapped[str] = mapped_column(String, nullable=True)
    ambulance_id: Mapped[str] = mapped_column(String, index=True)
    hospital_id: Mapped[str] = mapped_column(String, index=True)
    ambulance_score: Mapped[float] = mapped_column(Float)
    hospital_score: Mapped[float] = mapped_column(Float)
    route_score: Mapped[float] = mapped_column(Float)
    final_score: Mapped[float] = mapped_column(Float)
    eta_minutes: Mapped[float] = mapped_column(Float)
    distance_km: Mapped[float] = mapped_column(Float)
    rejected_ambulances: Mapped[str] = mapped_column(Text)
    rejected_hospitals: Mapped[str] = mapped_column(Text)
    explanation_text: Mapped[str] = mapped_column(Text)
    fallback_hospital_id: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    baseline_eta_minutes: Mapped[float] = mapped_column(Float, nullable=True)
    dispatch_tier: Mapped[str] = mapped_column(String, default="heuristic")
    overload_avoided: Mapped[bool] = mapped_column(Boolean, default=False)
    override_id: Mapped[str] = mapped_column(String, nullable=True)


class DispatchAuditLog(Base):
    __tablename__ = "dispatch_audit_log"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    event_type: Mapped[str] = mapped_column(String, index=True)
    dispatch_id: Mapped[str] = mapped_column(String, index=True)
    incident_id: Mapped[str] = mapped_column(String)
    actor_id: Mapped[str] = mapped_column(String, index=True)
    actor_role: Mapped[str] = mapped_column(String)
    ai_ambulance_id: Mapped[str] = mapped_column(String, nullable=True)
    ai_hospital_id: Mapped[str] = mapped_column(String, nullable=True)
    ai_eta_minutes: Mapped[float] = mapped_column(Float, nullable=True)
    ai_score: Mapped[float] = mapped_column(Float, nullable=True)
    ai_explanation: Mapped[str] = mapped_column(Text, nullable=True)
    final_ambulance_id: Mapped[str] = mapped_column(String)
    final_hospital_id: Mapped[str] = mapped_column(String)
    final_eta_minutes: Mapped[float] = mapped_column(Float)
    override_reason: Mapped[str] = mapped_column(Text, nullable=True)
    override_ambulance_id: Mapped[str] = mapped_column(String, nullable=True)
    override_hospital_id: Mapped[str] = mapped_column(String, nullable=True)
    incident_lat: Mapped[float] = mapped_column(Float, nullable=True)
    incident_lng: Mapped[float] = mapped_column(Float, nullable=True)
    incident_type: Mapped[str] = mapped_column(String, nullable=True)
    incident_severity: Mapped[str] = mapped_column(String, nullable=True)
    incident_city: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, index=True)
    metadata_json: Mapped[str] = mapped_column("metadata", Text, nullable=True)


class AIDecision(Base):
    __tablename__ = "ai_decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    dispatch_id: Mapped[str] = mapped_column(String, index=True)
    model_used: Mapped[str] = mapped_column(String)
    explanation_json: Mapped[str] = mapped_column(Text)
    score_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, index=True)


class ETALog(Base):
    __tablename__ = "eta_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    dispatch_id: Mapped[str] = mapped_column(String, index=True)
    predicted_eta: Mapped[float] = mapped_column(Float)
    actual_eta: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[str] = mapped_column(String, index=True)


class BenchmarkResult(Base):
    __tablename__ = "benchmark_results"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    scenario_count: Mapped[int] = mapped_column(Integer)
    avg_eta: Mapped[float] = mapped_column(Float)
    accuracy: Mapped[float] = mapped_column(Float)
    created_at: Mapped[str] = mapped_column(String, index=True)


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_resolved", "resolved"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String, index=True)
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String, index=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(String, index=True)


class OverrideRequest(Base):
    __tablename__ = "override_requests"
    __table_args__ = (
        Index("ix_override_requests_requested_by", "requested_by"),
        Index("ix_override_requests_requested_at", "requested_at"),
        Index("ix_override_requests_reason_category", "reason_category"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    dispatch_id: Mapped[str] = mapped_column(String, index=True)
    requested_by: Mapped[str] = mapped_column(String)
    requested_at: Mapped[str] = mapped_column(String)
    original_ambulance_id: Mapped[str] = mapped_column(String)
    original_hospital_id: Mapped[str] = mapped_column(String)
    proposed_ambulance_id: Mapped[str] = mapped_column(String)
    proposed_hospital_id: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(Text)
    reason_category: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    reviewed_by: Mapped[str] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[str] = mapped_column(String, nullable=True)
    rejection_reason: Mapped[str] = mapped_column(Text, nullable=True)
    audit_log_id: Mapped[str] = mapped_column(String, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    hospital_id: Mapped[str] = mapped_column(String, index=True)
    patient_name: Mapped[str] = mapped_column(String)
    patient_age: Mapped[int] = mapped_column(Integer)
    patient_gender: Mapped[str] = mapped_column(String)
    chief_complaint: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String)
    eta_minutes: Mapped[float] = mapped_column(Float)
    ambulance_id: Mapped[str] = mapped_column(String)
    ambulance_equipment: Mapped[str] = mapped_column(Text)
    ambulance_type: Mapped[str] = mapped_column(String)
    prep_checklist: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[str] = mapped_column(String)
    payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String, index=True)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_role", "role"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    full_name: Mapped[str] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(String)
