"""Shared pytest fixtures for backend tests."""

from __future__ import annotations

import os

import pytest


@pytest.fixture
def fresh_test_database(tmp_path, monkeypatch):
    """Point SQLite-mode tests at an isolated database file."""

    db_path = tmp_path / "raid_nexus.db"
    training_path = tmp_path / "training_data.csv"
    monkeypatch.setenv("RAID_NEXUS_DB_PATH", str(db_path))
    monkeypatch.setenv("RAID_NEXUS_TRAINING_DATA_PATH", str(training_path))
    monkeypatch.setenv("RAID_FORCE_SQLITE", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield db_path
    if db_path.exists():
        db_path.unlink()
    if training_path.exists():
        training_path.unlink()
    os.environ.pop("RAID_FORCE_SQLITE", None)
