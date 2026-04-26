"""Text-based triage logic for patient complaints and incident context."""

from __future__ import annotations

try:
    from config import SEVERITY_ORDER, SEVERITY_PRIORITY, TRIAGE_KEYWORDS
except ModuleNotFoundError:
    from backend.config import SEVERITY_ORDER, SEVERITY_PRIORITY, TRIAGE_KEYWORDS

# Transliterated Hindi/Urdu signal words (Hinglish)
# These handle mixed-language inputs where Hindi is typed
# phonetically in Latin script. The primary multilingual path
# now uses offline neural translation; these keywords remain a
# safety fallback for translation failures and mixed-language text.
HINGLISH_CRITICAL_SIGNALS: dict[str, tuple[str, str, str]] = {
    "mujhe chest mein pain hai": ("cardiac", "critical", "ALS"),
    "mujhe chest mei pain hai": ("cardiac", "critical", "ALS"),
    "chest mein pain": ("cardiac", "critical", "ALS"),
    "chest mei pain": ("cardiac", "critical", "ALS"),
    "chest me pain": ("cardiac", "critical", "ALS"),
    "seene mein dard": ("cardiac", "critical", "ALS"),
    "chati mein dard": ("cardiac", "critical", "ALS"),
    "chhati mein dard": ("cardiac", "critical", "ALS"),
    "seena dard": ("cardiac", "critical", "ALS"),
    "sans nahi": ("respiratory", "critical", "ALS"),
    "hosh nahi": ("other", "critical", "ALS"),
    "behosh": ("other", "critical", "ALS"),
    "dil ka dora": ("cardiac", "critical", "ALS"),
    "nab nahi": ("cardiac", "critical", "ALS"),
}

HINGLISH_HIGH_SIGNALS: dict[str, tuple[str, str, str]] = {
    "sar mein chot": ("trauma", "high", "ALS"),
    "khoon": ("trauma", "high", "ALS"),
    "chakkar": ("other", "high", "BLS"),
    "dard": ("other", "high", "BLS"),
    "tez bukhaar": ("other", "high", "BLS"),
}


def bump_severity(severity: str) -> str:
    """Increase a severity label by one level without exceeding critical."""

    index = min(SEVERITY_ORDER.index(severity) + 1, len(SEVERITY_ORDER) - 1)
    return SEVERITY_ORDER[index]


def _match_hinglish_signal(complaint: str) -> tuple[str, str, str] | None:
    for signal_map in (HINGLISH_CRITICAL_SIGNALS, HINGLISH_HIGH_SIGNALS):
        for phrase, outcome in signal_map.items():
            if phrase in complaint:
                return outcome
    return None


def classify_severity(chief_complaint: str, sos_mode: bool) -> dict[str, str | float]:
    """Classify severity, incident type, and ambulance requirement from complaint text."""

    complaint = chief_complaint.lower()
    incident_type = "other"
    severity = "medium"
    required_ambulance_type = "BLS"

    hinglish_match = _match_hinglish_signal(complaint)
    if hinglish_match is not None:
        incident_type, severity, required_ambulance_type = hinglish_match
    elif any(keyword in complaint for keyword in TRIAGE_KEYWORDS["cardiac"]):
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
