"""ASGI entry point for `uvicorn app.main:app`.

The production code still lives in `backend/` to preserve existing imports,
tests, and deployment flow. This module provides the requested `app.main`
entry point without moving or deleting the current backend.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from main import app, create_app  # type: ignore  # noqa: E402,F401
