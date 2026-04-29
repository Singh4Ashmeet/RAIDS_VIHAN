"""Patient repository for SQLite and PostgreSQL."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update

from database import fetch_all, fetch_one, insert_record, update_record
from models.orm import Patient
from repositories._helpers import is_pg_session, model_to_record, serialize_for_model


class PatientRepository:
    def __init__(self, db: Any = None):
        self.db = db

    async def create(self, patient: dict[str, Any]) -> dict[str, Any]:
        if is_pg_session(self.db):
            row = Patient(**serialize_for_model("patients", patient))
            self.db.add(row)
            await self.db.flush()
            return model_to_record(row)
        await insert_record("patients", patient)
        return patient

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        if is_pg_session(self.db):
            row = await self.db.get(Patient, id)
            return model_to_record(row) if row else None
        return await fetch_one("patients", id)

    async def get_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        if is_pg_session(self.db):
            stmt = select(Patient).order_by(Patient.created_at.desc()).limit(limit)
            return [model_to_record(row) for row in (await self.db.execute(stmt)).scalars().all()]
        return (await fetch_all("patients"))[:limit]

    async def update(self, id: str, updates: dict[str, Any]) -> None:
        if is_pg_session(self.db):
            await self.db.execute(update(Patient).where(Patient.id == id).values(**serialize_for_model("patients", updates)))
            await self.db.flush()
            return
        await update_record("patients", id, updates)
