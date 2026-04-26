"""Seed RAID Nexus hospitals and ambulances from CSV files."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import database
from config import CITY_AMBULANCE_BASE_SPEED_KMH, CITY_CENTERS

HOSPITALS_CSV_PATH = BACKEND_DIR / "data" / "hospitals.csv"
AMBULANCES_CSV_PATH = BACKEND_DIR / "data" / "ambulances.csv"

HOSPITAL_COLUMNS = [
    "id",
    "name",
    "city",
    "lat",
    "lng",
    "total_beds",
    "occupied_beds",
    "specialties",
    "er_wait_minutes",
    "diversion_status",
]

AMBULANCE_COLUMNS = [
    "id",
    "city",
    "lat",
    "lng",
    "status",
    "type",
    "crew_readiness",
    "driver_name",
    "paramedic_name",
]

ALS_EQUIPMENT = [
    "defibrillator",
    "ALS_kit",
    "oxygen",
    "stretcher",
    "IV_kit",
    "nebulizer",
]

BLS_EQUIPMENT = [
    "trauma_kit",
    "oxygen",
    "stretcher",
    "first_aid",
]

EXTRA_COLUMNS = {
    "hospitals": {
        "total_beds": "INTEGER",
        "occupied_beds": "INTEGER",
        "created_at": "TEXT",
    },
    "ambulances": {
        "driver_name": "TEXT",
        "paramedic_name": "TEXT",
        "created_at": "TEXT",
    },
}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description="Seed RAID Nexus hospitals and ambulances from CSV.")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete existing hospital and ambulance records before seeding.",
    )
    return parser.parse_args()


def _utc_now_string() -> str:
    """Return a UTC timestamp string using datetime.utcnow()."""

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return datetime.utcnow().isoformat()


def _parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _load_csv_rows(path: Path, expected_columns: list[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Seed file not found: {path}")

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        actual_columns = reader.fieldnames or []
        if actual_columns != expected_columns:
            raise ValueError(
                f"{path.name} columns do not match expected order. "
                f"Expected {expected_columns}, got {actual_columns}."
            )
        return list(reader)


def _infer_zone(city: str, lat: float, lng: float) -> str:
    center_lat, center_lng = CITY_CENTERS[city]
    lat_offset = lat - center_lat
    lng_offset = lng - center_lng

    if abs(lat_offset) >= abs(lng_offset):
        return "North" if lat_offset >= 0 else "South"
    return "East" if lng_offset >= 0 else "West"


def _infer_hospital_type(specialties: list[str]) -> str:
    specialty_set = {item.strip().lower() for item in specialties}

    if len(specialty_set) >= 4 or {"cardiology", "neurology", "surgery"}.issubset(specialty_set):
        return "multi-specialty"
    if {"surgery", "orthopedics"}.issubset(specialty_set):
        return "trauma"
    if "cardiology" in specialty_set:
        return "cardiac"
    return "general"


def _derive_icu_beds(total_beds: int, occupancy_pct: float) -> tuple[int, int]:
    total_icu_beds = max(10, int(round(total_beds * 0.08)))
    occupied_icu_beds = min(total_icu_beds, int(round(total_icu_beds * (occupancy_pct / 100.0))))
    icu_beds_available = max(total_icu_beds - occupied_icu_beds, 0)
    return icu_beds_available, total_icu_beds


def _compute_acceptance_score(
    occupancy_pct: float,
    er_wait_minutes: int,
    specialties: list[str],
    diversion_status: bool,
) -> float:
    capacity_score = max(0.0, 1.0 - (occupancy_pct / 100.0))
    wait_score = max(0.0, 1.0 - (min(er_wait_minutes, 60) / 60.0))
    specialty_score = min(len(specialties) / 5.0, 1.0)
    diversion_penalty = 0.0 if diversion_status else 0.05
    score = (capacity_score * 0.45) + (wait_score * 0.25) + (specialty_score * 0.30) + diversion_penalty
    return round(min(score, 1.0), 3)


def _derive_speed_kmh(unit_type: str, crew_readiness: float) -> float:
    if unit_type == "ALS":
        return round(CITY_AMBULANCE_BASE_SPEED_KMH + 2.5 + ((crew_readiness - 0.85) * 10.0), 1)
    return round(CITY_AMBULANCE_BASE_SPEED_KMH - 2.0 + ((crew_readiness - 0.70) * 6.0), 1)


def _build_hospital_payload(row: dict[str, str], created_at: str) -> dict[str, Any]:
    total_beds = int(row["total_beds"])
    occupied_beds = int(row["occupied_beds"])
    occupancy_pct = round((occupied_beds / total_beds) * 100.0, 2)
    specialties = [item.strip() for item in row["specialties"].split("|") if item.strip()]
    diversion_status = _parse_bool(row["diversion_status"])
    icu_beds_available, total_icu_beds = _derive_icu_beds(total_beds, occupancy_pct)

    return {
        "id": row["id"].strip(),
        "name": row["name"].strip(),
        "city": row["city"].strip(),
        "lat": float(row["lat"]),
        "lng": float(row["lng"]),
        "type": _infer_hospital_type(specialties),
        "specialties": specialties,
        "occupancy_pct": occupancy_pct,
        "er_wait_minutes": int(row["er_wait_minutes"]),
        "icu_beds_available": icu_beds_available,
        "total_icu_beds": total_icu_beds,
        "trauma_support": any(item in {"surgery", "orthopedics"} for item in specialties),
        "acceptance_score": _compute_acceptance_score(
            occupancy_pct,
            int(row["er_wait_minutes"]),
            specialties,
            diversion_status,
        ),
        "diversion_status": diversion_status,
        "incoming_patients": [],
        "total_beds": total_beds,
        "occupied_beds": occupied_beds,
        "created_at": created_at,
    }


def _build_ambulance_payload(row: dict[str, str], created_at: str) -> dict[str, Any]:
    city = row["city"].strip()
    unit_type = row["type"].strip()
    current_lat = float(row["lat"])
    current_lng = float(row["lng"])
    crew_readiness = float(row["crew_readiness"])

    return {
        "id": row["id"].strip(),
        "city": city,
        "current_lat": current_lat,
        "current_lng": current_lng,
        "status": row["status"].strip(),
        "type": unit_type,
        "equipment": ALS_EQUIPMENT if unit_type == "ALS" else BLS_EQUIPMENT,
        "speed_kmh": _derive_speed_kmh(unit_type, crew_readiness),
        "crew_readiness": crew_readiness,
        "assigned_incident_id": None,
        "assigned_hospital_id": None,
        "zone": _infer_zone(city, current_lat, current_lng),
        "driver_name": row["driver_name"].strip(),
        "paramedic_name": row["paramedic_name"].strip(),
        "created_at": created_at,
    }


def _detect_memory_store() -> dict[str, Any] | None:
    for attr_name in ("DATABASE", "DB", "MEMORY_DB", "_DATABASE", "_DB"):
        candidate = getattr(database, attr_name, None)
        if isinstance(candidate, dict):
            return candidate
    return None


def _detect_backend_kind(connection: Any, memory_store: dict[str, Any] | None) -> str:
    if memory_store is not None:
        return "memory"
    module_name = connection.__class__.__module__.lower()
    class_name = connection.__class__.__name__.lower()
    label = f"{module_name}.{class_name}"
    if "sqlite" in label:
        return "sqlite"
    if "postgres" in label or "asyncpg" in label or "psycopg" in label:
        return "postgres"
    raise RuntimeError(f"Unsupported database backend for seeding: {label}")


async def _ensure_sqlite_columns(connection: Any) -> None:
    for table, columns in EXTRA_COLUMNS.items():
        cursor = await connection.execute(f"PRAGMA table_info({table})")
        rows = await cursor.fetchall()
        existing_columns = {row[1] for row in rows}
        for column_name, column_type in columns.items():
            if column_name not in existing_columns:
                await connection.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_type}")
    await connection.commit()


async def _ensure_postgres_columns(connection: Any) -> None:
    for table, columns in EXTRA_COLUMNS.items():
        rows = await connection.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = $1
            """,
            table,
        )
        existing_columns = {row["column_name"] for row in rows}
        for column_name, column_type in columns.items():
            if column_name not in existing_columns:
                await connection.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column_name} {column_type}")


