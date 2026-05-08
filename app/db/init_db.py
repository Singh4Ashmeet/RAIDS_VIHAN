"""Initialize RAID Nexus database tables and seed data.

Run from the repository root:

    python -m app.db.init_db
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import close_connection, initialize_database, load_seed_data  # type: ignore  # noqa: E402


async def run() -> dict[str, int]:
    """Create tables, load seed data, and return inserted row counts."""

    await initialize_database()
    inserted = await load_seed_data()
    await close_connection()
    return inserted


def main() -> None:
    inserted = asyncio.run(run())
    print(json.dumps({"status": "ok", "inserted": inserted}, ensure_ascii=True))


if __name__ == "__main__":
    main()
