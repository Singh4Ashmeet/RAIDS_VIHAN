"""Compatibility shim for standardized response helpers."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from core.responses import APIResponse, fallback, success, unwrap_envelope


def error(message: str, code: int = 400, data: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content={"status": "error", "message": message, "data": data},
    )


__all__ = ["APIResponse", "success", "fallback", "error", "unwrap_envelope"]
