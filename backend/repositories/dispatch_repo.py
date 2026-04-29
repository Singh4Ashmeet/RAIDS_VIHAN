"""Dispatch repository for SQLite and PostgreSQL."""

from __future__ import annotations

from datetime import datetime
from statistics import mean
from typing import Any

from sqlalchemy import select, update

from core.config import KOLKATA_TZ
from database import fetch_all, fetch_one, insert_record, update_record
from models.orm import DispatchPlan
from repositories._helpers import is_pg_session, model_to_record, serialize_for_model


def _is_today_local(timestamp: str) -> bool:
    parsed = datetime.fromisoformat(timestamp)
    return parsed.astimezone(KOLKATA_TZ).date() == datetime.now(tz=KOLKATA_TZ).date()


class DispatchRepository:
    def __init__(self, db: Any = None):
        self.db = db

    async def create(self, plan: dict[str, Any]) -> dict[str, Any]:
        if is_pg_session(self.db):
            row = DispatchPlan(**serialize_for_model("dispatch_plans", plan))
            self.db.add(row)
            await self.db.flush()
            return model_to_record(row)
        await insert_record("dispatch_plans", plan)
        return plan

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        if is_pg_session(self.db):
            row = await self.db.get(DispatchPlan, id)
            return model_to_record(row) if row else None
        return await fetch_one("dispatch_plans", id)

    async def get_active(self) -> list[dict[str, Any]]:
        if is_pg_session(self.db):
            stmt = select(DispatchPlan).where(DispatchPlan.status == "active").order_by(DispatchPlan.created_at.desc())
            return [model_to_record(row) for row in (await self.db.execute(stmt)).scalars().all()]
        return await fetch_all("dispatch_plans", where_clause="status = ?", params=("active",))

    async def update_status(self, id: str, status: str) -> None:
        if is_pg_session(self.db):
            await self.db.execute(update(DispatchPlan).where(DispatchPlan.id == id).values(status=status))
            await self.db.flush()
            return
        await update_record("dispatch_plans", id, {"status": status})

    async def update(self, id: str, updates: dict[str, Any]) -> None:
        if is_pg_session(self.db):
            await self.db.execute(update(DispatchPlan).where(DispatchPlan.id == id).values(**serialize_for_model("dispatch_plans", updates)))
            await self.db.flush()
            return
        await update_record("dispatch_plans", id, updates)

    async def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        if is_pg_session(self.db):
            stmt = select(DispatchPlan).order_by(DispatchPlan.created_at.desc()).limit(limit)
            return [model_to_record(row) for row in (await self.db.execute(stmt)).scalars().all()]
        return (await fetch_all("dispatch_plans"))[:limit]

    async def get_analytics(self) -> dict[str, float | int]:
        dispatches = [item for item in await self.get_history(500) if _is_today_local(item["created_at"])]
        ai_eta_values = [float(item["eta_minutes"]) for item in dispatches]
        baseline_values = [
            float(item["baseline_eta_minutes"])
            for item in dispatches
            if item.get("baseline_eta_minutes") is not None
        ]
        avg_eta_ai = round(mean(ai_eta_values), 2) if ai_eta_values else 0.0
        avg_eta_baseline = round(mean(baseline_values), 2) if baseline_values else 0.0
        improvement_pct = (
            round(((avg_eta_baseline - avg_eta_ai) / avg_eta_baseline) * 100.0, 2)
            if avg_eta_baseline > 0
            else 0.0
        )
        return {
            "avg_eta_ai": avg_eta_ai,
            "avg_eta_baseline": avg_eta_baseline,
            "improvement_pct": improvement_pct,
            "dispatches_today": len(dispatches),
            "overloads_prevented": sum(1 for item in dispatches if item.get("overload_avoided")),
        }
