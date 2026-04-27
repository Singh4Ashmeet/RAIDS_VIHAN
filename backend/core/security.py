"""Shared security helpers for rate limiting and input validation."""

from __future__ import annotations

import html
import re

from fastapi import HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address

# Rate limiting uses in-memory storage in the prototype.
# Production should use Redis-backed storage so limits survive restarts
# and work across multiple server processes.
limiter = Limiter(key_func=get_remote_address)

INDIA_LAT_MIN = 8.0
INDIA_LAT_MAX = 37.1
INDIA_LNG_MIN = 68.0
INDIA_LNG_MAX = 97.5

VALID_INCIDENT_TYPES = {"cardiac", "trauma", "respiratory", "stroke", "accident", "other"}
VALID_SEVERITIES = {"critical", "high", "medium", "low"}

_TAG_RE = re.compile(r"<[^>]+>")


def validate_india_coordinates(lat: float, lng: float) -> None:
    """Require coordinates to fall within India's broad bounding box."""

    if not (INDIA_LAT_MIN <= float(lat) <= INDIA_LAT_MAX and INDIA_LNG_MIN <= float(lng) <= INDIA_LNG_MAX):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid coordinates — coordinates must be within India",
        )


def sanitize_text_field(value: str | None, *, max_length: int) -> str:
    """Normalize, strip tags, unescape entities, and cap text length."""

    normalized = html.unescape(_TAG_RE.sub("", str(value or "")).strip())
    normalized = normalized[:max_length].strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a description of the emergency",
        )
    return normalized


def validate_incident_type(value: str) -> str:
    """Validate and normalize the incident type string."""

    normalized = str(value).strip().lower()
    if normalized not in VALID_INCIDENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid incident type",
        )
    return normalized


def validate_severity(value: str) -> str:
    """Validate and normalize the severity string."""

    normalized = str(value).strip().lower()
    if normalized not in VALID_SEVERITIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid severity",
        )
    return normalized
