"""Offline multilingual translation helpers built on Helsinki-NLP Opus-MT models."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

LANGUAGE_MODEL_MAP: dict[str, str] = {
    "hi": "Helsinki-NLP/opus-mt-hi-en",
    "bn": "Helsinki-NLP/opus-mt-bn-en",
    "ur": "Helsinki-NLP/opus-mt-ur-en",
    "mr": "Helsinki-NLP/opus-mt-mr-en",
    "ta": "Helsinki-NLP/opus-mt-dra-en",
    "te": "Helsinki-NLP/opus-mt-dra-en",
    "kn": "Helsinki-NLP/opus-mt-dra-en",
    "gu": "Helsinki-NLP/opus-mt-mul-en",
    "pa": "Helsinki-NLP/opus-mt-mul-en",
    "ml": "Helsinki-NLP/opus-mt-mul-en",
}

SUPPORTED_TRANSLATION_LANGUAGES = {"en", *LANGUAGE_MODEL_MAP.keys()}

_translation_pipelines: dict[str, Any] = {}
_pipeline_lock: asyncio.Lock | None = None
HINGLISH_GLOSSARY: tuple[tuple[str, str], ...] = (
    ("mujhe chest mein pain hai", "chest pain"),
    ("mujhe chest mei pain hai", "chest pain"),
    ("mujhe chest me pain hai", "chest pain"),
    ("chest mein pain", "chest pain"),
    ("chest mei pain", "chest pain"),
    ("chest me pain", "chest pain"),
    ("sans lene mein takleef hai", "difficulty breathing"),
    ("sans lene mein takleef", "difficulty breathing"),
    ("sans nahi", "not breathing"),
    ("seene mein bahut dard", "severe chest pain"),
    ("seene mein dard", "chest pain"),
    ("chati mein dard", "chest pain"),
    ("chhati mein dard", "chest pain"),
    ("seena dard", "chest pain"),
    ("bahut dard", "severe pain"),
    ("dil ka dora", "heart attack"),
    ("hosh nahi", "unconscious"),
    ("behosh", "unconscious"),
    ("takleef hai", "distress"),
    ("ho raha hai", ""),
    (" aur ", " and "),
)


def _get_lock() -> asyncio.Lock:
    """Return a lazily initialized asyncio lock for translation model loading."""

    global _pipeline_lock
    if _pipeline_lock is None:
        _pipeline_lock = asyncio.Lock()
    return _pipeline_lock


def _load_translation_pipeline(model_name: str):
    """Load and cache a translation pipeline for the requested model."""

    if model_name in _translation_pipelines:
        return _translation_pipelines[model_name]

    logger.info("Loading translation model: %s (first use - downloading if needed)", model_name)
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    translator = {
        "tokenizer": tokenizer,
        "model": model,
    }
    _translation_pipelines[model_name] = translator
    logger.info("Translation model loaded: %s", model_name)
    return translator


def _translate_sync(text: str, model_name: str) -> str:
    """Translate text to English with the requested offline model."""

    try:
        translator = _load_translation_pipeline(model_name)
        tokenizer = translator["tokenizer"]
        model = translator["model"]
        inputs = tokenizer(text, return_tensors="pt", truncation=True)
        output = model.generate(**inputs, max_length=512)
        return str(tokenizer.decode(output[0], skip_special_tokens=True))
    except Exception as exc:
        logger.warning("Offline translation failed for %s: %s", model_name, exc)
        return text


def _translate_hinglish_phrase(text: str) -> str | None:
    normalized = text.strip().lower()
    if not normalized or not normalized.isascii():
        return None

    translated = normalized
    changed = False
    for source, target in HINGLISH_GLOSSARY:
        if source in translated:
            translated = translated.replace(source, target)
            changed = True

    translated = re.sub(r"\s+", " ", translated).strip(" ,.")
    if not changed or not translated:
        return None
    return translated


async def translate_to_english(text: str, language_code: str) -> dict[str, Any]:
    """Translate supported complaint text to English using offline models."""

    if language_code == "en":
        return {
            "translated_text": text,
            "original_text": text,
            "was_translated": False,
            "model_used": None,
            "language_code": "en",
        }

    model_name = LANGUAGE_MODEL_MAP.get(language_code)
    if model_name is None:
        return {
            "translated_text": text,
            "original_text": text,
            "was_translated": False,
            "model_used": None,
            "language_code": language_code,
            "translation_note": (
                "Offline translation is not configured for this language. "
                "Manual triage required for this language."
            ),
        }

    if language_code == "hi":
        hinglish_translation = _translate_hinglish_phrase(text)
        if hinglish_translation:
            return {
                "translated_text": hinglish_translation,
                "original_text": text,
                "was_translated": True,
                "model_used": f"{model_name} + hinglish_glossary",
                "language_code": language_code,
                "translation_note": (
                    "Offline emergency glossary plus Helsinki-NLP Opus-MT fallback. "
                    "Quality may vary for colloquial Hinglish text."
                ),
            }

    async with _get_lock():
        translated = await asyncio.to_thread(_translate_sync, text, model_name)

    was_translated = translated.strip() != text.strip()
    payload: dict[str, Any] = {
        "translated_text": translated,
        "original_text": text,
        "was_translated": was_translated,
        "model_used": model_name,
        "language_code": language_code,
    }
    if was_translated:
        payload["translation_note"] = (
            "Offline neural translation via Helsinki-NLP Opus-MT. "
            "Quality may vary for emergency domain text."
        )
    else:
        payload["translation_note"] = "Translation failed - original text returned."
    return payload


async def get_translation_status() -> dict[str, Any]:
    """Return the currently loaded translation-model status."""

    return {
        "loaded_models": list(_translation_pipelines.keys()),
        "model_count": len(_translation_pipelines),
        "supported_languages": sorted(SUPPORTED_TRANSLATION_LANGUAGES),
        "unsupported_language_behavior": "manual_review_no_translation",
        "universal_fallback": "Helsinki-NLP/opus-mt-mul-en",
    }
