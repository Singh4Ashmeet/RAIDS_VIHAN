# RAID Nexus

Real-time Autonomous Incident Dispatch and Decision System built for the Vihan 9.0 hackathon.

RAID Nexus is a full-stack emergency response platform that simulates how an intelligent dispatch center can triage incoming medical emergencies, allocate ambulances, recommend hospitals, and stream live operational updates to both operators and end users.

## Overview

The project combines a FastAPI backend, a React + Vite frontend, live WebSocket updates, seeded simulation data, rule-based triage, scoring-based dispatch, and optional LLM-generated explanations for dispatch decisions.

It is designed to demonstrate:

- faster ambulance and hospital allocation
- explainable dispatch recommendations
- live monitoring for admins and operators
- citizen-facing SOS and status tracking workflows
- scenario simulation for traffic spikes, overloads, and breakdowns

## Responsible AI

RAID Nexus is designed as an AI-assisted decision support tool. All dispatch recommendations are subject to human review. See [Ethical Framework](docs/ethics.md) for full details.

## Data & Methodology

Incident data is synthetically generated and calibrated to published Indian EMS statistics. See [Data Methodology](docs/data_methodology.md) for sources, validation, and limitations.

### Reproduce the Data

```bash
python backend/scripts/generate_incidents.py --count 500 --seed 42
python backend/scripts/validate_synthetic_data.py
python backend/scripts/benchmark.py
```

## Key Features

- Dual portal experience: admin dashboard plus user emergency workflow
- Smart dispatch pipeline for ambulance, hospital, and route selection
- Explainability output for why a dispatch decision was made
- Live WebSocket feed for ambulance, hospital, and scenario state updates
- Built-in simulation engine for operational changes over time
- Scenario lab for cardiac emergencies, traffic surges, overloads, and ambulance outages
- Analytics endpoint for daily dispatch and overload metrics
- Seeded demo environment with ambulances, hospitals, and incidents
- ML data generation utilities for synthetic training data
- Optional Ollama-based explanation generation with deterministic fallback

## Product Modules

### Admin Side

- Command Center for monitoring dispatches and operational state
- Fleet view for ambulances and hospital capacity
- Analytics dashboard for dispatch activity and overload prevention
- Scenario Lab for triggering demo events and observing effects

### User Side

- Emergency SOS intake flow
- Patient dispatch tracking
- Hospital finder workflow

## System Architecture

```text
React + Vite frontend
        |
        | HTTP (/api/*) + WebSocket (/ws/live)
        v
FastAPI backend
        |
        +-- Triage service
        +-- Dispatch scoring service
        +-- Geo and route scoring
        +-- Notification service
        +-- Simulation engine
        +-- LangGraph dispatch workflow
        +-- SQLite persistence
        +-- Optional Ollama explanation generation
```

## Tech Stack

### Frontend

- React 19
- Vite
- Vitest
- Testing Library

### Backend

- FastAPI
- Uvicorn
- Pydantic
- SQLite with `aiosqlite`
- LangGraph
- `httpx`
- `geopy`
- NumPy, Pandas, Scikit-learn, SciPy, XGBoost, Joblib

## Project Structure

```text
RAIDS_VIHAN/
|-- backend/
|   |-- api/             # REST and WebSocket routes
|   |-- agents/          # LangGraph-based dispatch workflow
|   |-- data/            # Seed data for ambulances, hospitals, incidents
|   |-- ml/              # Synthetic data generation and ML utilities
|   |-- models/          # Pydantic response and domain models
|   |-- services/        # Dispatch, scoring, geo, triage, notifications
|   |-- simulation/      # Background simulation engine
|   |-- tests/           # Backend smoke tests
|   |-- config.py
|   |-- database.py
|   `-- main.py
|-- frontend/
|   |-- src/
|   |   |-- admin/       # Admin-facing views
|   |   |-- context/     # Live WebSocket state management
|   |   |-- services/    # Frontend API client helpers
|   |   |-- shared/      # Reusable UI components
|   |   |-- test/        # Frontend test suite
|   |   `-- user/        # User-facing flows
|   |-- package.json
|   `-- vite.config.js
|-- start.py             # Unified launcher for backend + frontend
|-- requirements.txt     # Root Python dependency list
`-- README.md
```

