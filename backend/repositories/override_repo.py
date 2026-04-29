"""Override request repository."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update

from database import get_connection, insert_record, update_record
from models.orm import DispatchAuditLog, OverrideRequest
from repositories._helpers import is_pg_session, model_to_record, serialize_for_model


class OverrideRepository:
    def __init__(self, db: Any = None):
        self.db = db

    async def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        if is_pg_session(self.db):
            row = OverrideRequest(**serialize_for_model("override_requests", payload))
            self.db.add(row)
            await self.db.flush()
            return model_to_record(row)
        await insert_record("override_requests", payload)
        return payload

    async def update(self, id: str, updates: dict[str, Any]) -> None:
        if is_pg_session(self.db):
            await self.db.execute(update(OverrideRequest).where(OverrideRequest.id == id).values(**updates))
            await self.db.flush()
            return
        await update_record("override_requests", id, updates)

    async def history(
        self,
        cutoff: str,
        city: str | None = None,
        incident_type: str | None = None,
        reason_category: str | None = None,
    ) -> list[dict[str, Any]]:
        if is_pg_session(self.db):
            stmt = (
                select(OverrideRequest, DispatchAuditLog)
                .join(DispatchAuditLog, OverrideRequest.audit_log_id == DispatchAuditLog.id, isouter=True)
                .where(OverrideRequest.requested_at >= cutoff)
            )
            if city:
                stmt = stmt.where(DispatchAuditLog.incident_city == city)
            if incident_type:
                stmt = stmt.where(DispatchAuditLog.incident_type == incident_type)
            if reason_category:
                stmt = stmt.where(OverrideRequest.reason_category == reason_category)
            stmt = stmt.order_by(OverrideRequest.requested_at.desc()).limit(100)
            rows = []
            for override, audit in (await self.db.execute(stmt)).all():
                payload = model_to_record(override)
                audit_payload = model_to_record(audit) if audit else {}
                payload.update(
                    {
                        "ai_eta_minutes": audit_payload.get("ai_eta_minutes"),
                        "final_eta_minutes": audit_payload.get("final_eta_minutes"),
                        "incident_city": audit_payload.get("incident_city"),
                        "incident_type": audit_payload.get("incident_type"),
                    }
                )
                rows.append(payload)
            return rows

        where_parts = ["override_requests.requested_at >= ?"]
        params: list[object] = [cutoff]
        if city:
            where_parts.append("dispatch_audit_log.incident_city = ?")
            params.append(city)
        if incident_type:
            where_parts.append("dispatch_audit_log.incident_type = ?")
            params.append(incident_type)
        if reason_category:
            where_parts.append("override_requests.reason_category = ?")
            params.append(reason_category)

        async with get_connection() as connection:
            cursor = await connection.execute(
                f"""
                SELECT
                    override_requests.*,
                    dispatch_audit_log.ai_eta_minutes,
                    dispatch_audit_log.final_eta_minutes,
                    dispatch_audit_log.incident_city,
                    dispatch_audit_log.incident_type
                FROM override_requests
                LEFT JOIN dispatch_audit_log
                    ON override_requests.audit_log_id = dispatch_audit_log.id
                WHERE {' AND '.join(where_parts)}
                ORDER BY override_requests.requested_at DESC
                LIMIT 100
                """,
                tuple(params),
            )
            return [dict(row) for row in await cursor.fetchall()]
