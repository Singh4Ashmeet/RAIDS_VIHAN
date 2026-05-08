# RAID Nexus Production Hardening Audit

## Phase 0 Repository Findings

- Repository root: `C:\Users\Ashmeet Singh AI\OneDrive\Desktop\RAIDS_VIHAN`.
- Frontend root: `frontend`; Vite entry points are `frontend/src/main.jsx` and `frontend/src/App.jsx`.
- Backend root: `backend`; current FastAPI entry point is `backend/main.py`; compatibility import style currently assumes running from `backend`.
- API routes: `backend/api/ambulances.py`, `backend/api/auth.py`, `backend/api/dispatch.py`, `backend/api/hospitals.py`, `backend/api/incidents.py`, `backend/api/overrides.py`, `backend/api/patients.py`, `backend/api/system.py`, `backend/api/websocket.py`, plus route registrations in `backend/main.py:596-625`.
- WebSocket logic: backend endpoint and broadcast helpers are in `backend/api/websocket.py:23-136`; ping loop is `backend/api/websocket.py:88-96`; frontend WebSocket connection/reconnect handling is in `frontend/src/store/dispatchStore.js:389-552`.
- Polling/fallback load logic: authenticated startup calls `connectWS()` and `fetchAll()` from `frontend/src/App.jsx:39-40`; REST fallback data loading is `frontend/src/store/dispatchStore.js:233-254`.
- ML model files: `backend/ml/delay_model.pkl`, `backend/ml/eta_drift_model.pkl`, `backend/ml/severity_model.pkl`; ML/training scripts are `backend/ml/train.py`, `backend/ml/synthetic_generator.py`, and `backend/scripts/benchmark.py`.
- Data files: `backend/data/ambulances.json`, `backend/data/hospitals.json`, `backend/data/incidents_seed.json`, CSV mirrors, benchmark JSON, synthetic/train/test incident JSON, and local SQLite files `backend/raid_nexus.db*`.
- Startup/deploy scripts: `start.py`, root `Dockerfile`, `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, `render.yaml`, `.github/workflows/ci.yml`; README documents `python start.py`.
- Package managers/config: Python uses `requirements.txt`, `backend/requirements.txt`, and `pyproject.toml`; frontend uses npm with `frontend/package.json` and `frontend/package-lock.json`; Vite/Tailwind configs are present.
- Environment/config: committed examples are `.env.example` and `backend/.env.example`; runtime config is `backend/core/config.py`; no committed real `.env` file was found in root or backend.
- Existing tests: backend tests live in `backend/tests` plus `backend/test_full_integration.py`; frontend tests live in `frontend/src/test` and include API, page, scenario, and WebSocket reconnect coverage.
- README/deployment docs: `README.md`, `docs/deployment.md`, `docs/production_architecture.md`, `docs/realtime_map_system.md`, plus ethics/security/user-guide docs.
- Optional modules already exist: `optimizer_cpp`, `mobile_driver_java`, and `simulation_csharp` each have initial documentation or source.

## 10-Line Internal Implementation Plan

1. Preserve the current `backend/main.py` entry point and add an `app.main` compatibility package instead of moving files.
2. Add missing backend compatibility modules only where imports or commands require them.
3. Introduce a reusable WebSocket `ConnectionManager` while keeping existing `/ws/live` behavior and lowercase event types.
4. Broadcast standardized uppercase event names alongside current event `type` aliases.
5. Add AI dispatch service classes as wrappers around existing scoring logic, not replacements.
6. Extend dispatch responses with structured `explanation` while preserving existing `explanation_text` and score fields.
7. Add database init command/schema coverage for requested tables without deleting local JSON or SQLite files.
8. Add frontend TypeScript types, `api.ts`, and `socket.ts` beside existing JS services to avoid import breakage.
9. Keep current polling/fetch fallback and add heartbeat/reconnect handling through a typed socket client.
10. Run backend and frontend tests/builds after surgical edits, then document any skipped risky migrations as TODOs.