## Seeded Demo Data

On startup, the backend initializes a local SQLite database and loads demo records. The current smoke tests expect:

- 15 ambulances
- 10 hospitals
- 50 incidents

## Dispatch Pipeline

The dispatch engine follows a staged flow:

1. intake incident and patient context
2. triage severity and incident type
3. score ambulance candidates
4. score hospital candidates
5. evaluate route quality and ETA
6. allocate the best dispatch plan
7. generate a human-readable explanation

The workflow is implemented with LangGraph and returns score-aware dispatch output including rejected alternatives and explanation text.

## API Overview

### Core Routes

- `GET /health` - backend liveness check
- `GET /docs` - interactive Swagger documentation
- `GET /api/ambulances` - list ambulance fleet data
- `GET /api/hospitals` - list hospitals and capacity status
- `GET /api/incidents` - list incidents
- `POST /api/incidents` - create a new incident
- `POST /api/patients` - create a patient intake request and trigger dispatch
- `GET /api/patients/{patient_id}` - fetch patient plus assigned resources
- `POST /api/dispatch` - manually trigger dispatch for an incident
- `GET /api/dispatch/{dispatch_id}` - fetch a saved dispatch plan
- `GET /api/analytics` - daily dispatch and overload metrics
- `POST /api/simulate/scenario` - trigger a demo scenario
- `WS /ws/live` - receive state snapshots and live operational events

### Scenario Types

The simulation endpoint supports:

- `cardiac`
- `traffic`
- `overload`
- `breakdown`

## Live Updates

The frontend connects to `/ws/live` and receives:

- initial state snapshot
- simulation tick updates
- new dispatch events
- hospital notification events

Vite is already configured to proxy both `/api` and `/ws` traffic to the backend during local development.

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm

### 1. Install Dependencies

Install backend Python packages from the repo root:

```bash
pip install -r requirements.txt
```

Install frontend packages:

```bash
cd frontend
npm install
```

### 2. Run the Full Stack

The easiest way to start everything is the unified launcher:

```bash
python start.py
```

Default local URLs:

- frontend: `http://localhost:3000`
- backend API docs: `http://localhost:8000/docs`

### 3. Run Services Manually

Backend:

```bash
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm run dev
```

## Testing

### Backend

```bash
cd backend
python -m unittest tests.test_smoke -v
```

### Frontend

```bash
cd frontend
npm test
```

## Configuration

The backend supports runtime overrides through environment variables:

- `RAID_NEXUS_DB_PATH` - custom SQLite database location
- `RAID_NEXUS_TRAINING_DATA_PATH` - custom output path for generated ML data

## Explainability and LLM Fallback

Dispatch explanations can optionally use a local Ollama endpoint:

- default URL: `http://localhost:11434/api/generate`
- default model: `mistral`

If Ollama is unavailable, the system falls back to a deterministic explanation so the dispatch workflow still completes.

## Development Notes

- frontend API requests are proxied through Vite to `localhost:8000`
- backend state is persisted in SQLite
- simulation ticks run in the background after FastAPI startup
- analytics are calculated for the current local day using the configured timezone

## Suggested Demo Flow

1. Start the stack with `python start.py`
2. Open the admin portal and review command center status
3. Switch to the user portal and submit an SOS request
4. Observe dispatch creation and status updates
5. Trigger scenario events from Scenario Lab
6. Review analytics and hospital notifications

## Practical Next Improvements

- Add basic admin and user authentication with protected frontend views and secured API routes
- Show ambulances, incidents, and hospitals on an interactive city map using the existing latitude and longitude data
- Store dispatch history, scenario triggers, and notifications in a searchable audit log screen
- Improve the dispatch explanation panel by surfacing score breakdowns and rejected-option reasons directly in the UI
- Expand backend and frontend automated tests to cover patient dispatch, scenario simulation, and WebSocket updates end to end
- Package the project with Docker and add a simple CI workflow for install, lint, and test checks

## License

This repository currently does not define a license file. Add one before public distribution if needed.
