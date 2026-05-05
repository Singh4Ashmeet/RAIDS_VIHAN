"""Canonical API response envelope helpers."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class ApiResponse(BaseModel):
    status: str
    message: str
    data: Optional[Any] = None


APIResponse = ApiResponse


def success(data: Any = None, message: str = "OK") -> dict[str, Any]:
    return {"status": "success", "message": message, "data": data}


def fallback(data: Any = None, message: str = "Fallback mode") -> dict[str, Any]:
    return {"status": "fallback", "message": message, "data": data}


def error(message: str, code: int = 500, data: Any = None) -> dict[str, Any]:
    _ = (code, data)
    return {"status": "error", "message": message, "data": None}


def unwrap_envelope(payload: Any) -> tuple[Any, str | None, str | None]:
    """Return the inner payload from the project's response envelope shape."""

    if isinstance(payload, dict) and {"status", "message", "data"} <= payload.keys():
        return payload.get("data"), payload.get("status"), payload.get("message")
    return payload, None, None


__all__ = ["ApiResponse", "APIResponse", "success", "fallback", "error", "unwrap_envelope"]
