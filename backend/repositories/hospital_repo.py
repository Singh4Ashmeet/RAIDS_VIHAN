"""Hospital repository for SQLite and PostgreSQL."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update

from database import fetch_all, fetch_one, insert_record, update_record
from models.orm import Hospital
from repositories._helpers import is_pg_session, model_to_record, serialize_for_model


class HospitalRepository:
    def __init__(self, db: Any = None):
        self.db = db

    async def get_all(self, city: str | None = None) -> list[dict[str, Any]]:
        if is_pg_session(self.db):
            stmt = select(Hospital)
            if city:
                stmt = stmt.where(Hospital.city == city)
            stmt = stmt.order_by(Hospital.id.asc())
            return [model_to_record(row) for row in (await self.db.execute(stmt)).scalars().all()]
        if city:
            return await fetch_all("hospitals", where_clause="city = ?", params=(city,))
        return await fetch_all("hospitals")

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        if is_pg_session(self.db):
            row = await self.db.get(Hospital, id)
            return model_to_record(row) if row else None
        return await fetch_one("hospitals", id)

    async def get_available(self) -> list[dict[str, Any]]:
        if is_pg_session(self.db):
            stmt = select(Hospital).where(Hospital.diversion_status.is_(False)).order_by(Hospital.id.asc())
            return [model_to_record(row) for row in (await self.db.execute(stmt)).scalars().all()]
        return await fetch_all("hospitals", where_clause="diversion_status = ?", params=(False,))

    async def update_occupancy(self, id: str, occupied_beds: int) -> None:
        updates = {"occupancy_pct": float(occupied_beds)}
        if is_pg_session(self.db):
            await self.db.execute(update(Hospital).where(Hospital.id == id).values(**updates))
            await self.db.flush()
            return
        await update_record("hospitals", id, updates)

    async def set_diversion(self, id: str, status: bool) -> None:
        if is_pg_session(self.db):
            await self.db.execute(update(Hospital).where(Hospital.id == id).values(diversion_status=status))
            await self.db.flush()
            return
        await update_record("hospitals", id, {"diversion_status": status})

    async def update(self, id: str, updates: dict[str, Any]) -> None:
        if is_pg_session(self.db):
            await self.db.execute(update(Hospital).where(Hospital.id == id).values(**serialize_for_model("hospitals", updates)))
            await self.db.flush()
            return
        await update_record("hospitals", id, updates)

    async def bulk_upsert(self, hospitals: list[dict[str, Any]]) -> None:
        if is_pg_session(self.db):
            for item in hospitals:
                await self.db.merge(Hospital(**serialize_for_model("hospitals", item)))
            await self.db.flush()
            return
        for item in hospitals:
            existing = await fetch_one("hospitals", str(item["id"]))
            if existing:
                await update_record("hospitals", str(item["id"]), {k: v for k, v in item.items() if k != "id"})
            else:
                await insert_record("hospitals", item)