def _serialize_for_sqlite(table: str, payload: dict[str, Any]) -> dict[str, Any]:
    serialized = dict(payload)
    if table == "hospitals":
        serialized["specialties"] = json.dumps(payload["specialties"], ensure_ascii=True)
        serialized["incoming_patients"] = json.dumps(payload["incoming_patients"], ensure_ascii=True)
        serialized["trauma_support"] = 1 if payload["trauma_support"] else 0
        serialized["diversion_status"] = 1 if payload["diversion_status"] else 0
    elif table == "ambulances":
        serialized["equipment"] = json.dumps(payload["equipment"], ensure_ascii=True)
    return serialized


async def _clear_sqlite_tables(connection: Any) -> None:
    await connection.execute("DELETE FROM hospitals")
    await connection.execute("DELETE FROM ambulances")
    await connection.commit()


async def _clear_postgres_tables(connection: Any) -> None:
    await connection.execute("TRUNCATE TABLE hospitals, ambulances RESTART IDENTITY CASCADE")


def _upsert_sql(table: str, columns: list[str], backend_kind: str) -> str:
    column_sql = ", ".join(columns)
    if backend_kind == "sqlite":
        placeholders = ", ".join(f":{column}" for column in columns)
    else:
        placeholders = ", ".join(f"${index}" for index in range(1, len(columns) + 1))
    update_sql = ", ".join(f"{column} = EXCLUDED.{column}" for column in columns if column != "id")
    return (
        f"INSERT INTO {table} ({column_sql}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT(id) DO UPDATE SET {update_sql}"
    )


