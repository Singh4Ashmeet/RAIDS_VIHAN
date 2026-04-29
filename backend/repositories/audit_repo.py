"""Audit repository for dispatch audit logs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from database import fetch_all, insert_record
from models.orm import DispatchAuditLog
from repositories._helpers import is_pg_session, model_to_record, serialize_for_model


class AuditRepository:
    def __init__(self, db: Any = None):
        self.db = db

    async def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        if is_pg_session(self.db):
            serialized = serialize_for_model("dispatch_audit_log", payload)
            if "metadata" in serialized:
                serialized["metadata_json"] = serialized.pop("metadata")
            row = DispatchAuditLog(**serialized)
            self.db.add(row)
            await self.db.flush()
            return model_to_record(row)
        await insert_record("dispatch_audit_log", payload)
        return payload

    async def get_trail(self, dispatch_id: str) -> list[dict[str, Any]]:
        if is_pg_session(self.db):
            stmt = (
                select(DispatchAuditLog)
                .where(DispatchAuditLog.dispatch_id == dispatch_id)
                .order_by(DispatchAuditLog.created_at.asc())
            )
            return [model_to_record(row) for row in (await self.db.execute(stmt)).scalars().all()]
        return await fetch_all("dispatch_audit_log", where_clause="dispatch_id = ?", params=(dispatch_id,))

    async def get_recent(self, cutoff: str, city: str | None = None) -> list[dict[str, Any]]:
        if is_pg_session(self.db):
            stmt = select(DispatchAuditLog).where(DispatchAuditLog.created_at >= cutoff)
            if city:
                stmt = stmt.where(DispatchAuditLog.incident_city == city)
            stmt = stmt.order_by(DispatchAuditLog.created_at.asc())
            return [model_to_record(row) for row in (await self.db.execute(stmt)).scalars().all()]
        where_parts = ["created_at >= ?"]
        params: list[Any] = [cutoff]
        if city:
            where_parts.append("incident_city = ?")
            params.append(city)
        return await fetch_all("dispatch_audit_log", where_clause=" AND ".join(where_parts), params=tuple(params))
