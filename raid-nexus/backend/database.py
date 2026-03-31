"""SQLite helpers, schema management, and seed loading for RAID Nexus."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

import aiosqlite

from config import DATA_DIR, DB_PATH

TABLE_JSON_FIELDS: dict[str, set[str]] = {
    "ambulances": {"equipment"},
    "hospitals": {"specialties", "incoming_patients"},
    "dispatch_plans": {"rejected_ambulances", "rejected_hospitals"},
    "notifications": {"ambulance_equipment", "prep_checklist", "payload"},
}

TABLE_BOOL_FIELDS: dict[str, set[str]] = {
    "hospitals": {"trauma_support", "diversion_status"},
    "patients": {"sos_mode"},
    "dispatch_plans": {"overload_avoided"},
}

TABLE_ORDERING: dict[str, str] = {
    "ambulances": "ORDER BY id ASC",
    "hospitals": "ORDER BY id ASC",
    "incidents": "ORDER BY created_at DESC",
    "patients": "ORDER BY created_at DESC",
    "dispatch_plans": "ORDER BY created_at DESC",
    "notifications": "ORDER BY created_at DESC",
}


@asynccontextmanager
async def get_connection() -> aiosqlite.Connection:
    """Yield an initialized aiosqlite connection."""

    connection = await aiosqlite.connect(DB_PATH)
    connection.row_factory = aiosqlite.Row
    await connection.execute("PRAGMA foreign_keys = ON;")
    await connection.execute("PRAGMA journal_mode = WAL;")
    try:
        yield connection
    finally:
        await connection.close()


async def initialize_database() -> None:
    """Create all required SQLite tables."""

    async with get_connection() as connection:
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
                patient_id TEXT
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
                overload_avoided INTEGER NOT NULL DEFAULT 0
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
            """
        )
        await connection.commit()


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
