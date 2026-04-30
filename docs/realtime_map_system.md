# RAID Nexus Realtime Map System

## Folder Structure

```text
backend/
  api/websocket.py              # /ws/live snapshot feed with map context
  services/realtime_map.py      # route geometry, ambulance options, reroute events
  services/dispatch_service.py  # dispatch_created + dispatch_update broadcasts
  services/traffic.py           # traffic simulation override support
  simulation/engine.py          # ambulance ticks, scenario mutations, route_change events
  simulation/incident_sim.py    # incident_created + new_incident broadcasts

frontend/
  src/components/maps/
    RealtimeDispatchMap.jsx     # shared admin/user MapLibre realtime map
  src/store/dispatchStore.js    # WebSocket listeners and map state
  src/pages/admin/CommandCenter.jsx
  src/pages/user/DispatchStatus.jsx
  src/index.css                 # MapLibre controls and marker animations
```

## Free Map Stack

- `maplibre-gl` renders the map client-side with a Mapbox-compatible API.
- CARTO dark raster tiles are used for the dark basemap, with OpenStreetMap attribution.
- OSRM public routing is used for route polylines and ETAs where available.
- If OSRM is unavailable or rate-limited, the backend returns a deterministic fallback route so the UI keeps working.

No Mapbox or Google Maps API key is required.

## WebSocket Events

The map listens on the existing `/ws/live` connection and supports these events:

```text
state_snapshot               # initial ambulances, hospitals, incidents, active route context
simulation_tick              # periodic fleet/hospital refresh
ambulance_location_update    # 1-2 second smooth marker updates
incident_created             # backward-compatible incident event
new_incident                 # map-friendly incident event
dispatch_created             # backward-compatible dispatch event with map context
dispatch_update              # route, ETA, score, and ambulance option updates
route_change                 # old red dashed route + new animated green route
score_update                 # existing analytics update
scenario_triggered           # existing scenario event log integration
```

## Local Run

```bash
pip install -r requirements.txt
cd frontend
npm install
cd ..
python start.py
```

Open:

```text
http://127.0.0.1:5173/admin/command
http://127.0.0.1:5173/user/status
```

If Vite chooses another port, the backend now allows local dev ports through the default CORS regex.

## Using The Map

Admin:

1. Open Command Center.
2. Select or dispatch an incident.
3. Use the map's Real/Simulation switch.
4. In Simulation Mode, trigger Incident, Traffic, Breakdown, or Hospital Full scenarios.
5. Watch ambulance options, alternate routes, route changes, and demand heatmap overlays update live.

User:

1. Submit an SOS or use an active dispatch session.
2. Open My Status.
3. Track the assigned ambulance marker, user blue dot, route path, ETA, and status rail.

## Verification

Commands used:

```bash
npm run build
npm test -- --run
RAID_LIGHTWEIGHT_TRIAGE=true RAID_DISABLE_SIMULATION=true python -m pytest backend/tests -q --tb=short
python -m compileall backend/core backend/services backend/simulation backend/api
```
