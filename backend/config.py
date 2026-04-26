"""Application configuration and runtime constants for RAID Nexus."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Final
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
DEFAULT_DB_PATH = ROOT_DIR / "raid_nexus.db"
DB_PATH_ENV_VAR = "RAID_NEXUS_DB_PATH"
TRAINING_DATA_PATH_ENV_VAR = "RAID_NEXUS_TRAINING_DATA_PATH"

ENV_FILE = ROOT_DIR / ".env"
_ENV_EXISTS = ENV_FILE.is_file()
if _ENV_EXISTS:
    load_dotenv(ENV_FILE)

_DEV_AUTH_DEFAULTS: Final[dict[str, str]] = {
    "SECRET_KEY": "change-this-to-a-random-64-char-string-in-production",
    "ACCESS_TOKEN_EXPIRE_MINUTES": "480",
    "ALGORITHM": "HS256",
    "ADMIN_USERNAME": "admin",
    "ADMIN_PASSWORD": "admin123",
    "USER_USERNAME": "user",
    "USER_PASSWORD": "user123",
}

if not _ENV_EXISTS and any(os.getenv(key) is None for key in _DEV_AUTH_DEFAULTS):
    print("WARNING: Using default credentials. Set environment variables for production.")


def _auth_setting(name: str, *, required: bool = False) -> str:
    value = os.getenv(name)
    if value is None and not _ENV_EXISTS:
        value = _DEV_AUTH_DEFAULTS.get(name)
    if required and not value:
        raise ValueError(f"{name} must be set in backend/.env or environment variables.")
    return str(value or _DEV_AUTH_DEFAULTS.get(name, ""))


SECRET_KEY: Final[str] = _auth_setting("SECRET_KEY", required=True)
ALGORITHM: Final[str] = _auth_setting("ALGORITHM") or "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: Final[int] = int(_auth_setting("ACCESS_TOKEN_EXPIRE_MINUTES") or "480")
ADMIN_USERNAME: Final[str] = _auth_setting("ADMIN_USERNAME") or "admin"
ADMIN_PASSWORD: Final[str] = _auth_setting("ADMIN_PASSWORD") or "admin123"
USER_USERNAME: Final[str] = _auth_setting("USER_USERNAME") or "user"
USER_PASSWORD: Final[str] = _auth_setting("USER_PASSWORD") or "user123"

UTC = timezone.utc
KOLKATA_TZ = ZoneInfo("Asia/Kolkata")

CITY_CENTERS: Final[dict[str, tuple[float, float]]] = {
    "Delhi": (28.6139, 77.2090),
    "Mumbai": (19.0760, 72.8777),
    "Bengaluru": (12.9716, 77.5946),
    "Chennai": (13.0827, 80.2707),
    "Hyderabad": (17.3850, 78.4867),
}

CITY_BOUNDS: Final[dict[str, dict[str, float]]] = {
    city: {
        "lat_min": lat - 0.2,
        "lat_max": lat + 0.2,
        "lng_min": lng - 0.2,
        "lng_max": lng + 0.2,
    }
    for city, (lat, lng) in CITY_CENTERS.items()
}

CITY_TO_CODE: Final[dict[str, int]] = {
    "Delhi": 0,
    "Mumbai": 1,
    "Bengaluru": 2,
    "Chennai": 3,
    "Hyderabad": 4,
}

SEVERITY_ORDER: Final[list[str]] = ["low", "medium", "high", "critical"]
SEVERITY_PRIORITY: Final[dict[str, float]] = {
    "critical": 1.0,
    "high": 0.8,
    "medium": 0.5,
    "low": 0.3,
}

TRIAGE_KEYWORDS: Final[dict[str, tuple[str, ...]]] = {
    "cardiac": ("heart", "chest pain", "cardiac", "heart attack", "palpitation"),
    "trauma": ("accident", "fracture", "bleeding", "injury", "fall"),
    "respiratory": ("breathing", "asthma", "oxygen", "choke", "suffocate"),
}

INCIDENT_EQUIPMENT_REQUIREMENTS: Final[dict[str, list[str]]] = {
    "cardiac": ["defibrillator", "ALS_kit"],
    "trauma": ["trauma_kit", "oxygen"],
    "respiratory": ["oxygen", "nebulizer"],
    "accident": ["trauma_kit", "stretcher"],
    "other": [],
}

INCIDENT_SPECIALTY_REQUIREMENTS: Final[dict[str, tuple[str, ...]]] = {
    "cardiac": ("cardiac", "multi-specialty"),
    "trauma": ("trauma",),
}

TRAFFIC_STATE: dict[str, dict[str, datetime | float | None]] = {
    city: {"multiplier": 1.0, "expires_at": None}
    for city in CITY_CENTERS
}

SIMULATION_TICK_SECONDS = 2
AMBULANCE_STEP_MIN = 0.10
AMBULANCE_STEP_MAX = 0.15
SCENE_HOLD_TICKS = 1
HOSPITAL_HOLD_TICKS = 2
AUTO_BREAKDOWN_TICKS = 5
INCIDENT_GENERATION_INTERVAL = 30
AUTO_BREAKDOWN_INTERVAL = 20
HOSPITAL_OCCUPANCY_MIN = 40.0
HOSPITAL_OCCUPANCY_MAX = 95.0
ER_WAIT_MIN = 5
ER_WAIT_MAX = 60
CITY_AMBULANCE_BASE_SPEED_KMH = 40.0

ANALYTICS_OVERLOAD_THRESHOLD = 90.0


def get_db_path() -> Path:
    """Return the active SQLite database path, honoring test/runtime overrides."""

    return Path(os.getenv(DB_PATH_ENV_VAR, str(DEFAULT_DB_PATH))).expanduser()


def utc_now() -> datetime:
    """Return the current UTC timestamp."""

    return datetime.now(tz=UTC)


def isoformat_utc(value: datetime | None = None) -> str:
    """Convert a datetime into an ISO 8601 UTC string."""

    current = value or utc_now()
    return current.astimezone(UTC).isoformat()
