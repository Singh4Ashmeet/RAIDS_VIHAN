"""Offline language detection helpers for triage safety checks."""

from __future__ import annotations

import re
from typing import Any

from langdetect import DetectorFactory, detect_langs
from langdetect.lang_detect_exception import LangDetectException

DetectorFactory.seed = 0

SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "kn": "Kannada",
    "mr": "Marathi",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "ml": "Malayalam",
    "ur": "Urdu",
}

HINGLISH_HINTS: tuple[str, ...] = (
    "seene mein",
    "seene mein dard",
    "chest mein pain",
    "chest mei pain",
    "chest me pain",
    "mujhe chest",
    "chati mein dard",
    "chhati mein dard",
    "seena dard",
    "dard ho raha",
    "bahut dard",
    "sans lene mein takleef",
    "sans nahi",
    "hosh nahi",
    "behosh",
    "dil ka dora",
    "nab nahi",
    "sar mein chot",
    "khoon",
    "chakkar",
    "tez bukhaar",
    "tez bukhar",
)


def _unknown_result(reason: str) -> dict[str, Any]:
    return {
        "language_code": "unknown",
        "language_name": "Unknown",
        "confidence": 0.0,
        "is_english": False,
        "is_indian_language": False,
        "detection_reliable": False,
        "all_detected": [],
        "reason": reason,
    }


def detect_language(text: str) -> dict[str, Any]:
    """Detect the dominant complaint language and return normalized metadata."""

    normalized = text.strip()
    if len(normalized) < 3:
        return _unknown_result("Text too short for reliable detection")

    if re.match(r"^[\d\s\W]+$", normalized):
        return _unknown_result("No alphabetic content")

    lowered = normalized.lower()
    if any(token in lowered for token in HINGLISH_HINTS):
        return {
            "language_code": "hi",
            "language_name": SUPPORTED_LANGUAGES["hi"],
            "confidence": 0.85,
            "is_english": False,
            "is_indian_language": True,
            "detection_reliable": True,
            "all_detected": [{"code": "hi", "prob": 0.85}],
        }

    try:
        results = detect_langs(normalized)
        if not results:
            return _unknown_result("Detection failed")

        top_result = results[0]
        top_prob = round(float(top_result.prob), 3)
        all_detected = [
            {
                "code": str(candidate.lang),
                "prob": round(float(candidate.prob), 3),
            }
            for candidate in results
        ]

        if top_prob < 0.70:
            return {
                **_unknown_result("Detection confidence below threshold"),
                "confidence": top_prob,
                "all_detected": all_detected,
            }

        language_code = str(top_result.lang)
        language_name = SUPPORTED_LANGUAGES.get(language_code, "Unknown")
        return {
            "language_code": language_code,
            "language_name": language_name,
            "confidence": top_prob,
            "is_english": language_code == "en",
            "is_indian_language": language_code in SUPPORTED_LANGUAGES and language_code != "en",
            "detection_reliable": True,
            "all_detected": all_detected,
        }
    except LangDetectException:
        return _unknown_result("Detection failed")


def get_language_review_message(detection: dict[str, Any]) -> str | None:
    """Return a dispatcher-facing review hint when language safety review is needed."""

    if detection.get("is_english") and detection.get("detection_reliable"):
        return None

    if not detection.get("detection_reliable"):
        return (
            "Language could not be reliably detected. "
            "Please verify complaint text and triage manually."
        )

    language_name = str(detection.get("language_name") or "Unknown language")
    if detection.get("is_indian_language"):
        return (
            f"Complaint appears to be in {language_name}. "
            "Automatic classification is English-only. "
            "Manual triage recommended."
        )

    return (
        f"Complaint appears to be in {language_name}. "
        "Automatic classification is English-only. "
        "Manual triage recommended."
    )
