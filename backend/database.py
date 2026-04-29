"""Database helpers, schema management, and seed loading for RAID Nexus."""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

import aiosqlite
from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import (
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    DATA_DIR,
    USER_PASSWORD,
    USER_USERNAME,
    get_database_url,
    get_db_path,
    isoformat_utc,
    settings,
)
from models.orm import Base

_PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _normalize_async_database_url(database_url: str | None) -> str | None:
    """Return a SQLAlchemy async URL for PostgreSQL connection strings."""

    if not database_url:
        return database_url
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql+psycopg2://"):
        database_url = database_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)

    parsed = urlsplit(database_url)
    if parsed.scheme != "postgresql+asyncpg":
        return database_url

    query_params = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() != "sslmode"
    ]
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query_params, doseq=True),
            parsed.fragment,
        )
    )


def _database_sslmode(database_url: str | None) -> str | None:
    """Extract libpq sslmode from a database URL query string."""

    if not database_url:
        return None

    for key, value in parse_qsl(urlsplit(database_url).query, keep_blank_values=True):
        if key.lower() == "sslmode":
            return value.lower()
    return None


def _postgres_connect_args(database_url: str, sslmode: str | None) -> dict[str, Any]:
    """Return asyncpg connect args for provider-specific PostgreSQL URLs."""

    if sslmode in {"require", "verify-ca", "verify-full"} or "neon.tech" in database_url:
        return {"ssl": "require"}
    return {}


RAW_DATABASE_URL = get_database_url()
DATABASE_SSLMODE = _database_sslmode(RAW_DATABASE_URL)
DATABASE_URL = _normalize_async_database_url(RAW_DATABASE_URL)
IS_POSTGRES = bool(
    DATABASE_URL
    and DATABASE_URL.startswith(("postgresql", "postgres"))
    and not settings.RAID_FORCE_SQLITE
)

engine = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None

if IS_POSTGRES:
    engine = create_async_engine(
        str(DATABASE_URL),
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
        connect_args=_postgres_connect_args(str(DATABASE_URL), DATABASE_SSLMODE),
    )
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

TABLE_JSON_FIELDS: dict[str, set[str]] = {
    "ambulances": {"equipment"},
    "hospitals": {"specialties", "incoming_patients"},
    "incidents": {"anomaly_flags"},
    "dispatch_plans": {"rejected_ambulances", "rejected_hospitals"},
    "dispatch_audit_log": {"metadata"},
    "notifications": {"ambulance_equipment", "prep_checklist", "payload"},
}

TABLE_BOOL_FIELDS: dict[str, set[str]] = {
    "hospitals": {"trauma_support", "diversion_status"},
    "incidents": {"requires_human_review", "has_anomaly"},
    "patients": {"sos_mode"},
    "dispatch_plans": {"overload_avoided"},
    "users": {"is_active"},
}

TABLE_ORDERING: dict[str, str] = {
    "ambulances": "ORDER BY id ASC",
    "hospitals": "ORDER BY id ASC",
    "incidents": "ORDER BY created_at DESC",
    "patients": "ORDER BY created_at DESC",
    "dispatch_plans": "ORDER BY created_at DESC",
    "dispatch_audit_log": "ORDER BY created_at ASC",
    "override_requests": "ORDER BY requested_at DESC",
    "notifications": "ORDER BY created_at DESC",
    "users": "ORDER BY username ASC",
}

_DB_LOCK = asyncio.Lock()
_DB_CONNECTION: aiosqlite.Connection | None = None
_DB_CONNECTION_PATH: str | None = None


def using_postgres() -> bool:
    """Return True when the app is configured to use PostgreSQL."""

    return IS_POSTGRES


def database_backend_label() -> str:
    """Return a human-readable database backend label for health responses."""

    return "PostgreSQL (SQLAlchemy asyncpg pool)" if IS_POSTGRES else "aiosqlite (single connection)"


