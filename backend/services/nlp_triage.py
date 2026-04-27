"""NLP-based emergency triage using a local zero-shot language model."""

from __future__ import annotations

import asyncio
import logging
import os
from threading import Lock
from typing import Any

try:
    from services.language_detector import detect_language, get_language_review_message
except ModuleNotFoundError:
    from backend.services.language_detector import detect_language, get_language_review_message

try:
    from services.offline_translator import translate_to_english
except ModuleNotFoundError:
    from backend.services.offline_translator import translate_to_english

logger = logging.getLogger(__name__)

LIGHTWEIGHT_TRIAGE = os.getenv("RAID_LIGHTWEIGHT_TRIAGE", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
MODEL_NAME = "facebook/bart-large-mnli"
TRIAGE_VERSION = "nlp_v1"
LOW_TYPE_CONFIDENCE = 0.55
LOW_SEVERITY_CONFIDENCE = 0.60

CANDIDATE_LABELS = [
    "cardiac emergency",
    "trauma or physical injury",
    "respiratory distress",
    "stroke or neurological emergency",
    "road traffic accident",
    "general medical emergency",
]

LABEL_TO_TYPE = {
    "cardiac emergency": "cardiac",
    "trauma or physical injury": "trauma",
    "respiratory distress": "respiratory",
    "stroke or neurological emergency": "stroke",
    "road traffic accident": "accident",
    "general medical emergency": "other",
}

CRITICAL_SIGNALS = [
    "unconscious",
    "not breathing",
    "cardiac arrest",
    "no pulse",
    "unresponsive",
    "severe bleeding",
    "stroke",
    "anaphylaxis",
    "choking",
    "drowning",
]

HIGH_SIGNALS = [
    "chest pain",
    "difficulty breathing",
    "head injury",
    "heavy bleeding",
    "severe pain",
    "seizure",
    "diabetic",
]

LOW_SIGNALS = [
    "minor",
    "small cut",
    "mild",
    "stable",
    "not serious",
    "sprain",
    "bruise",
]

SEVERITY_LABELS = [
    "life threatening emergency",
    "urgent medical attention needed",
    "non-urgent medical care needed",
]

SEVERITY_MAP = {
    "life threatening emergency": "critical",
    "urgent medical attention needed": "high",
    "non-urgent medical care needed": "medium",
}

SEVERITY_ORDER = ["low", "medium", "high", "critical"]

_classifier = None
_classifier_lock = Lock()


def _get_classifier():
    """Return the cached zero-shot classifier, loading it lazily on first use."""

    global _classifier
    if _classifier is None:
        with _classifier_lock:
            if _classifier is None:
                logger.info("Loading NLP triage model...")
                from transformers import pipeline

                _classifier = pipeline(
                    "zero-shot-classification",
                    model=MODEL_NAME,
                    device=-1,
                )
    return _classifier


def _rounded_scores(result: dict[str, Any]) -> dict[str, float]:
    return {
        str(label): round(float(score), 4)
        for label, score in zip(result.get("labels", []), result.get("scores", []), strict=False)
    }


def _load_keyword_classifier():
    try:
        from services.triage_service import classify_severity as keyword_classify_severity
    except ModuleNotFoundError:
        from backend.services.triage_service import classify_severity as keyword_classify_severity

    return keyword_classify_severity


def classify_incident_type(complaint: str) -> dict[str, Any]:
    """Classify the broad incident type from raw complaint text."""

    result = _get_classifier()(complaint, CANDIDATE_LABELS, multi_label=False)
    top_label = str(result["labels"][0])
    confidence = round(float(result["scores"][0]), 4)
    return {
        "incident_type": LABEL_TO_TYPE.get(top_label, "other"),
        "confidence": confidence,
        "all_scores": _rounded_scores(result),
        "requires_human_review": confidence < LOW_TYPE_CONFIDENCE,
        "method": "nlp_zero_shot",
    }


def _find_signal(complaint: str, signals: list[str]) -> str | None:
    normalized = complaint.lower()
    for signal in signals:
        if signal in normalized:
            return signal
    return None


def classify_severity(complaint: str, incident_type: str) -> dict[str, Any]:
    """Classify emergency severity using signal detection plus zero-shot fallback."""

    _ = incident_type
    critical_signal = _find_signal(complaint, CRITICAL_SIGNALS)
    if critical_signal:
        return {
            "severity": "critical",
            "confidence": 0.95,
            "signal_detected": critical_signal,
            "requires_human_review": False,
            "method": "signal_detected",
        }

    high_signal = _find_signal(complaint, HIGH_SIGNALS)
    if high_signal:
        return {
            "severity": "high",
            "confidence": 0.85,
            "signal_detected": high_signal,
            "requires_human_review": False,
            "method": "signal_detected",
        }

    low_signal = _find_signal(complaint, LOW_SIGNALS)
    if low_signal:
        return {
            "severity": "medium",
            "confidence": 0.80,
            "signal_detected": low_signal,
            "requires_human_review": False,
            "method": "signal_detected",
        }

    result = _get_classifier()(complaint, SEVERITY_LABELS, multi_label=False)
    top_label = str(result["labels"][0])
    confidence = round(float(result["scores"][0]), 4)
    return {
        "severity": SEVERITY_MAP.get(top_label, "medium"),
        "confidence": confidence,
        "signal_detected": None,
        "requires_human_review": confidence < LOW_SEVERITY_CONFIDENCE,
        "method": "nlp_zero_shot",
    }


def _bump_severity(severity: str) -> str:
    index = SEVERITY_ORDER.index(severity) if severity in SEVERITY_ORDER else 1
    return SEVERITY_ORDER[min(index + 1, len(SEVERITY_ORDER) - 1)]


def get_resource_requirement(
    incident_type: str,
    severity: str,
    type_confidence: float,
    severity_confidence: float,
) -> dict[str, Any]:
    """Return the ambulance capability required for the triaged incident."""

    if type_confidence < LOW_TYPE_CONFIDENCE or severity_confidence < LOW_SEVERITY_CONFIDENCE:
        return {
            "ambulance_type_required": "ALS",
            "escalated_due_to_uncertainty": True,
            "escalation_reason": "Low classification confidence - defaulting to ALS for safety",
        }

    requires_als = (
        (incident_type in {"cardiac", "stroke"} and severity in {"critical", "high"})
        or (incident_type in {"trauma", "respiratory", "accident"} and severity == "critical")
    )
    return {
        "ambulance_type_required": "ALS" if requires_als else "BLS",
        "escalated_due_to_uncertainty": False,
        "escalation_reason": None,
    }


def _review_reason(type_result: dict[str, Any], severity_result: dict[str, Any]) -> str | None:
    if type_result.get("requires_human_review"):
        return (
            "Low confidence in incident type classification "
            f"({float(type_result.get('confidence', 0.0)):.2f}). Human review recommended before dispatch."
        )
    if severity_result.get("requires_human_review"):
        return (
            "Low confidence in severity classification "
            f"({float(severity_result.get('confidence', 0.0)):.2f}). Human review recommended before dispatch."
        )
    return None


def _combine_review_reasons(*reasons: str | None) -> str | None:
    merged = " ".join(reason.strip() for reason in reasons if reason and reason.strip())
    return merged or None


def _keyword_fallback_triage(
    complaint: str,
    sos_mode: bool,
    *,
    triage_version: str,
    requires_human_review: bool = False,
    review_reason: str | None = None,
    language_detection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    keyword_classify_severity = _load_keyword_classifier()
    keyword_result = keyword_classify_severity(complaint, sos_mode)
    incident_type = str(keyword_result["incident_type"])
    severity = str(keyword_result["severity"])
    ambulance_type = str(keyword_result["required_ambulance_type"])
    result: dict[str, Any] = {
        "incident_type": incident_type,
        "severity": severity,
        "ambulance_type_required": ambulance_type,
        "requires_human_review": requires_human_review,
        "review_reason": review_reason,
        "type_classification": {
            "incident_type": incident_type,
            "confidence": 1.0,
            "all_scores": {},
            "requires_human_review": requires_human_review,
            "method": "keyword_fallback",
        },
        "severity_classification": {
            "severity": severity,
            "confidence": 1.0,
            "signal_detected": None,
            "requires_human_review": requires_human_review,
            "method": "keyword_fallback",
        },
        "resource_requirement": {
            "ambulance_type_required": ambulance_type,
            "escalated_due_to_uncertainty": False,
            "escalation_reason": None,
        },
        "triage_version": triage_version,
        "triage_confidence": 1.0,
    }
    if language_detection is not None:
        result["language_detection"] = language_detection
    return result


async def _run_nlp_classification(
    complaint: str,
    city: str | None = None,
    sos_mode: bool = False,
) -> dict[str, Any]:
    """Run the normal English NLP triage path."""

    _ = city
    type_task = asyncio.to_thread(classify_incident_type, complaint)
    severity_task = asyncio.to_thread(classify_severity, complaint, "")
    type_result, severity_result = await asyncio.gather(type_task, severity_task)

    if sos_mode and severity_result["severity"] != "critical":
        severity_result = {
            **severity_result,
            "severity": _bump_severity(str(severity_result["severity"])),
            "confidence": max(float(severity_result["confidence"]), 0.90),
            "signal_detected": severity_result.get("signal_detected") or "sos_mode",
            "requires_human_review": False,
            "method": "signal_detected",
        }

    resource_result = get_resource_requirement(
        str(type_result["incident_type"]),
        str(severity_result["severity"]),
        float(type_result["confidence"]),
        float(severity_result["confidence"]),
    )
    requires_review = bool(type_result["requires_human_review"] or severity_result["requires_human_review"])
    review_reason = _review_reason(type_result, severity_result)
    return {
        "incident_type": type_result["incident_type"],
        "severity": severity_result["severity"],
        "ambulance_type_required": resource_result["ambulance_type_required"],
        "requires_human_review": requires_review,
        "review_reason": review_reason,
        "type_classification": type_result,
        "severity_classification": severity_result,
        "resource_requirement": resource_result,
        "triage_version": TRIAGE_VERSION,
        "triage_confidence": round(
            min(float(type_result["confidence"]), float(severity_result["confidence"])),
            4,
        ),
    }


async def triage_incident(complaint: str, city: str | None = None, sos_mode: bool = False) -> dict[str, Any]:
    """Run language-aware triage and return incident, severity, review, and resource metadata."""

    lang_result = detect_language(complaint)
    lang_review_msg = get_language_review_message(lang_result)

    try:
        if LIGHTWEIGHT_TRIAGE:
            fallback_result = _keyword_fallback_triage(
                complaint,
                sos_mode,
                triage_version="keyword_lightweight",
                requires_human_review=not bool(lang_result.get("is_english")),
                review_reason=(
                    _combine_review_reasons(
                        "Hosted lightweight triage mode is active. Manual review recommended for non-English reports.",
                        lang_review_msg,
                    )
                    if not bool(lang_result.get("is_english"))
                    else None
                ),
                language_detection=lang_result,
            )
            fallback_result["deployment_mode"] = "lightweight"
            return fallback_result

        if not lang_result["is_english"] and lang_result["detection_reliable"]:
            translation = await translate_to_english(
                complaint,
                str(lang_result["language_code"]),
            )

            if translation["was_translated"]:
                result = await _run_nlp_classification(
                    str(translation["translated_text"]),
                    city=city,
                    sos_mode=sos_mode,
                )
                result["requires_human_review"] = True
                result["review_reason"] = (
                    f"Complaint translated from {lang_result['language_name']} to English "
                    "(offline neural translation). Verify triage classification before dispatch."
                )
                result["language_detection"] = lang_result
                result["translation"] = {
                    "original_text": translation["original_text"],
                    "translated_text": translation["translated_text"],
                    "model_used": translation["model_used"],
                    "was_translated": True,
                }
                result["triage_version"] = "nlp_translated"
                return result

            translation_unavailable = translation.get("model_used") is None
            fallback_result = _keyword_fallback_triage(
                complaint,
                sos_mode,
                triage_version=(
                    "keyword_fallback_translation_unavailable"
                    if translation_unavailable
                    else "keyword_fallback_translation_failed"
                ),
                requires_human_review=True,
                review_reason=(
                    (
                        "Automatic translation is not configured for this language. "
                        f"{lang_result['language_name']} complaint requires manual triage."
                    )
                    if translation_unavailable
                    else f"Translation from {lang_result['language_name']} failed. Manual triage required."
                ),
                language_detection=lang_result,
            )
            fallback_result["translation"] = {
                "original_text": translation["original_text"],
                "translated_text": translation["translated_text"],
                "model_used": translation["model_used"],
                "was_translated": False,
            }
            return fallback_result

        result = await _run_nlp_classification(complaint, city=city, sos_mode=sos_mode)
        if not lang_result["detection_reliable"]:
            result["requires_human_review"] = True
            result["review_reason"] = _combine_review_reasons(result.get("review_reason"), lang_review_msg)
        result["language_detection"] = lang_result
        return result
    except Exception as exc:
        logger.error("NLP triage failed, falling back to keyword triage: %s", exc)
        fallback_result = _keyword_fallback_triage(
            complaint,
            sos_mode,
            triage_version="keyword_fallback",
            language_detection=lang_result,
        )
        if not lang_result["is_english"] or not lang_result["detection_reliable"]:
            fallback_result["requires_human_review"] = True
            fallback_result["review_reason"] = _combine_review_reasons(
                fallback_result.get("review_reason"),
                lang_review_msg,
            )
        return fallback_result
