"""Incident repository for SQLite and PostgreSQL."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update

from database import fetch_all, fetch_one, insert_record, update_record
from models.orm import Incident
from repositories._helpers import is_pg_session, model_to_record, serialize_for_model


class IncidentRepository:
    def __init__(self, db: Any = None):
        self.db = db

    async def create(self, incident: dict[str, Any]) -> dict[str, Any]:
        if is_pg_session(self.db):
            row = Incident(**serialize_for_model("incidents", incident))
            self.db.add(row)
            await self.db.flush()
            return model_to_record(row)
        await insert_record("incidents", incident)
        return incident

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        if is_pg_session(self.db):
            row = await self.db.get(Incident, id)
            return model_to_record(row) if row else None
        return await fetch_one("incidents", id)

    async def get_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        if is_pg_session(self.db):
            stmt = select(Incident).order_by(Incident.created_at.desc()).limit(limit)
            return [model_to_record(row) for row in (await self.db.execute(stmt)).scalars().all()]
        return (await fetch_all("incidents"))[:limit]

    async def update_status(self, id: str, status: str) -> None:
        if is_pg_session(self.db):
            await self.db.execute(update(Incident).where(Incident.id == id).values(status=status))
            await self.db.flush()
            return
        await update_record("incidents", id, {"status": status})

    async def update(self, id: str, updates: dict[str, Any]) -> None:
        if is_pg_session(self.db):
            await self.db.execute(update(Incident).where(Incident.id == id).values(**serialize_for_model("incidents", updates)))
            await self.db.flush()
            return
        await update_record("incidents", id, updates)
