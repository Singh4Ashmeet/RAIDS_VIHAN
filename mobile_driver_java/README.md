# RAID Nexus Mobile Driver Contract

This directory is a documentation scaffold for a future Java/Android ambulance driver app. It contains no runnable mobile code.

The mobile client should treat the FastAPI backend as the source of truth and use the standard API envelope:

```json
{
  "status": "success",
  "message": "OK",
  "data": {}
}
```

## Authentication

Use `POST /api/auth/login` with form fields:

- `username`
- `password`

Successful responses return token fields under `data`. Send the token on protected calls as:

```http
Authorization: Bearer <access_token>
```

## Driver Data Flow

Target driver endpoints:

- `GET /api/driver/dispatches/{driver_id}` for assignments scoped to one ambulance or driver identity.
- `POST /api/driver/location` with `{ "lat": 28.6139, "lng": 77.2090, "timestamp": "2026-05-08T10:00:00Z" }`.
- `POST /api/driver/status` with `{ "status": "en_route" | "on_scene" | "available" }`.

Current backend-compatible read endpoints:

- `GET /api/ambulances` for fleet state.
- `GET /api/incidents` for active incident context.
- `GET /api/hospitals` for receiving hospital state.
- `GET /api/patients/{id}` when a dispatch references a patient.

Recommended live channel:

- `WS /ws/live` for `state_snapshot`, `simulation_tick`, `dispatch_created`, and `hospital_notification` events.

The Android app should render dispatch state from API or WebSocket payloads without mutating assignment decisions locally.

## Error Handling

Any `status: "error"` envelope should be shown as a blocking workflow error. Any `status: "fallback"` envelope should be shown as an operational warning while still presenting the returned `data`.

## Minimal Java Client

`src/main/java/in/raidnexus/driver/DriverClient.java` is a small Java 11 HTTP client scaffold that documents auth and read calls without requiring Android tooling in this repository.
