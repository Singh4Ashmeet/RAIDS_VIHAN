"""Application configuration and runtime constants for RAID Nexus."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Final
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
DEFAULT_DB_PATH = ROOT_DIR / "raid_nexus.db"
DB_PATH_ENV_VAR = "RAID_NEXUS_DB_PATH"
DATABASE_URL_ENV_VAR = "DATABASE_URL"
POSTGRES_URL_ENV_VAR = "POSTGRES_URL"
TRAINING_DATA_PATH_ENV_VAR = "RAID_NEXUS_TRAINING_DATA_PATH"
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    """Environment-backed settings used by backend services."""

    DATABASE_URL: str = "sqlite:///./raid_nexus.db"
    POSTGRES_URL: str = ""
    ENVIRONMENT: str = "development"

    SECRET_KEY: str = "dev-secret-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    USER_USERNAME: str = "user"
    USER_PASSWORD: str = "user123"

    TOMTOM_API_KEY: str = ""
    OSRM_URL: str = "http://router.project-osrm.org"

    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 3000
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://raid-nexus.onrender.com",
    ]
    CORS_ORIGIN_REGEX: str = r"^http://(localhost|127\.0\.0\.1):\d+$"

    ENABLE_NLP_TRIAGE: bool = True
    ENABLE_TRANSLATION: bool = True
    ENABLE_ANOMALY_DETECTION: bool = True

    RAID_NEXUS_DB_PATH: str = str(DEFAULT_DB_PATH)
    RAID_NEXUS_TRAINING_DATA_PATH: str = ""
    RAID_FORCE_SQLITE: bool = False
    RAID_DISABLE_SIMULATION: bool = False
    RAID_LIGHTWEIGHT_TRIAGE: bool = False

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

SECRET_KEY: Final[str] = settings.SECRET_KEY
ALGORITHM: Final[str] = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES: Final[int] = settings.ACCESS_TOKEN_EXPIRE_MINUTES
ADMIN_USERNAME: Final[str] = settings.ADMIN_USERNAME
ADMIN_PASSWORD: Final[str] = settings.ADMIN_PASSWORD
USER_USERNAME: Final[str] = settings.USER_USERNAME
USER_PASSWORD: Final[str] = settings.USER_PASSWORD

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

    return Path(os.getenv(DB_PATH_ENV_VAR, settings.RAID_NEXUS_DB_PATH or str(DEFAULT_DB_PATH))).expanduser()


def get_database_url() -> str | None:
    """Return the configured database URL."""

    return (
        os.getenv(POSTGRES_URL_ENV_VAR)
        or os.getenv(DATABASE_URL_ENV_VAR)
        or settings.POSTGRES_URL
        or settings.DATABASE_URL
    )


def utc_now() -> datetime:
    """Return the current UTC timestamp."""

    return datetime.now(tz=UTC)


def isoformat_utc(value: datetime | None = None) -> str:
    """Convert a datetime into an ISO 8601 UTC string."""

    current = value or utc_now()
    return current.astimezone(UTC).isoformat()
