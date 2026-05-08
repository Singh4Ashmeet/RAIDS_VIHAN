import logging
import os

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = settings.OLLAMA_URL or settings.OLLAMA_BASE_URL
OLLAMA_URL = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
MODEL = "mistral"
USE_LLM = settings.USE_LLM or os.getenv("USE_LLM", "").lower() in {"1", "true", "yes"}
ENABLE_OLLAMA = USE_LLM and os.getenv("RAID_NEXUS_ENABLE_OLLAMA", "").lower() in {"1", "true", "yes"}
TIMEOUT_SECONDS = 0.75


async def generate_explanation(
    incident: dict,
    patient: dict | None,
    ambulance_id: str,
    hospital_id: str,
    eta_minutes: float,
    ambulance_score: float,
    hospital_score: float,
    final_score: float,
    rejected_hospitals: list,
) -> str:

    rejected_summary = ""
    if rejected_hospitals:
        top_reject = rejected_hospitals[0]
        rejected_summary = (
            f"Closest alternative was {top_reject.get('id')} "
            f"(score {top_reject.get('score', 0):.0%}) - "
            f"rejected: {top_reject.get('reason', 'lower suitability')}."
        )

    complaint = (patient or {}).get("chief_complaint") or incident.get("description", "")
    age_note = f"Patient age: {patient['age']}. " if patient else ""

    prompt = f"""You are an AI dispatch system. Write one clear paragraph (3-4 sentences)
explaining this emergency dispatch decision to a dispatcher.
Be specific. Use the exact unit IDs and hospital names provided.

Incident: {incident.get('type', 'emergency')} - {complaint}
{age_note}Severity: {incident.get('severity', 'high')}
Dispatched: Ambulance {ambulance_id} - ETA {eta_minutes:.1f} min - score {ambulance_score:.0%}
Hospital: {hospital_id} - combined score {hospital_score:.0%}
Final dispatch score: {final_score:.0%}
{rejected_summary}

Write only the explanation paragraph. No headers. No bullet points."""

    fallback_text = (
        f"Selected ambulance {ambulance_id} for {incident.get('type', 'emergency')} "
        f"incident based on response ETA ({eta_minutes:.1f} min), equipment match, "
        f"and crew readiness score {ambulance_score:.0%}. "
        f"Destination {hospital_id} selected with hospital suitability score {hospital_score:.0%}. "
        f"Combined dispatch confidence: {final_score:.0%}. "
        + (rejected_summary if rejected_summary else "No viable alternatives available.")
    )

    if not USE_LLM or not ENABLE_OLLAMA:
        return fallback_text

    try:
        timeout = httpx.Timeout(TIMEOUT_SECONDS, connect=0.25)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.post(
                OLLAMA_URL,
                json={
                    "model": MODEL,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()
            text = data.get("response", "").strip()
            if text and len(text) > 20:
                return text
    except Exception as exc:
        logger.warning("Ollama unavailable; using rule-based explanation: %s", exc)

    return fallback_text
