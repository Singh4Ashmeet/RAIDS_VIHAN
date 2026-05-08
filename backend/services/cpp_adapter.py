"""Optional adapter for the C++ dispatch optimizer scaffold."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def _binary_path() -> str | None:
    """Return the optional optimizer binary path if it is available."""

    for name in ("raid_optimizer", "dispatch_optimizer"):
        binary = shutil.which(name)
        if binary:
            return binary

    repo_root = Path(__file__).resolve().parents[2]
    candidates = [
        repo_root / "optimizer_cpp" / "build" / "raid_optimizer",
        repo_root / "optimizer_cpp" / "build" / "raid_optimizer.exe",
        repo_root / "optimizer_cpp" / "build" / "dispatch_optimizer",
        repo_root / "optimizer_cpp" / "build" / "dispatch_optimizer.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def _python_greedy(incident: dict[str, Any], ambulances: list[dict[str, Any]]) -> dict[str, Any]:
    """Fallback assignment when the compiled optimizer is unavailable."""

    from services.dispatch_engine import ETAPredictionService

    service = ETAPredictionService()
    available = [ambulance for ambulance in ambulances if ambulance.get("status") == "available"]
    if not available:
        return {"status": "error", "message": "No available ambulances", "assignment": None}
    selected = min(available, key=lambda ambulance: service.predict_eta(incident, ambulance))
    return {
        "status": "success",
        "message": "Python greedy fallback selected assignment",
        "assignment": {
            "ambulance_id": selected.get("id"),
            "incident_id": incident.get("id"),
            "eta_minutes": service.predict_eta(incident, selected),
            "optimizer": "python_greedy",
        },
    }


def optimize_dispatch(incident: dict[str, Any], ambulances: list[dict[str, Any]]) -> dict[str, Any]:
    """Use the optional C++ optimizer, falling back to Python greedy logic."""

    binary = _binary_path()
    if not binary:
        return _python_greedy(incident, ambulances)

    payload = {"incident": incident, "ambulances": ambulances}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True)
        input_path = Path(handle.name)

    try:
        completed = subprocess.run(
            [binary, str(input_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if completed.returncode != 0:
            return _python_greedy(incident, ambulances)
        return json.loads(completed.stdout)
    except Exception:
        return _python_greedy(incident, ambulances)
    finally:
        try:
            input_path.unlink()
        except OSError:
            pass
