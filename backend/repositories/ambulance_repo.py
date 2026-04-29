"""Ambulance repository for SQLite and PostgreSQL."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update

from database import fetch_all, fetch_one, insert_record, update_record
from models.orm import Ambulance
from repositories._helpers import is_pg_session, model_to_record, serialize_for_model


class AmbulanceRepository:
    def __init__(self, db: Any = None):
        self.db = db

    async def get_all(self, city: str | None = None) -> list[dict[str, Any]]:
        if is_pg_session(self.db):
            stmt = select(Ambulance)
            if city:
                stmt = stmt.where(Ambulance.city == city)
            stmt = stmt.order_by(Ambulance.id.asc())
            rows = (await self.db.execute(stmt)).scalars().all()
            return [model_to_record(row) for row in rows]
        if city:
            return await fetch_all("ambulances", where_clause="city = ?", params=(city,))
        return await fetch_all("ambulances")

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        if is_pg_session(self.db):
            row = await self.db.get(Ambulance, id)
            return model_to_record(row) if row else None
        return await fetch_one("ambulances", id)

    async def get_available(self, city: str | None = None) -> list[dict[str, Any]]:
        if is_pg_session(self.db):
            stmt = select(Ambulance).where(Ambulance.status == "available")
            if city:
                stmt = stmt.where(Ambulance.city == city)
            stmt = stmt.order_by(Ambulance.id.asc())
            rows = (await self.db.execute(stmt)).scalars().all()
            return [model_to_record(row) for row in rows]
        if city:
            return await fetch_all("ambulances", where_clause="status = ? AND city = ?", params=("available", city))
        return await fetch_all("ambulances", where_clause="status = ?", params=("available",))

    async def update_status(self, id: str, status: str) -> None:
        if is_pg_session(self.db):
            await self.db.execute(update(Ambulance).where(Ambulance.id == id).values(status=status))
            await self.db.flush()
            return
        await update_record("ambulances", id, {"status": status})

    async def update_position(self, id: str, lat: float, lng: float) -> None:
        updates = {"current_lat": lat, "current_lng": lng}
        if is_pg_session(self.db):
            await self.db.execute(update(Ambulance).where(Ambulance.id == id).values(**updates))
            await self.db.flush()
            return
        await update_record("ambulances", id, updates)

    async def update(self, id: str, updates: dict[str, Any]) -> None:
        if is_pg_session(self.db):
            await self.db.execute(update(Ambulance).where(Ambulance.id == id).values(**serialize_for_model("ambulances", updates)))
            await self.db.flush()
            return
        await update_record("ambulances", id, updates)

    async def bulk_upsert(self, ambulances: list[dict[str, Any]]) -> None:
        if is_pg_session(self.db):
            for item in ambulances:
                await self.db.merge(Ambulance(**serialize_for_model("ambulances", item)))
            await self.db.flush()
            return
        for item in ambulances:
            existing = await fetch_one("ambulances", str(item["id"]))
            if existing:
                await update_record("ambulances", str(item["id"]), {k: v for k, v in item.items() if k != "id"})
            else:
                await insert_record("ambulances", item)
