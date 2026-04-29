"""Standard API response envelopes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class APIResponse(BaseModel):
    status: str
    data: Any = None
    message: str = ""


def success(data: Any = None, message: str = "OK") -> dict[str, Any]:
    return {"status": "success", "data": data, "message": message}


def error(message: str, data: Any = None) -> dict[str, Any]:
    return {"status": "error", "data": data, "message": message}


def fallback(data: Any = None, message: str = "Fallback mode") -> dict[str, Any]:
    return {"status": "fallback", "data": data, "message": message}


def unwrap_envelope(payload: Any) -> tuple[Any, str | None, str | None]:
    """Return the inner payload from the project's response envelope shape."""

    if isinstance(payload, dict) and {"status", "message", "data"} <= payload.keys():
        return payload.get("data"), payload.get("status"), payload.get("message")
    return payload, None, None