async def _upsert_sqlite_records(connection: Any, table: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return

    columns = list(rows[0].keys())
    sql = _upsert_sql(table, columns, "sqlite")
    for row in rows:
        await connection.execute(sql, _serialize_for_sqlite(table, row))
    await connection.commit()


async def _upsert_postgres_records(connection: Any, table: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return

    columns = list(rows[0].keys())
    sql = _upsert_sql(table, columns, "postgres")
    for row in rows:
        values = [json.dumps(row[column], ensure_ascii=True) if isinstance(row[column], list) else row[column] for column in columns]
        await connection.execute(sql, *values)


def _get_memory_table(store: dict[str, Any], table_name: str) -> Any:
    if table_name not in store:
        store[table_name] = {}
    return store[table_name]


def _clear_memory_tables(store: dict[str, Any]) -> None:
    for table_name in ("hospitals", "ambulances"):
        table = _get_memory_table(store, table_name)
        if isinstance(table, dict):
            table.clear()
        elif isinstance(table, list):
            table[:] = []
        else:
            store[table_name] = {}


def _upsert_memory_records(store: dict[str, Any], table_name: str, rows: list[dict[str, Any]]) -> None:
    table = _get_memory_table(store, table_name)
    if isinstance(table, dict):
        for row in rows:
            table[row["id"]] = dict(row)
        return

    if isinstance(table, list):
        index_by_id = {item.get("id"): index for index, item in enumerate(table) if isinstance(item, dict)}
        for row in rows:
            record = dict(row)
            if row["id"] in index_by_id:
                table[index_by_id[row["id"]]] = record
            else:
                table.append(record)
        return

    raise RuntimeError(f"Unsupported in-memory table type for {table_name}: {type(table)!r}")


async def _seed_relational_backend(backend_kind: str, connection: Any, clear: bool) -> None:
    if backend_kind == "sqlite":
        await _ensure_sqlite_columns(connection)
        if clear:
            await _clear_sqlite_tables(connection)
    elif backend_kind == "postgres":
        await _ensure_postgres_columns(connection)
        if clear:
            await _clear_postgres_tables(connection)
    else:
        raise RuntimeError(f"Unsupported relational backend: {backend_kind}")


async def run_seed(clear: bool = False) -> tuple[int, int]:
    """Read the CSVs and seed the configured database."""

    created_at = _utc_now_string()
    hospital_rows = _load_csv_rows(HOSPITALS_CSV_PATH, HOSPITAL_COLUMNS)
    ambulance_rows = _load_csv_rows(AMBULANCES_CSV_PATH, AMBULANCE_COLUMNS)
    hospitals = [_build_hospital_payload(row, created_at) for row in hospital_rows]
    ambulances = [_build_ambulance_payload(row, created_at) for row in ambulance_rows]

    await database.initialize_database()

    memory_store = _detect_memory_store()
    if memory_store is not None:
        if clear:
            _clear_memory_tables(memory_store)
        _upsert_memory_records(memory_store, "hospitals", hospitals)
        _upsert_memory_records(memory_store, "ambulances", ambulances)
        return len(hospitals), len(ambulances)

    async with database.get_connection() as connection:
        backend_kind = _detect_backend_kind(connection, None)
        await _seed_relational_backend(backend_kind, connection, clear)
        if backend_kind == "sqlite":
            await _upsert_sqlite_records(connection, "hospitals", hospitals)
            await _upsert_sqlite_records(connection, "ambulances", ambulances)
        else:
            await _upsert_postgres_records(connection, "hospitals", hospitals)
            await _upsert_postgres_records(connection, "ambulances", ambulances)

    if hasattr(database, "close_connection"):
        await database.close_connection()
    return len(hospitals), len(ambulances)


def main() -> None:
    args = parse_args()
    hospitals_seeded, ambulances_seeded = asyncio.run(run_seed(clear=args.clear))
    print(f"Seeded {hospitals_seeded} hospitals and {ambulances_seeded} ambulances across 5 cities")


if __name__ == "__main__":
    main()
