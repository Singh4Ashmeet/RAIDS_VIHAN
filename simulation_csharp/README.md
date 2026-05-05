# RAID Nexus C# Simulation Contract

This directory is a documentation scaffold for a future C#/.NET simulation or load-generation client. It contains no runnable .NET code.

The simulator should call only public HTTP API routes and should not import backend Python modules.

## Core Endpoints

- `GET /health` for service readiness.
- `POST /api/simulate/scenario` with `{ "type": "cardiac" | "overload" | "breakdown" | "traffic" }`.
- `POST /api/incidents` to create incidents with severity, city, and location.
- `POST /api/dispatch` to trigger dispatch for an incident.
- `GET /api/analytics` to read persisted dispatch analytics.

All `/api/*` responses use:

```json
{
  "status": "success",
  "message": "OK",
  "data": {}
}
```

## Scenario Expectations

Cardiac scenarios return a `dispatch_plan` and structured `explanation` under `data`. Invalid scenario types should return HTTP 422 with an error envelope.

Analytics should be checked after multiple dispatches to confirm persisted values survive backend restarts.

## WebSocket Events

The simulator may observe `WS /ws/live`, but it should not depend on WebSocket delivery for correctness checks. Use HTTP responses and `GET /api/analytics` as the durable verification path.
