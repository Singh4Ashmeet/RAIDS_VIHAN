# Multi-language Modules

## Python Core

Python owns the FastAPI backend, repositories, dispatch engine, AI/ML services, simulation, seed loading, and tests. Start it with:

```bash
uvicorn app.main:app --reload --port 8000
```

## TypeScript Frontend

TypeScript contracts live in `frontend/src/types`. Centralized REST and WebSocket clients live in `frontend/src/services`.

```bash
cd frontend
npm run dev
```

## C++ Optimizer

The optional optimizer scaffold is in `optimizer_cpp`.

```bash
cd optimizer_cpp
cmake -B build
cmake --build build
```

`backend/services/cpp_adapter.py` uses an installed `raid_optimizer` binary when available and falls back to Python assignment logic otherwise. The C++ module reads `input.json` and writes `output.json` for route and assignment experiments.

## Java Driver Client

`mobile_driver_java` contains a minimal Java HTTP client and API contract for future Android driver workflows:

- `GET /api/driver/dispatches/{driver_id}`
- `POST /api/driver/location`
- `POST /api/driver/status`

## C# Simulation Tool

`simulation_csharp` contains a minimal .NET console simulation runner. It reads `API_BASE_URL` from `appsettings.json`, calls the backend REST API, and can be extended to generate repeatable N-scenario runs.

These optional modules are intentionally non-blocking. The main app must start and pass tests when they are absent.
