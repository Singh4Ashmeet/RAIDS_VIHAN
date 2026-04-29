"""Backend package bootstrap for repo-root imports.

The application is normally launched from this directory, where imports such
as ``from api.auth import router`` resolve naturally. Adding the backend
directory to ``sys.path`` also lets diagnostics and tooling import modules as
``backend.api.*`` from the repository root.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
backend_path = str(BACKEND_DIR)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)
