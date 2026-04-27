"""Shared FastAPI dependency providers.

Route modules use these functions to depend on infrastructure without
binding directly to implementation modules. The current repository layer is
function based for compatibility with the existing codebase; this module gives
new routes a stable dependency-injection boundary.
"""

from __future__ import annotations

from types import ModuleType

try:
    from repositories import database
except ModuleNotFoundError:  # pragma: no cover - package-style imports
    from backend.repositories import database


def get_database_repository() -> ModuleType:
    """Return the active database repository module."""

    return database
