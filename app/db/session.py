"""Compatibility wrapper exposing the active backend database session."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import AsyncSessionLocal, engine, get_db  # type: ignore  # noqa: E402,F401

SessionLocal = AsyncSessionLocal
