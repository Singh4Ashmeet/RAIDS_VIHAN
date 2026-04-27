from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

def success(data, message="OK"):
    return {"status": "success", "message": message, "data": data}

def fallback(data, message):
    return {"status": "fallback", "message": message, "data": data}

def error(message, code=400):
    return JSONResponse(
        status_code=code,
        content={"status": "error", "message": message, "data": None}
    )


def unwrap_envelope(payload: Any) -> tuple[Any, str | None, str | None]:
    """Return the inner payload from the project's response envelope shape."""

    if isinstance(payload, dict) and {"status", "message", "data"} <= payload.keys():
        return payload.get("data"), payload.get("status"), payload.get("message")
    return payload, None, None
