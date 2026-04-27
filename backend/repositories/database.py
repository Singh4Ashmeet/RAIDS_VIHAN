"""Database helpers, schema management, and seed loading for RAID Nexus."""

from __future__ import annotations

# ARCHITECTURE NOTE - Scalability
# Current implementation supports local SQLite and DATABASE_URL-driven
# PostgreSQL via asyncpg. This is appropriate for prototype/development use.
# Production deployment still requires:
#   1. Formal database migrations via Alembic
#   2. Separation of read/write connections
#   3. Managed backups and retention policies
#   4. Observability for slow queries and pool saturation
# See docs/production_architecture.md for the full production design.

import asyncio
import json
import os
import re
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

import aiosqlite
from passlib.context import CryptContext

try:
    import asyncpg
except ModuleNotFoundError:  # pragma: no cover - exercised only when dependency is missing at runtime
    asyncpg = None

try:
    from core.config import (
        ADMIN_PASSWORD,
        ADMIN_USERNAME,
        DATA_DIR,
        USER_PASSWORD,
        USER_USERNAME,
        get_database_url,
        get_db_path,
        isoformat_utc,
    )
except ModuleNotFoundError:
    from backend.core.config import (
        ADMIN_PASSWORD,
        ADMIN_USERNAME,
        DATA_DIR,
        USER_PASSWORD,
        USER_USERNAME,
        get_database_url,
        get_db_path,
        isoformat_utc,
    )

_PWD_CONTEXT = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
_PG_POOL: Any | None = None
_PG_DSN: str | None = None

_NAMED_PARAM_RE = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")


def _postgres_url() -> str | None:
    """Return the active PostgreSQL URL unless tests force SQLite."""

    if os.getenv("RAID_FORCE_SQLITE", "").strip().lower() in {"1", "true", "yes", "on"}:
        return None
    return get_database_url()


def using_postgres() -> bool:
    """Return True when the app is configured to use PostgreSQL."""

    return bool(_postgres_url())


def database_backend_label() -> str:
    """Return a human-readable database backend label for health responses."""

    if using_postgres():
        return "PostgreSQL (asyncpg pool)"
    return "aiosqlite (single connection)"


class _PostgresCursor:
    """Small cursor-like wrapper for asyncpg rows."""

    def __init__(self, rows: list[Any] | tuple[Any, ...] = ()) -> None:
        self._rows = list(rows)

    async def fetchone(self) -> Any | None:
        return self._rows[0] if self._rows else None

    async def fetchall(self) -> list[Any]:
        return list(self._rows)


def _convert_named_placeholders(query: str, params: dict[str, Any]) -> tuple[str, list[Any]]:
    """Convert SQLite-style :name placeholders to asyncpg $1 placeholders."""

    values: list[Any] = []
    positions: dict[str, int] = {}

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in params:
            raise KeyError(f"Missing SQL parameter: {name}")
        if name not in positions:
            positions[name] = len(values) + 1
            values.append(params[name])
        return f"${positions[name]}"

    return _NAMED_PARAM_RE.sub(replace, query), values


def _convert_qmark_placeholders(query: str, params: tuple[Any, ...] | list[Any]) -> tuple[str, list[Any]]:
    """Convert SQLite-style ? placeholders to asyncpg $1 placeholders."""

    values = list(params)
    index = 0

    def replace(_match: re.Match[str]) -> str:
        nonlocal index
        index += 1
        return f"${index}"

    converted = re.sub(r"\?", replace, query)
    if index != len(values):
        raise ValueError(f"SQL placeholder count ({index}) does not match parameter count ({len(values)}).")
    return converted, values


def _prepare_postgres_query(query: str, params: Any = None, extra_args: tuple[Any, ...] = ()) -> tuple[str, list[Any]]:
    """Prepare a query and parameters for asyncpg."""

    if extra_args:
        return query, list((params,) + extra_args) if params is not None else list(extra_args)
    if params is None:
        return query, []
    if isinstance(params, dict):
        return _convert_named_placeholders(query, params)
    if isinstance(params, (tuple, list)):
        return _convert_qmark_placeholders(query, params)
    return _convert_qmark_placeholders(query, (params,))