class _Cursor:
    """Small cursor-like wrapper used by the SQLAlchemy adapter."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = rows or []

    async def fetchone(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None

    async def fetchall(self) -> list[dict[str, Any]]:
        return list(self._rows)


def _query_returns_rows(query: str) -> bool:
    first_token = query.lstrip().split(None, 1)[0].upper() if query.strip() else ""
    return first_token in {"SELECT", "WITH", "SHOW"} or " RETURNING " in f" {query.upper()} "


def _convert_qmarks(query: str, params: tuple[Any, ...] | list[Any]) -> tuple[str, dict[str, Any]]:
    values: dict[str, Any] = {}
    index = 0

    def replace(_match: re.Match[str]) -> str:
        nonlocal index
        key = f"p{index}"
        values[key] = params[index]
        index += 1
        return f":{key}"

    converted = re.sub(r"\?", replace, query)
    if index != len(params):
        raise ValueError(f"SQL placeholder count ({index}) does not match parameter count ({len(params)}).")
    return converted, values


def _prepare_sqlalchemy_query(query: str, params: Any = None) -> tuple[str, dict[str, Any]]:
    if params is None:
        return query, {}
    if isinstance(params, dict):
        return query, dict(params)
    if isinstance(params, (tuple, list)):
        return _convert_qmarks(query, params)
    return _convert_qmarks(query, (params,))


class _SqlAlchemyConnection:
    """Compatibility adapter exposing a subset of aiosqlite's async API."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, query: str, params: Any = None) -> _Cursor:
        sql, values = _prepare_sqlalchemy_query(query, params)
        result = await self._session.execute(text(sql), values)
        if _query_returns_rows(sql):
            return _Cursor([dict(row) for row in result.mappings().all()])
        return _Cursor()

    async def commit(self) -> None:
        await self._session.commit()


async def _ensure_connection() -> aiosqlite.Connection:
    """Return a reusable SQLite connection for the active database path."""

    global _DB_CONNECTION, _DB_CONNECTION_PATH

    db_path = get_db_path()
    resolved_path = str(db_path.resolve())
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if _DB_CONNECTION is not None and _DB_CONNECTION_PATH == resolved_path:
        return _DB_CONNECTION

    if _DB_CONNECTION is not None:
        await _DB_CONNECTION.close()

    connection = await aiosqlite.connect(db_path, timeout=30)
    connection.row_factory = aiosqlite.Row
    await connection.execute("PRAGMA foreign_keys = ON;")
    await connection.execute("PRAGMA busy_timeout = 30000;")
    _DB_CONNECTION = connection
    _DB_CONNECTION_PATH = resolved_path
    return connection


async def close_connection() -> None:
    """Close reusable database connections, if any are open."""

    global _DB_CONNECTION, _DB_CONNECTION_PATH

    if _DB_CONNECTION is not None:
        await _DB_CONNECTION.close()
    _DB_CONNECTION = None
    _DB_CONNECTION_PATH = None
    if engine is not None:
        await engine.dispose()


@asynccontextmanager
async def get_connection():
    """Yield an initialized database connection adapter."""

    if IS_POSTGRES:
        if AsyncSessionLocal is None:
            raise RuntimeError("PostgreSQL sessionmaker is not initialized.")
        async with AsyncSessionLocal() as session:
            yield _SqlAlchemyConnection(session)
        return

    async with _DB_LOCK:
        connection = await _ensure_connection()
        yield connection


async def get_db() -> AsyncGenerator[AsyncSession | aiosqlite.Connection, None]:
    """Yield a request-scoped database session/connection."""

    if IS_POSTGRES:
        if AsyncSessionLocal is None:
            raise RuntimeError("PostgreSQL sessionmaker is not initialized.")
        async with AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        return

    async with get_connection() as connection:
        try:
            yield connection
            await connection.commit()
        except Exception:
            await connection.rollback()
            raise


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    patient_count INTEGER NOT NULL,
    location_lat REAL NOT NULL,
    location_lng REAL NOT NULL,
    city TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    patient_id TEXT,
    triage_confidence REAL,
    requires_human_review INTEGER NOT NULL DEFAULT 0,
    review_reason TEXT,
    triage_version TEXT,
    language_detected TEXT,
    language_name TEXT,
    original_complaint TEXT,
    translated_complaint TEXT,
    translation_model TEXT,
    has_anomaly INTEGER NOT NULL DEFAULT 0,
    anomaly_flags TEXT
);

