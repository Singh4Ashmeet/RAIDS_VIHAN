"""Root test fixtures for RAID Nexus production-hardening checks."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("RAID_DISABLE_SIMULATION", "1")
os.environ.setdefault("RAID_LIGHTWEIGHT_TRIAGE", "1")
os.environ.setdefault("ENABLE_NLP_TRIAGE", "false")
os.environ.setdefault("ENABLE_TRANSLATION", "false")
os.environ.setdefault("USE_LLM", "false")
os.environ.setdefault("RAID_FORCE_SQLITE", "1")


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Return a FastAPI TestClient backed by an isolated SQLite database."""

    db_path = tmp_path / "raid_nexus.db"
    training_path = tmp_path / "training_data.csv"
    monkeypatch.setenv("RAID_NEXUS_DB_PATH", str(db_path))
    monkeypatch.setenv("RAID_NEXUS_TRAINING_DATA_PATH", str(training_path))
    monkeypatch.setenv("RAID_FORCE_SQLITE", "1")
    monkeypatch.setenv("RAID_DISABLE_SIMULATION", "1")
    monkeypatch.setenv("RAID_LIGHTWEIGHT_TRIAGE", "1")
    monkeypatch.setenv("ENABLE_NLP_TRIAGE", "false")
    monkeypatch.setenv("ENABLE_TRANSLATION", "false")
    monkeypatch.setenv("USE_LLM", "false")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_URL", raising=False)

    from core.security import limiter
    from main import create_app
    from fastapi.testclient import TestClient

    limiter._storage.reset()
    with TestClient(create_app()) as test_client:
        yield test_client
