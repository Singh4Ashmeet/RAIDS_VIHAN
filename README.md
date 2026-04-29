# RAID Nexus - Real-time AI Emergency Dispatch

## Problem Statement
India's EMS systems still struggle with fragmented call intake, uneven ambulance distribution, overloaded hospitals, and dispatch decisions that often depend on incomplete operator context. In many cities, response times can stretch into the 17-40 minute range, especially when traffic, hospital diversion, and specialty capacity are not considered together. RAID Nexus demonstrates an AI-assisted dispatch layer that triages emergencies, scores ambulances and hospitals, streams live state, and keeps a human operator in control.

## Live Demo
Live app: https://raid-nexus.onrender.com

Demo credentials: Admin: `admin/admin123` | User: `user/user123`

Demo flow:
1. Open `https://raid-nexus.onrender.com/user/sos`.
2. Submit an emergency SOS form.
3. Watch the dispatch get created and shown in real time.
4. Open `/admin` or `/admin/command` to see Command Center update live.
5. Trigger Scenario Lab events from `/admin/scenarios`.

## Architecture
```text
React/Vite frontend
  |  HTTPS /api/*
  |  WebSocket /ws/live
  v
FastAPI backend on Render
  |-- API routes
  |-- Auth, rate limiting, response envelopes
  |-- Dispatch services and LangGraph workflow
  |-- NLP triage, translation, anomaly and fairness modules
  |-- Scenario simulation engine
  |-- Repository layer
  v
PostgreSQL on Neon via SQLAlchemy async + asyncpg
  |
  +-- SQLite via aiosqlite for zero-config local development
```

## Key Features
| Feature | Status | Description |
|---|---:|---|
| SOS intake | ✓ Implemented | User form creates patient, incident, dispatch, and tracking state. |
| Command Center | ✓ Implemented | Admin view monitors incidents, dispatch plans, score breakdowns, and live feed state. |
| WebSocket live feed | ✓ Implemented | Streams snapshots, simulation ticks, dispatches, scenarios, overrides, and anomaly events. |
| PostgreSQL migration | ✓ Implemented | Async SQLAlchemy/asyncpg path with SQLite fallback and Alembic scaffolding. |
| Repository layer | ✓ Implemented | Ambulance, hospital, incident, dispatch, patient, audit, notification, override, and user data access. |
| Audit log and overrides | ✓ Implemented | Human override requests, history, stats, and dispatch audit trail. |
| Hospital pre-alerts | ✓ Implemented | Dispatch creates hospital notification payloads with preparation checklist. |
| JWT auth | ✓ Implemented | Login, `/auth/me`, admin-only override routes, and WebSocket token validation. |
| NLP triage | ✓ Implemented | Feature-flagged NLP with keyword fallback for Render free tier. |
| Translation | ✓ Implemented | Feature-flagged offline translation fallback path. |
| Anomaly detection | ✓ Implemented | Configurable anomaly flagging and live anomaly events. |
| Rate limiting | ✓ Implemented | SlowAPI limits on sensitive routes. |
| Fairness benchmarking | ✓ Implemented | Benchmark output includes fairness metrics and cross-city flags. |
| Demand heatmap | ✓ Implemented | Admin demand heatmap page backed by generated demand data. |
| Production observability | 🚧 In Progress | Timing middleware exists; metrics/log aggregation can be expanded. |

## Ethical Framework
See [docs/ethics.md](docs/ethics.md). RAID Nexus is designed as decision support, not an autonomous replacement for emergency operators. The system surfaces confidence, reasons, alternatives, and override history so humans can audit and correct AI recommendations.

## AI/ML Pipeline
The pipeline starts with SOS text and structured patient data, then runs triage classification, optional NLP confidence scoring, optional translation, anomaly checks, dispatch scoring, hospital suitability scoring, route/ETA scoring, fairness reporting, and benchmark comparison against nearest-unit and random baselines. Heavy NLP and translation models are controlled by feature flags so production free-tier deployments can fall back to lightweight keyword triage.