def _query_returns_rows(query: str) -> bool:
    """Return True if a SQL statement should be executed with fetch."""

    first_token = query.lstrip().split(None, 1)[0].upper() if query.strip() else ""
    return first_token in {"SELECT", "WITH", "SHOW"} or " RETURNING " in f" {query.upper()} "


class _PostgresConnection:
    """Compatibility adapter exposing a subset of aiosqlite's async API."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    async def execute(self, query: str, params: Any = None, *args: Any) -> _PostgresCursor:
        sql, values = _prepare_postgres_query(query, params, args)
        if _query_returns_rows(sql):
            rows = await self._connection.fetch(sql, *values)
            return _PostgresCursor(rows)
        await self._connection.execute(sql, *values)
        return _PostgresCursor()

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        sql, values = _prepare_postgres_query(query, None, args)
        return list(await self._connection.fetch(sql, *values))

    async def fetchrow(self, query: str, *args: Any) -> Any | None:
        sql, values = _prepare_postgres_query(query, None, args)
        return await self._connection.fetchrow(sql, *values)

    async def commit(self) -> None:
        return None


async def _ensure_postgres_pool() -> Any:
    """Return a reusable asyncpg pool for DATABASE_URL."""

    global _PG_POOL, _PG_DSN

    database_url = _postgres_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured.")
    if asyncpg is None:
        raise RuntimeError("asyncpg is required for PostgreSQL support. Install requirements.txt.")
    if _PG_POOL is not None and _PG_DSN == database_url:
        return _PG_POOL
    if _PG_POOL is not None:
        await _PG_POOL.close()

    _PG_POOL = await asyncpg.create_pool(
        dsn=database_url,
        min_size=1,
        max_size=int(os.getenv("RAID_POSTGRES_POOL_SIZE", "5")),
        command_timeout=30,
    )
    _PG_DSN = database_url
    return _PG_POOL


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

    global _DB_CONNECTION, _DB_CONNECTION_PATH, _PG_POOL, _PG_DSN

    if _DB_CONNECTION is not None:
        await _DB_CONNECTION.close()
    _DB_CONNECTION = None
    _DB_CONNECTION_PATH = None
    if _PG_POOL is not None:
        await _PG_POOL.close()
    _PG_POOL = None
    _PG_DSN = None


@asynccontextmanager
async def get_connection():
    """Yield an initialized database connection adapter."""

    if using_postgres():
        pool = await _ensure_postgres_pool()
        async with pool.acquire() as connection:
            yield _PostgresConnection(connection)
        return

    async with _DB_LOCK:
        connection = await _ensure_connection()
        yield connection


async def initialize_database() -> None:
    """Create all required database tables."""

    if using_postgres():
        await _initialize_postgres_database()
        return

    async with get_connection() as connection:
        await connection.execute("PRAGMA journal_mode = WAL;")
        await connection.executescript(
            """
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
                event_type TEXT NOT NULL CHECK (
                    event_type IN (
                        'ai_dispatch',
                        'human_override',
                        'fallback_dispatch',
                        'dispatch_cancelled',
                        'override_rejected'
                    )
                ),
                dispatch_id TEXT NOT NULL,
                incident_id TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                actor_role TEXT NOT NULL CHECK (actor_role IN ('admin', 'dispatcher', 'system')),
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
                metadata TEXT,
                FOREIGN KEY (dispatch_id) REFERENCES dispatch_plans(id)
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
                reason_category TEXT NOT NULL CHECK (
                    reason_category IN (
                        'ambulance_closer',
                        'hospital_specialty',
                        'local_knowledge',
                        'ai_error',
                        'resource_conflict',
                        'other'
                    )
                ),
                status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected')),
                reviewed_by TEXT,
                reviewed_at TEXT,
                rejection_reason TEXT,
                audit_log_id TEXT,
                FOREIGN KEY (dispatch_id) REFERENCES dispatch_plans(id),
                FOREIGN KEY (audit_log_id) REFERENCES dispatch_audit_log(id)
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
                role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
                full_name TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            """
        )
        cursor = await connection.execute("PRAGMA table_info(dispatch_plans)")
        dispatch_columns = {str(row["name"]) for row in await cursor.fetchall()}
        if "override_id" not in dispatch_columns:
            await connection.execute("ALTER TABLE dispatch_plans ADD COLUMN override_id TEXT")
        cursor = await connection.execute("PRAGMA table_info(incidents)")
        incident_columns = {str(row["name"]) for row in await cursor.fetchall()}
        incident_migrations = {
            "triage_confidence": "ALTER TABLE incidents ADD COLUMN triage_confidence REAL",
            "requires_human_review": (
                "ALTER TABLE incidents ADD COLUMN requires_human_review INTEGER NOT NULL DEFAULT 0"
            ),
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
            cursor = await connection.execute(
                "SELECT id, hashed_password, role, full_name, is_active FROM users WHERE username = ?",
                (default_user["username"],),
            )
            existing_user = await cursor.fetchone()
            if existing_user is None:
                hashed_password = _PWD_CONTEXT.hash(default_user["password"])
                await connection.execute(
                    """
                    INSERT INTO users (
                        id,
                        username,
                        hashed_password,
                        role,
                        full_name,
                        is_active,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        default_user["username"],
                        hashed_password,
                        default_user["role"],
                        default_user["full_name"],
                        1,
                        created_at,
                    ),
                )
                continue

            password_matches = _PWD_CONTEXT.verify(
                default_user["password"],
                str(existing_user["hashed_password"]),
            )
            if (
                not password_matches
                or str(existing_user["role"]) != default_user["role"]
                or str(existing_user["full_name"] or "") != default_user["full_name"]
                or int(existing_user["is_active"]) != 1
            ):
                hashed_password = _PWD_CONTEXT.hash(default_user["password"])
                await connection.execute(
                    """
                    UPDATE users
                    SET hashed_password = ?,
                        role = ?,
                        full_name = ?,
                        is_active = 1
                    WHERE username = ?
                    """,
                    (
                        hashed_password,
                        default_user["role"],
                        default_user["full_name"],
                        default_user["username"],
                    ),
                )
        await connection.commit()