CREATE TABLE IF NOT EXISTS ambulances (
    id TEXT PRIMARY KEY,
    city TEXT NOT NULL,
    current_lat REAL NOT NULL,
    current_lng REAL NOT NULL,
    status TEXT NOT NULL,
    type TEXT NOT NULL,
    equipment TEXT NOT NULL,
    speed_kmh REAL NOT NULL,
    crew_readiness REAL NOT NULL,
    assigned_incident_id TEXT,
    assigned_hospital_id TEXT,
    zone TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hospitals (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    lat REAL NOT NULL,
    lng REAL NOT NULL,
    type TEXT NOT NULL,
    specialties TEXT NOT NULL,
    occupancy_pct REAL NOT NULL,
    er_wait_minutes INTEGER NOT NULL,
    icu_beds_available INTEGER NOT NULL,
    total_icu_beds INTEGER NOT NULL,
    trauma_support INTEGER NOT NULL,
    acceptance_score REAL NOT NULL,
    diversion_status INTEGER NOT NULL,
    incoming_patients TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    age INTEGER NOT NULL,
    gender TEXT NOT NULL,
    mobile TEXT NOT NULL,
    location_lat REAL NOT NULL,
    location_lng REAL NOT NULL,
    chief_complaint TEXT NOT NULL,
    severity TEXT NOT NULL,
    sos_mode INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    assigned_ambulance_id TEXT,
    assigned_hospital_id TEXT,
    status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dispatch_plans (
    id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    patient_id TEXT,
    ambulance_id TEXT NOT NULL,
    hospital_id TEXT NOT NULL,
    ambulance_score REAL NOT NULL,
    hospital_score REAL NOT NULL,
    route_score REAL NOT NULL,
    final_score REAL NOT NULL,
    eta_minutes REAL NOT NULL,
    distance_km REAL NOT NULL,
    rejected_ambulances TEXT NOT NULL,
    rejected_hospitals TEXT NOT NULL,
    explanation_text TEXT NOT NULL,
    fallback_hospital_id TEXT,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    baseline_eta_minutes REAL,
    overload_avoided INTEGER NOT NULL DEFAULT 0,
    override_id TEXT
);

CREATE TABLE IF NOT EXISTS dispatch_audit_log (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    dispatch_id TEXT NOT NULL,
    incident_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    ai_ambulance_id TEXT,
    ai_hospital_id TEXT,
    ai_eta_minutes REAL,
    ai_score REAL,
    ai_explanation TEXT,
    final_ambulance_id TEXT NOT NULL,
    final_hospital_id TEXT NOT NULL,
    final_eta_minutes REAL NOT NULL,
    override_reason TEXT,
    override_ambulance_id TEXT,
    override_hospital_id TEXT,
    incident_lat REAL,
    incident_lng REAL,
    incident_type TEXT,
    incident_severity TEXT,
    incident_city TEXT,
    created_at TEXT NOT NULL,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS override_requests (
    id TEXT PRIMARY KEY,
    dispatch_id TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    original_ambulance_id TEXT NOT NULL,
    original_hospital_id TEXT NOT NULL,
    proposed_ambulance_id TEXT NOT NULL,
    proposed_hospital_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    reason_category TEXT NOT NULL,
    status TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TEXT,
    rejection_reason TEXT,
    audit_log_id TEXT
);

CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    hospital_id TEXT NOT NULL,
    patient_name TEXT NOT NULL,
    patient_age INTEGER NOT NULL,
    patient_gender TEXT NOT NULL,
    chief_complaint TEXT NOT NULL,
    severity TEXT NOT NULL,
    eta_minutes REAL NOT NULL,
    ambulance_id TEXT NOT NULL,
    ambulance_equipment TEXT NOT NULL,
    ambulance_type TEXT NOT NULL,
    prep_checklist TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    role TEXT NOT NULL,
    full_name TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
"""

SQLITE_INDEXES = """
CREATE INDEX IF NOT EXISTS ix_ambulances_city ON ambulances(city);
CREATE INDEX IF NOT EXISTS ix_ambulances_status ON ambulances(status);
CREATE INDEX IF NOT EXISTS ix_hospitals_city ON hospitals(city);
CREATE INDEX IF NOT EXISTS ix_hospitals_diversion_status ON hospitals(diversion_status);
CREATE INDEX IF NOT EXISTS ix_incidents_city ON incidents(city);
CREATE INDEX IF NOT EXISTS ix_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS ix_incidents_severity ON incidents(severity);
CREATE INDEX IF NOT EXISTS ix_incidents_created_at ON incidents(created_at);
CREATE INDEX IF NOT EXISTS ix_dispatch_plans_incident_id ON dispatch_plans(incident_id);
CREATE INDEX IF NOT EXISTS ix_dispatch_plans_ambulance_id ON dispatch_plans(ambulance_id);
CREATE INDEX IF NOT EXISTS ix_dispatch_plans_hospital_id ON dispatch_plans(hospital_id);
CREATE INDEX IF NOT EXISTS ix_dispatch_plans_status ON dispatch_plans(status);
CREATE INDEX IF NOT EXISTS ix_dispatch_audit_log_dispatch_id ON dispatch_audit_log(dispatch_id);
CREATE INDEX IF NOT EXISTS ix_dispatch_audit_log_actor_id ON dispatch_audit_log(actor_id);
CREATE INDEX IF NOT EXISTS ix_dispatch_audit_log_event_type ON dispatch_audit_log(event_type);
CREATE INDEX IF NOT EXISTS ix_dispatch_audit_log_created_at ON dispatch_audit_log(created_at);
CREATE INDEX IF NOT EXISTS ix_override_requests_dispatch_id ON override_requests(dispatch_id);
CREATE INDEX IF NOT EXISTS ix_override_requests_status ON override_requests(status);
CREATE INDEX IF NOT EXISTS ix_users_username ON users(username);
"""


async def initialize_database() -> None:
    """Create all required database tables for the active backend."""

    if IS_POSTGRES:
        if engine is None:
            raise RuntimeError("PostgreSQL engine is not initialized.")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await _ensure_default_users()
        return

    async with get_connection() as connection:
        await connection.execute("PRAGMA journal_mode = WAL;")
        await connection.executescript(SQLITE_SCHEMA)
        await connection.executescript(SQLITE_INDEXES)
        await _apply_sqlite_compat_migrations(connection)
        await connection.commit()
    await _ensure_default_users()


async def _apply_sqlite_compat_migrations(connection: aiosqlite.Connection) -> None:
    """Add compatibility columns for existing local SQLite databases."""

    cursor = await connection.execute("PRAGMA table_info(dispatch_plans)")
    dispatch_columns = {str(row["name"]) for row in await cursor.fetchall()}
    if "override_id" not in dispatch_columns:
        await connection.execute("ALTER TABLE dispatch_plans ADD COLUMN override_id TEXT")

    cursor = await connection.execute("PRAGMA table_info(incidents)")
    incident_columns = {str(row["name"]) for row in await cursor.fetchall()}
    incident_migrations = {
        "triage_confidence": "ALTER TABLE incidents ADD COLUMN triage_confidence REAL",
        "requires_human_review": "ALTER TABLE incidents ADD COLUMN requires_human_review INTEGER NOT NULL DEFAULT 0",
        "review_reason": "ALTER TABLE incidents ADD COLUMN review_reason TEXT",
        "triage_version": "ALTER TABLE incidents ADD COLUMN triage_version TEXT",
        "language_detected": "ALTER TABLE incidents ADD COLUMN language_detected TEXT",
        "language_name": "ALTER TABLE incidents ADD COLUMN language_name TEXT",
        "original_complaint": "ALTER TABLE incidents ADD COLUMN original_complaint TEXT",
        "translated_complaint": "ALTER TABLE incidents ADD COLUMN translated_complaint TEXT",
        "translation_model": "ALTER TABLE incidents ADD COLUMN translation_model TEXT",
        "has_anomaly": "ALTER TABLE incidents ADD COLUMN has_anomaly INTEGER NOT NULL DEFAULT 0",
        "anomaly_flags": "ALTER TABLE incidents ADD COLUMN anomaly_flags TEXT",
    }
    for column, statement in incident_migrations.items():
        if column not in incident_columns:
            await connection.execute(statement)

    await connection.execute(
        "UPDATE dispatch_plans SET status = 'active' WHERE status IN ('success', 'dispatched')"
    )


def _json_empty_value(table: str, key: str) -> Any:
    if table == "dispatch_audit_log" and key == "metadata":
        return {}
    if table == "notifications" and key == "payload":
        return {}
    return []


def _serialize_value(table: str, key: str, value: Any) -> Any:
    """Serialize a value into a database-friendly representation."""

    if key in TABLE_JSON_FIELDS.get(table, set()):
        return json.dumps(value if value is not None else _json_empty_value(table, key), ensure_ascii=True)
    if key in TABLE_BOOL_FIELDS.get(table, set()):
        return bool(value) if IS_POSTGRES else (1 if bool(value) else 0)
    return value


def _deserialize_record(table: str, row: Any | None) -> dict[str, Any] | None:
    """Convert a DB row into a Python dictionary."""

    if row is None:
        return None

    record = dict(row)
    for key in TABLE_JSON_FIELDS.get(table, set()):
        value = record.get(key)
        record[key] = json.loads(value) if value else _json_empty_value(table, key)
    for key in TABLE_BOOL_FIELDS.get(table, set()):
        if key in record:
            record[key] = bool(record[key])
    return record


async def _ensure_default_users() -> None:
    """Create/update demo users from environment-backed credentials."""

    created_at = isoformat_utc()
    default_users = [
        {
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD,
            "role": "admin",
            "full_name": "Admin",
        },
        {
            "username": USER_USERNAME,
            "password": USER_PASSWORD,
            "role": "user",
            "full_name": "User",
        },
    ]
    for default_user in default_users:
        existing_user = await fetch_one("users", default_user["username"], id_field="username")
        if existing_user is None:
            await insert_record(
                "users",
                {
                    "id": str(uuid4()),
                    "username": default_user["username"],
                    "hashed_password": _PWD_CONTEXT.hash(default_user["password"]),
                    "role": default_user["role"],
                    "full_name": default_user["full_name"],
                    "is_active": True,
                    "created_at": created_at,
                },
            )
            continue

        password_matches = _PWD_CONTEXT.verify(
            default_user["password"],
            str(existing_user["hashed_password"]),
        )
        if (
            not password_matches
            or str(existing_user["role"]) != default_user["role"]
            or str(existing_user.get("full_name") or "") != default_user["full_name"]
            or not bool(existing_user.get("is_active"))
        ):
            await update_record(
                "users",
                default_user["username"],
                {
                    "hashed_password": _PWD_CONTEXT.hash(default_user["password"]),
                    "role": default_user["role"],
                    "full_name": default_user["full_name"],
                    "is_active": True,
                },
                id_field="username",
            )


async def count_rows(table: str) -> int:
    """Count rows in a table."""

    async with get_connection() as connection:
        cursor = await connection.execute(f"SELECT COUNT(*) AS total FROM {table}")
        row = await cursor.fetchone()
        return int(row["total"])


async def insert_record(table: str, payload: dict[str, Any]) -> None:
    """Insert a serialized record into a table."""

    serialized = {key: _serialize_value(table, key, value) for key, value in payload.items()}
    columns = ", ".join(serialized.keys())
    placeholders = ", ".join(f":{key}" for key in serialized.keys())
    async with get_connection() as connection:
        await connection.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
            serialized,
        )
        await connection.commit()


async def update_record(
    table: str,
    record_id: str,
    updates: dict[str, Any],
    *,
    id_field: str = "id",
) -> None:
    """Update selected fields on a record."""

    serialized = {key: _serialize_value(table, key, value) for key, value in updates.items()}
    assignments = ", ".join(f"{key} = :{key}" for key in serialized.keys())
    serialized["record_id"] = record_id
    async with get_connection() as connection:
        await connection.execute(
            f"UPDATE {table} SET {assignments} WHERE {id_field} = :record_id",
            serialized,
        )
        await connection.commit()


async def fetch_one(table: str, record_id: str, *, id_field: str = "id") -> dict[str, Any] | None:
    """Fetch a single record by identifier."""

    async with get_connection() as connection:
        cursor = await connection.execute(
            f"SELECT * FROM {table} WHERE {id_field} = ?",
            (record_id,),
        )
        row = await cursor.fetchone()
        return _deserialize_record(table, row)


async def fetch_all(
    table: str,
    *,
    where_clause: str | None = None,
    params: tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    """Fetch multiple records with optional filtering."""

    query = f"SELECT * FROM {table}"
    if where_clause:
        query = f"{query} WHERE {where_clause}"
    query = f"{query} {TABLE_ORDERING.get(table, '')}".strip()
    async with get_connection() as connection:
        cursor = await connection.execute(query, params)
        rows = await cursor.fetchall()
    return [_deserialize_record(table, row) for row in rows]


async def delete_record(table: str, record_id: str, *, id_field: str = "id") -> None:
    """Delete a record by identifier."""

    async with get_connection() as connection:
        await connection.execute(f"DELETE FROM {table} WHERE {id_field} = ?", (record_id,))
        await connection.commit()


async def load_seed_data() -> dict[str, int]:
    """Load seed data into empty tables and return inserted counts."""

    inserted = {"ambulances": 0, "hospitals": 0, "incidents": 0}
    seed_files = {
        "ambulances": DATA_DIR / "ambulances.json",
        "hospitals": DATA_DIR / "hospitals.json",
        "incidents": DATA_DIR / "incidents_seed.json",
    }

    for table, path in seed_files.items():
        if await count_rows(table) > 0:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for record in payload:
            await insert_record(table, record)
            inserted[table] += 1
    return inserted
