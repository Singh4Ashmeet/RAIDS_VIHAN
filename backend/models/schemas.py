"""Shared Pydantic schema entry point.

Route modules still own their narrow request models where that preserves existing
imports and avoids churn. New backend code should prefer adding reusable request
and response schemas here.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class APIEnvelope(BaseModel):
    status: str
    data: Any = None
    message: str = ""