## Setup - Local (SQLite, zero config)
```bash
git clone https://github.com/Singh4Ashmeet/RAIDS_VIHAN.git
cd RAIDS_VIHAN
pip install -r requirements.txt
python start.py
```

Open:
- Frontend: `http://localhost:3000/user/sos`
- Backend docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

## Setup - Production (PostgreSQL on Neon)
1. Create a Neon account at https://neon.tech.
2. Create a database and copy the connection string.
3. Set `DATABASE_URL` to `postgresql+asyncpg://user:pass@host/dbname?ssl=require`.
4. Deploy to Render with the included `render.yaml`.

## Environment Variables
| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./raid_nexus.db` | PostgreSQL URL in production; SQLite fallback locally. |
| `POSTGRES_URL` | empty | Optional alternate PostgreSQL URL. |
| `ENVIRONMENT` | `development` | Use `production` on Render. |
| `SECRET_KEY` | `dev-secret-change-in-production` | JWT signing secret. Replace in production. |
| `ALGORITHM` | `HS256` | JWT algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | Session duration. |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | `admin` / `admin123` | Demo admin credentials; override in production. |
| `USER_USERNAME` / `USER_PASSWORD` | `user` / `user123` | Demo user credentials; override in production. |
| `TOMTOM_API_KEY` | empty | Optional traffic provider key. |
| `OSRM_URL` | `http://router.project-osrm.org` | Routing backend URL. |
| `BACKEND_PORT` | `8000` | Local backend port. |
| `FRONTEND_PORT` | `3000` | Local frontend port. |
| `CORS_ORIGINS` | localhost + Render URL | Allowed browser origins. |
| `ENABLE_NLP_TRIAGE` | `true` | Disable on Render free tier to avoid large model memory use. |
| `ENABLE_TRANSLATION` | `true` | Disable on Render free tier. |
| `ENABLE_ANOMALY_DETECTION` | `true` | Enables anomaly checks. |
| `RAID_FORCE_SQLITE` | `false` | Force SQLite even if PostgreSQL is configured. |
| `RAID_DISABLE_SIMULATION` | `false` | Disable background simulation loop. |

## Evaluation Results
| Run | Dataset | AI ETA | Baseline ETA | Improvement | Fairness |
|---|---|---:|---:|---:|---|
| Held-out benchmark | `test_incidents.json` | Run `backend/scripts/benchmark.py --split test` | TBD | TBD | TBD |
| Cross-city benchmark | synthetic city split | Run `backend/scripts/benchmark.py --mode cross_city` | TBD | TBD | TBD |

## Known Limitations
- Demo data is synthetic and calibrated, not real EMS operational data.
- Dispatch scoring is decision support and still requires human oversight.
- Public OSRM routing can rate-limit local tests; fallback ETA logic keeps flows working.
- Render free tier memory is too small for heavier NLP/translation models.
- Auth is demo-grade and should be integrated with a managed identity provider for real deployments.
- SQLite local mode is convenient but does not model production concurrency.
- Hospital capacity values are simulated and should be replaced with verified feeds before real-world use.

## Research Citations
| Study | Year | Method | Reported improvement |
|---|---:|---|---:|
| Liu et al., "Dynamic ambulance redeployment and dispatching" | 2019 | Approximate Dynamic Programming | 22.4% |
| Schmid, "Solving the dynamic ambulance relocation problem" | 2012 | Robust optimization | 18.7% |
| Kergosien et al., "Generic model for online optimization of EMS" | 2015 | Online optimization heuristic | 31.2% |
| Maxwell et al., "Approximate dynamic programming for EMS" | 2010 | Approximate Dynamic Programming | 26.8% |

## Testing
```bash
python -m pytest backend/tests/ -v --tb=short
cd frontend
npm test -- --run
npm run build
```

## License
MIT
