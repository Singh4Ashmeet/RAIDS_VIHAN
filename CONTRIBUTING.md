# Contributing

## Safe Change Rules

1. Preserve existing routes, component names, startup commands, and data files.
2. Add new behavior behind small services, routes, or adapters before replacing old paths.
3. Keep SQLite local mode working whenever PostgreSQL code changes.
4. Keep optional ML, LLM, C++, Java, and C# modules non-blocking.
5. Never commit real secrets or patient PII.

## Local Checks

```bash
pytest tests/ -v --tb=short
python -m pytest backend/tests/ -v --tb=short
cd frontend && npm test -- --run && npm run build
```

## Adding An API

- Add a Pydantic request/response schema.
- Add the route under `backend/api`.
- Put business logic under `backend/services`.
- Preserve the canonical response envelope.
- Document the endpoint in `API_CONTRACT.md`.

## Adding Dispatch Logic

- Prefer extending `backend/services/dispatch_engine.py` service classes.
- Keep the fallback chain intact: model, deterministic heuristic, random valid assignment.
- Return explanations with selected ambulance, selected hospital, score breakdown, and rejected candidates.
- Add tests in `tests/test_dispatch_engine.py` or backend-specific tests.

## Frontend Changes

- Keep the dark RAID Nexus palette: `slate-900`, `slate-800`, `blue-500`, emerald, amber, and red.
- Use centralized services for API and WebSocket calls.
- Include loading, error, empty, and reconnect states for data-fetching UI.
- Guard map rendering when coordinates are absent.
