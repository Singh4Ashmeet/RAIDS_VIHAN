"""User repository for authentication."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from database import fetch_one
from models.orm import User
from repositories._helpers import is_pg_session, model_to_record


class UserRepository:
    def __init__(self, db: Any = None):
        self.db = db

    async def get_by_username(self, username: str) -> dict[str, Any] | None:
        if is_pg_session(self.db):
            stmt = select(User).where(User.username == username)
            row = (await self.db.execute(stmt)).scalars().first()
            return model_to_record(row) if row else None
        return await fetch_one("users", username, id_field="username")
