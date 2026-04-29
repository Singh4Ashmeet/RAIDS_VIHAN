"""Notification repository for hospital pre-alerts."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from database import fetch_all, insert_record
from models.orm import Notification
from repositories._helpers import is_pg_session, model_to_record, serialize_for_model


class NotificationRepository:
    def __init__(self, db: Any = None):
        self.db = db

    async def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        if is_pg_session(self.db):
            row = Notification(**serialize_for_model("notifications", payload))
            self.db.add(row)
            await self.db.flush()
            return model_to_record(row)
        await insert_record("notifications", payload)
        return payload

    async def get_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        if is_pg_session(self.db):
            stmt = select(Notification).order_by(Notification.created_at.desc()).limit(limit)
            return [model_to_record(row) for row in (await self.db.execute(stmt)).scalars().all()]
        return (await fetch_all("notifications"))[:limit]
