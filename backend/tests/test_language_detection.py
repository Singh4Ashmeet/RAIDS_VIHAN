"""Focused tests for multilingual triage safety behavior."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from services.language_detector import detect_language
from services.nlp_triage import triage_incident
from services.triage_service import classify_severity


class LanguageDetectionTests(unittest.TestCase):
    """Verify language detection and safe fallback paths."""

    def test_short_text_returns_unknown(self) -> None:
        result = detect_language("..")
        self.assertEqual(result["language_code"], "unknown")
        self.assertFalse(result["detection_reliable"])
        self.assertEqual(result["reason"], "Text too short for reliable detection")

    def test_hinglish_phrase_detects_hindi(self) -> None:
        result = detect_language("seene mein dard hai")
        self.assertEqual(result["language_code"], "hi")
        self.assertEqual(result["language_name"], "Hindi")
        self.assertTrue(result["detection_reliable"])
        self.assertTrue(result["is_indian_language"])

    def test_keyword_fallback_handles_hinglish_critical_signal(self) -> None:
        result = classify_severity("patient ko seene mein dard hai", False)
        self.assertEqual(result["incident_type"], "cardiac")
        self.assertEqual(result["severity"], "critical")
        self.assertEqual(result["required_ambulance_type"], "ALS")

    def test_non_english_path_translates_and_forces_human_review(self) -> None:
        mocked_translation = AsyncMock(
            return_value={
                "translated_text": "severe chest pain",
                "original_text": "seene mein dard hai",
                "was_translated": True,
                "model_used": "Helsinki-NLP/opus-mt-hi-en",
                "language_code": "hi",
            }
        )
        with patch("services.nlp_triage.translate_to_english", mocked_translation):
            result = asyncio.run(triage_incident("seene mein dard hai"))
        self.assertEqual(result["triage_version"], "nlp_translated")
        self.assertTrue(result["requires_human_review"])
        self.assertEqual(result["language_detection"]["language_code"], "hi")
        self.assertEqual(result["translation"]["translated_text"], "severe chest pain")


if __name__ == "__main__":
    unittest.main()
