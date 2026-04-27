"""Compatibility shim for legacy imports.

New backend code should import from ``repositories.database``.
"""

from repositories.database import *  # noqa: F401,F403

