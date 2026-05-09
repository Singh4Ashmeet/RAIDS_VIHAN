# RAID Nexus

Real-time Autonomous Incident Dispatch and Decision System for Indian city ambulance operations. The platform combines a React command center, FastAPI APIs, WebSocket live updates, deterministic AI fallbacks, optional ML/LLM explainability, and a PostgreSQL upgrade path while preserving local SQLite demo mode.

## Quick Start

```bash
git clone https://github.com/Singh4Ashmeet/RAIDS_VIHAN.git
cd RAIDS_VIHAN && cp .env.example .env
docker compose up --build
```

Open the frontend at `http://localhost:5173`, API docs at `http://localhost:8000/docs`, and health at `http://localhost:8000/health`.

## Manual Dev Startup

Backend:

```bash
python -m app.db.init_db
uvicorn app.main:app --reload --port 8000
```

Production-style backend command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

## Environment Variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLite URL for demo mode or PostgreSQL URL for production. |
| `POSTGRES_URL` | Optional alternate PostgreSQL URL. |
| `ENVIRONMENT` | `development`, `test`, or `production`. |
| `SECRET_KEY` | JWT signing secret. Replace before production. |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Demo admin login. Override in real deployments. |
| `USER_USERNAME`, `USER_PASSWORD` | Demo user login. Override in real deployments. |
| `CORS_ORIGINS` | Comma-separated browser origins. Use explicit origins in production. |
| `MODEL_PATH` | Optional dispatch or ETA model path. Missing models fall back safely. |
| `USE_LLM` | Enables optional LLM explanations when set to `true`. Default is `false`. |
| `OLLAMA_URL`, `OLLAMA_BASE_URL` | Optional local Ollama endpoint. |
| `OPENROUTER_API_KEY` | Optional OpenRouter key. Startup never requires it. |
| `ENABLE_NLP_TRIAGE`, `ENABLE_TRANSLATION` | Heavy model feature flags. Disable for lightweight deployments. |
| `RAID_LIGHTWEIGHT_TRIAGE` | Uses keyword triage path when enabled. |
| `RAID_DISABLE_SIMULATION` | Disables background simulation loop for tests and CI. |
| `TOMTOM_API_KEY`, `OSRM_URL` | Optional traffic/routing providers. |
| `VITE_API_BASE_URL`, `VITE_WS_URL` | Frontend REST and WebSocket targets. |

See [.env.example](./.env.example) for the full template.

## Architecture Overview

Frontend: React, Vite, Tailwind, and Zustand render the operator dashboard, map views, scenario tools, and live status panels. REST calls go through `frontend/src/services/api.ts`; live events use `frontend/src/services/socket.ts` or the existing store-level WebSocket fallback.

Backend: FastAPI serves `/api/*`, `/health`, `/ws/live`, and the built SPA. Existing routes remain under `backend/api`, while `app.main` provides the production entry point requested by Docker, CI, and deployment scripts.

AI and dispatch: The current scorer is preserved in `backend/services/dispatch.py`. `backend/services/dispatch_engine.py` adds stable service classes for ETA prediction, hospital scoring, ambulance allocation, explanations, and benchmark simulation with ML, heuristic, then random-valid fallback behavior.

Realtime: `backend/websocket/manager.py` standardizes events such as `INCIDENT_CREATED`, `DISPATCH_ASSIGNED`, `AMBULANCE_UPDATED`, `HOSPITAL_UPDATED`, `BENCHMARK_UPDATED`, and `HEARTBEAT`. Polling and previous lower-case payload fields remain for backward compatibility.

Data: SQLite remains the zero-config local path. PostgreSQL is enabled by `DATABASE_URL` and SQLAlchemy asyncpg. `python -m app.db.init_db` creates tables and loads seed data without deleting existing local data.

## Language Roles

TypeScript defines frontend contracts and service clients. Python owns FastAPI, dispatch logic, AI/ML fallbacks, seeding, and simulation. SQL/PostgreSQL provides production persistence and analytics. C++ is scaffolded as an optional optimizer. Java is scaffolded as a driver-client integration contract. C# is scaffolded as an optional external simulation runner.

## Demo Flow

1. Start the stack with Docker Compose or manual dev commands.
2. Open the frontend and submit an incident or SOS request.
3. The backend creates an incident, scores ambulances and hospitals, and returns a dispatch explanation.
4. Live clients receive WebSocket dispatch and map events.
5. Admin screens can inspect dispatch history, analytics, scenario runs, and override flows.

## Fallback Behavior

Missing ML models use deterministic distance/capacity heuristics. Failed heuristic allocation uses a random valid assignment and logs a warning. `USE_LLM=false` or any LLM failure uses the rule-based explanation generator. Missing C++ optimizer binaries fall back to Python logic. WebSocket reconnect is automatic on the frontend, and polling remains available where it already existed.

## Deployment Options

Render: the repo includes a production Blueprint in `render.yaml`. Push the repo, then open `https://dashboard.render.com/blueprint/new?repo=https://github.com/Singh4Ashmeet/RAIDS_VIHAN`, set the prompted admin/user passwords, and apply the Blueprint. It deploys one Docker web service and one managed Postgres database.

Docker VPS: run `docker compose up --build -d` with production `.env` values and a managed Postgres-compatible volume or service. For a public domain, set `VITE_API_BASE_URL`, `VITE_WS_URL`, and `CORS_ORIGINS` before building.

Lightweight production images use `requirements-prod.txt`, which excludes optional local NLP/translation packages. Use `--build-arg REQUIREMENTS_FILE=requirements.txt` only if you want the heavy offline AI stack inside the container.

Vercel: deploy the frontend only, set `VITE_API_BASE_URL` and `VITE_WS_URL` to the backend host.

## Testing

```bash
pytest tests/ -v --tb=short
python -m pytest backend/tests/ -v --tb=short
cd frontend && npm test -- --run && npm run build
```

## More Docs

- [Architecture](./ARCHITECTURE.md)
- [Production Checklist](./PRODUCTION.md)
- [API Contract](./API_CONTRACT.md)
- [Multi-language Modules](./MULTILANGUAGE_MODULES.md)
- [Contributing](./CONTRIBUTING.md)
- [Hardening Audit](./docs/production_hardening_audit.md)
