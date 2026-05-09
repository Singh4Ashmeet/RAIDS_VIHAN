"""Shared repository helpers."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from database import IS_POSTGRES, TABLE_BOOL_FIELDS, TABLE_INSERT_DEFAULTS, TABLE_JSON_FIELDS


def is_pg_session(db: Any) -> bool:
    return IS_POSTGRES and isinstance(db, AsyncSession)


def serialize_for_model(table: str, payload: dict[str, Any]) -> dict[str, Any]:
    serialized: dict[str, Any] = {}
    payload_with_defaults = {**TABLE_INSERT_DEFAULTS.get(table, {}), **payload}
    for key, value in payload_with_defaults.items():
        if key in TABLE_JSON_FIELDS.get(table, set()):
            serialized[key] = json.dumps(value if value is not None else [], ensure_ascii=True)
        elif key in TABLE_BOOL_FIELDS.get(table, set()):
            serialized[key] = bool(value)
        else:
            serialized[key] = value
    return serialized


def model_to_record(model: Any) -> dict[str, Any]:
    table = model.__tablename__
    record = {
        column.name: getattr(model, column.key)
        for column in model.__table__.columns
    }
    for key in TABLE_JSON_FIELDS.get(table, set()):
        value = record.get(key)
        if not value:
            record[key] = {} if key in {"metadata", "payload"} else []
        elif isinstance(value, str):
            record[key] = json.loads(value)
    for key in TABLE_BOOL_FIELDS.get(table, set()):
        if key in record:
            record[key] = bool(record[key])
    return record
