# API Contract

All normal responses use:

```json
{"status": "success", "message": "OK", "data": {}}
```

Errors use a stable JSON shape with a human-safe message.

## Health

`GET /health`

Response includes `status`, `timestamp`, `version`, service readiness, and database backend details.

## Incidents

`POST /api/incidents`

```json
{
  "type": "cardiac",
  "severity": "critical",
  "patient_count": 1,
  "location_lat": 28.6139,
  "location_lng": 77.209,
  "city": "Delhi",
  "description": "Severe chest pain"
}
```

Returns `201` with `incident` and `dispatch_plan`. `dispatch_plan.explanation` contains `selected_ambulance`, `selected_hospital`, `score_breakdown`, and `rejected`.

`GET /api/incidents`

Lists recent incidents. Optional query: `status=open|dispatched|resolved`.

## Dispatch

`POST /api/dispatch`

```json
{"incident_id": "INC-001"}
```

Runs dispatch scoring for an existing incident. Rate limited to `10/minute`.

`GET /api/dispatch/{dispatch_id}`

Returns a saved dispatch with structured `explanation`.

## Realtime

`GET /ws/live`

WebSocket events include both legacy lower-case `type` fields and standard uppercase `event` names where applicable.

Standard event names:

- `INCIDENT_CREATED`
- `DISPATCH_ASSIGNED`
- `AMBULANCE_UPDATED`
- `HOSPITAL_UPDATED`
- `BENCHMARK_UPDATED`
- `HEARTBEAT`

Clients should respond to `HEARTBEAT` with `HEARTBEAT_ACK` when supported.

## Driver Client

`GET /api/driver/dispatches/{driver_id}`

Returns dispatches for a driver or ambulance id.

`POST /api/driver/location`

```json
{"driver_id": "AMB-001", "lat": 28.61, "lng": 77.2, "timestamp": "2026-05-08T10:00:00Z"}
```

`POST /api/driver/status`

```json
{"driver_id": "AMB-001", "status": "en_route"}
```

Allowed statuses: `en_route`, `on_scene`, `available`.

## Analytics And Admin

Existing backward-compatible routes remain under `/api`, including auth, patients, ambulances, hospitals, overrides, scenarios, analytics, benchmark, fairness, literature comparison, anomalies, translation status, and demand heatmap.