async def _execute_statements(connection: Any, script: str) -> None:
    """Execute semicolon-delimited SQL statements."""

    for statement in (part.strip() for part in script.split(";")):
        if statement:
            await connection.execute(statement)


async def _postgres_columns(connection: Any, table: str) -> set[str]:
    """Return column names for a PostgreSQL table."""

    rows = await connection.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = $1
        """,
        table,
    )
    return {str(row["column_name"]) for row in rows}


async def _initialize_postgres_database() -> None:
    """Create all required PostgreSQL tables and compatibility columns."""

    async with get_connection() as connection:
        await _execute_statements(
            connection,
            """
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
                event_type TEXT NOT NULL CHECK (
                    event_type IN (
                        'ai_dispatch',
                        'human_override',
                        'fallback_dispatch',
                        'dispatch_cancelled',
                        'override_rejected'
                    )
                ),
                dispatch_id TEXT NOT NULL,
                incident_id TEXT NOT NULL,
                actor_id TEXT NOT NULL,
                actor_role TEXT NOT NULL CHECK (actor_role IN ('admin', 'dispatcher', 'system')),
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
                metadata TEXT,
                FOREIGN KEY (dispatch_id) REFERENCES dispatch_plans(id)
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
                reason_category TEXT NOT NULL CHECK (
                    reason_category IN (
                        'ambulance_closer',
                        'hospital_specialty',
                        'local_knowledge',
                        'ai_error',
                        'resource_conflict',
                        'other'
                    )
                ),
                status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected')),
                reviewed_by TEXT,
                reviewed_at TEXT,
                rejection_reason TEXT,
                audit_log_id TEXT,
                FOREIGN KEY (dispatch_id) REFERENCES dispatch_plans(id),
                FOREIGN KEY (audit_log_id) REFERENCES dispatch_audit_log(id)
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
                role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
                full_name TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            """,
        )

        dispatch_columns = await _postgres_columns(connection, "dispatch_plans")
        if "override_id" not in dispatch_columns:
            await connection.execute("ALTER TABLE dispatch_plans ADD COLUMN IF NOT EXISTS override_id TEXT")

        incident_columns = await _postgres_columns(connection, "incidents")
        incident_migrations = {
            "triage_confidence": "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS triage_confidence REAL",
            "requires_human_review": (
                "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS requires_human_review INTEGER NOT NULL DEFAULT 0"
            ),
            "review_reason": "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS review_reason TEXT",
            "triage_version": "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS triage_version TEXT",
            "language_detected": "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS language_detected TEXT",
            "language_name": "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS language_name TEXT",
            "original_complaint": "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS original_complaint TEXT",
            "translated_complaint": "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS translated_complaint TEXT",
            "translation_model": "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS translation_model TEXT",
            "has_anomaly": "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS has_anomaly INTEGER NOT NULL DEFAULT 0",
            "anomaly_flags": "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS anomaly_flags TEXT",
        }
        for column, statement in incident_migrations.items():
            if column not in incident_columns:
                await connection.execute(statement)

        await connection.execute(
            "UPDATE dispatch_plans SET status = 'active' WHERE status IN ('success', 'dispatched')"
        )

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
            cursor = await connection.execute(
                "SELECT id, hashed_password, role, full_name, is_active FROM users WHERE username = ?",
                (default_user["username"],),
            )
            existing_user = await cursor.fetchone()
            if existing_user is None:
                hashed_password = _PWD_CONTEXT.hash(default_user["password"])
                await connection.execute(
                    """
                    INSERT INTO users (
                        id,
                        username,
                        hashed_password,
                        role,
                        full_name,
                        is_active,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        default_user["username"],
                        hashed_password,
                        default_user["role"],
                        default_user["full_name"],
                        1,
                        created_at,
                    ),
                )
                continue

            password_matches = _PWD_CONTEXT.verify(
                default_user["password"],
                str(existing_user["hashed_password"]),
            )
            if (
                not password_matches
                or str(existing_user["role"]) != default_user["role"]
                or str(existing_user["full_name"] or "") != default_user["full_name"]
                or int(existing_user["is_active"]) != 1
            ):
                hashed_password = _PWD_CONTEXT.hash(default_user["password"])
                await connection.execute(
                    """
                    UPDATE users
                    SET hashed_password = ?,
                        role = ?,
                        full_name = ?,
                        is_active = 1
                    WHERE username = ?
                    """,
                    (
                        hashed_password,
                        default_user["role"],
                        default_user["full_name"],
                        default_user["username"],
                    ),
                )


def _serialize_value(table: str, key: str, value: Any) -> Any:
    """Serialize a value into a SQLite-friendly representation."""

    if key in TABLE_JSON_FIELDS.get(table, set()):
        return json.dumps(value, ensure_ascii=True)
    if key in TABLE_BOOL_FIELDS.get(table, set()):
        return 1 if bool(value) else 0
    return value


def _deserialize_record(table: str, row: aiosqlite.Row | None) -> dict[str, Any] | None:
    """Convert a SQLite row into a Python dictionary."""

    if row is None:
        return None

    record = dict(row)
    for key in TABLE_JSON_FIELDS.get(table, set()):
        record[key] = json.loads(record[key]) if record.get(key) else []
    for key in TABLE_BOOL_FIELDS.get(table, set()):
        if key in record:
            record[key] = bool(record[key])
    return record


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
    table_aliases = {"incidents": "incidents", "ambulances": "ambulances", "hospitals": "hospitals"}

    for key, path in seed_files.items():
        table = table_aliases[key]
        if await count_rows(table) > 0:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for record in payload:
            await insert_record(table, record)
            inserted[key] += 1
    return inserted
