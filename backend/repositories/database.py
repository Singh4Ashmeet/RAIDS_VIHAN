"""Compatibility shim for database helpers.

The implementation lives in ``backend/database.py`` so Alembic, legacy imports,
and repository modules share the same SQLAlchemy/SQLite runtime state.
"""

try:
    from database import *  # noqa: F401,F403
except ModuleNotFoundError:  # pragma: no cover - package-style imports
    from backend.database import *  # type: ignore  # noqa: F401,F403
