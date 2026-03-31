"""Text-based triage logic for patient complaints and incident context."""

from __future__ import annotations

from config import SEVERITY_ORDER, SEVERITY_PRIORITY, TRIAGE_KEYWORDS


def bump_severity(severity: str) -> str:
    """Increase a severity label by one level without exceeding critical."""

    index = min(SEVERITY_ORDER.index(severity) + 1, len(SEVERITY_ORDER) - 1)
    return SEVERITY_ORDER[index]


def classify_severity(chief_complaint: str, sos_mode: bool) -> dict[str, str | float]:
    """Classify severity, incident type, and ambulance requirement from complaint text."""

    complaint = chief_complaint.lower()
    incident_type = "other"
    severity = "medium"
    required_ambulance_type = "BLS"

    if any(keyword in complaint for keyword in TRIAGE_KEYWORDS["cardiac"]):
        incident_type = "cardiac"
        severity = "critical"
        required_ambulance_type = "ALS"
    elif any(keyword in complaint for keyword in TRIAGE_KEYWORDS["trauma"]):
        incident_type = "trauma"
        severity = "high"
        if any(token in complaint for token in ("multiple", "severe", "major", "bleeding")):
            required_ambulance_type = "ALS"
        else:
            required_ambulance_type = "BLS"
    elif any(keyword in complaint for keyword in TRIAGE_KEYWORDS["respiratory"]):
        incident_type = "respiratory"
        severity = "high"
        required_ambulance_type = "ALS"

    if sos_mode:
        severity = bump_severity(severity)
        required_ambulance_type = "ALS"

    return {
        "severity": severity,
        "incident_type": incident_type,
        "required_ambulance_type": required_ambulance_type,
        "priority_score": SEVERITY_PRIORITY[severity],
    }
