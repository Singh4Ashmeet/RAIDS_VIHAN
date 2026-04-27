# RAID Nexus System Walkthrough

## 1. Purpose

This document explains how RAID Nexus works as a complete system. It is written as an operational walkthrough for developers, evaluators, and reviewers who need to understand every major page, backend function group, dispatch workflow, simulation, and data flow without reading the entire codebase first. It complements the architecture, ethics, security, multilingual, and data methodology documents by describing the live behavior of the application step by step.

RAID Nexus is an AI-assisted emergency dispatch prototype. The user-facing portal collects emergency reports, the backend triages those reports, the dispatch engine scores ambulance and hospital options, and the admin command center lets dispatchers review recommendations, run simulations, and override decisions. The system is intentionally built as decision support: recommendations are generated automatically, but administrative workflows keep humans in the loop.

## 2. Runtime Overview

The application has three main runtime layers.

| Layer | Location | Responsibility |
|---|---|---|
| Frontend | `frontend/src` | React application, login, SOS portal, admin command center, simulations, analytics, heatmap, and WebSocket state updates. |
| Backend API | `backend/main.py`, `backend/api` | FastAPI app, authentication, route registration, protected admin APIs, incident intake, dispatch preview, system scenarios, and static frontend hosting. |
| Backend Services | `backend/services`, `backend/simulation`, `backend/scripts` | Dispatch scoring, triage, routing, traffic, audit logging, anomaly detection, demand prediction, fairness metrics, data generation, benchmarks, and simulation engine. |

The deployed Render version can run in a lighter mode. `RAID_LIGHTWEIGHT_TRIAGE=1` avoids preloading large NLP and translation models during startup. `RAID_DISABLE_SIMULATION=1` disables the continuous background simulation loop, but the manual Scenario Lab still works because the simulation engine object is still created. This keeps the hosted demo responsive while preserving the interactive scenario functions.

## 3. Application Startup

Startup is coordinated in `backend/main.py`. The FastAPI app is created through `create_app()`, which attaches middleware, registers routers, exposes direct API endpoints, mounts the frontend build, and installs the fallback route for the single-page React app.

The startup sequence is:

1. A dedicated CPU thread pool is created with four workers. This prevents CPU-heavy work from blocking the async event loop when functions use `asyncio.to_thread()`.

2. The lifespan handler initializes the event loop executor and logs that the CPU pool is ready.

3. The database is initialized through `initialize_database()` in `backend/repositories/database.py`. Tables are created or migrated, boolean conversion fields are registered, and default users are seeded if the users table is empty. Legacy imports through `backend/database.py` remain as a compatibility shim, but new backend modules use the repository layer directly.

4. Seed data is loaded through `load_seed_data()`. Hospitals and ambulances are inserted or updated from the seed files so the demo always has fleet and hospital capacity.

5. NLP and translation model warmup may be started in the background. In normal mode, the NLP classifier and Hindi translation model can preload asynchronously. In lightweight mode, this is skipped so startup does not wait on model downloads.

6. The demand predictor builds its training density grid from `backend/data/train_incidents.json`. The test set is intentionally held out for evaluation.

7. A `SimulationEngine` instance is created. If background simulation is enabled, `engine.start()` launches the recurring simulation loop. If it is disabled, the engine remains available for manual scenario execution.

8. On shutdown, the background simulation is stopped if it was running, the database connection is closed, and the CPU thread pool is shut down cleanly.

## 4. Database and Core Records

The backend uses PostgreSQL through an `asyncpg` pool when `DATABASE_URL` is configured. If no PostgreSQL URL is set, it falls back to SQLite through a single shared `aiosqlite` connection for local development. This keeps the project easy to run locally while allowing the hosted deployment to use a managed Postgres database.

The important tables are:

| Table | Purpose |
|---|---|
| `users` | Stores JWT login users with bcrypt password hashes, roles, active state, and UUID IDs. |
| `patients` | Stores user-submitted patient records and report descriptions. |
| `incidents` | Stores emergency incidents, triage outputs, review flags, language metadata, translation metadata, anomaly flags, location, status, and timestamps. |
| `ambulances` | Stores fleet location, status, equipment type, crew readiness, and current assignment state. |
| `hospitals` | Stores hospital location, specialty, capacity, ER wait time, diversion state, and occupancy. |
| `dispatches` | Stores dispatch plans, selected ambulance and hospital, ETA, score breakdown, route metadata, explanation text, and status. |
| `dispatch_audit_log` | Stores audit events for AI dispatches, human overrides, and fallback decisions. |
| `override_requests` | Stores override requests, mandatory reasons, selected replacement resources, and review metadata. |

The incident model is central. It carries the dispatch-critical fields `type`, `severity`, `lat`, `lng`, `city`, and `status`, plus safety and research fields such as `triage_confidence`, `requires_human_review`, `review_reason`, `triage_version`, `language_detected`, `language_name`, `original_complaint`, `translated_complaint`, `translation_model`, `has_anomaly`, and `anomaly_flags`.

## 5. Authentication Flow

Authentication is handled by `backend/api/auth.py`.

The backend stores users in the database, not in source code. During startup, default admin and user accounts are seeded from environment configuration if no users exist. Passwords are hashed with passlib bcrypt.

Login works as follows:

1. The frontend submits a username and password to `POST /api/auth/login` as form data.

2. The backend fetches the user row by username.

3. If the user does not exist, the password does not match, or the account is disabled, the endpoint rejects the login.

4. If login succeeds, `create_access_token()` signs a JWT with the username in `sub`, the role in `role`, and an expiry timestamp.

5. The frontend stores the token, role, and username in Zustand state and localStorage.

6. Axios attaches `Authorization: Bearer <token>` to API requests.

7. `get_current_user()` decodes the JWT and fetches the current user from the database.

8. `get_current_admin()` allows only users with the `admin` role.

The WebSocket path also uses JWT authentication. The frontend connects with the token in the query string. The backend calls `verify_ws_token()` before accepting the connection. Invalid or expired tokens are closed with WebSocket close code `1008`.

## 6. Frontend Navigation

The React application is organized around authenticated routes in `frontend/src/App.jsx`. Legacy non-routed admin and user folders have been removed; all live screens now sit under `frontend/src/pages`, reusable UI sits under `frontend/src/components`, layouts sit under `frontend/src/layouts`, API clients sit under `frontend/src/services`, and application state sits under `frontend/src/store`.

| Route | Page | Purpose |
|---|---|---|
| `/` | `LandingPage` | Public entry page with links to login and SOS. |
| `/login` | `LoginPage` | Username/password login with password visibility toggle. |
| `/user/sos` | `SOSPortal` | User emergency report form with voice input and automatic priority detection. |
| `/user/status` | `DispatchStatus` | User-facing dispatch status screen. |
| `/user/hospitals` | `HospitalFinder` | User-facing hospital discovery view. |
| `/admin/command` | `CommandCenter` | Main dispatcher workspace with incidents, dispatch plan, fleet status, review alerts, anomaly alerts, and override controls. |
| `/admin/fleet` | `FleetHospitals` | Ambulance and hospital operational view. |
| `/admin/analytics` | `Analytics` | Benchmark, fairness, and literature comparison results. |
| `/admin/scenario` | `ScenarioLab` | Manual simulation and resilience testing. |
| `/admin/heatmap` | `DemandHeatmap` | Demand hotspot grid and prepositioning recommendations. |

The frontend state is split mainly between two stores. `authStore` owns login, logout, token hydration, and session validation. `dispatchStore` owns incidents, dispatches, ambulances, hospitals, notifications, anomaly alerts, override state, initial data fetching, and the WebSocket connection.

## 7. SOS Intake Flow

The main user emergency intake flow starts in `frontend/src/pages/user/SOSPortal.jsx`.

The user enters or dictates a report. The page supports voice capture through the browser speech recognition API when available. The report is analyzed on the client for priority intent so the UI can turn Priority SOS on automatically when the full report appears critical. The intended behavior is not a simple one-word switch. The report text is scanned for emergency meaning across phrases such as chest pain, breathing difficulty, unconsciousness, stroke signs, severe bleeding, and comparable high-risk signals. When the report indicates a critical emergency, the UI enables priority mode and explains that priority was enabled from the report.

When submitted:

1. `SOSPortal` sends the patient/report payload through the API service.

2. `backend/api/patients.py` receives the request.

3. The backend sanitizes and validates fields according to the model and route rules.

4. The backend calls the triage pipeline to classify incident type, severity, required ambulance level, review status, language, and translation metadata.

5. `build_incident_payload()` in `backend/simulation/incident_sim.py` turns the patient report and triage result into an incident insert payload.

6. `create_incident()` inserts the incident into the database.

7. The new incident is broadcast to admin clients as `incident_created`.

8. Dispatch execution may then create a dispatch recommendation, depending on the calling flow.

The incident feed in the command center shows review indicators when `requires_human_review` is true. If language information is available and the language is not English, the card also shows a language badge.

## 8. Triage Pipeline

The modern triage path is in `backend/services/nlp_triage.py`.

The public function is `triage_incident(complaint, city=None, sos_mode=False)`. It returns a dict with the dispatch-critical fields `incident_type`, `severity`, `ambulance_type_required`, `requires_human_review`, `review_reason`, `type_classification`, `severity_classification`, `resource_requirement`, `triage_confidence`, and `triage_version`. It can also include `language_detection` and `translation`.

The step-by-step flow is:

1. Language detection runs first through `backend/services/language_detector.py`.

2. If the text is confidently English, the normal NLP path runs.

3. If the text is confidently non-English and supported by the offline translator, `translate_to_english()` translates it to English, then the NLP classifier runs on the translated text. The result is always flagged for human review because emergency-domain translation quality has not been clinically validated.

4. If translation fails, the system falls back to the keyword triage service and marks the result for human review.

5. If language detection is unreliable, NLP can still run, but review is forced.

6. Incident type classification uses a zero-shot classifier when enabled. In lightweight mode, the classifier can fall back to a keyword-style implementation to avoid loading large models.

7. Severity classification first checks safety signals, then can use zero-shot severity labels. Critical and high signals take precedence.

8. Resource requirement rules select ALS or BLS. When classification confidence is low, the system escalates to ALS for safety.

9. Exceptions are caught and logged. The old keyword triage service remains available as a fallback.

The fallback service in `backend/services/triage_service.py` includes English keywords and selected Hindi/Urdu transliterated safety terms such as chest pain, breathing difficulty, unconsciousness, fainting, heart attack, no pulse, head injury, blood, dizziness, pain, and high fever. This does not provide full multilingual triage; it is a safety net.

## 9. Dispatch Pipeline

The dispatch scoring engine is in `backend/services/dispatch.py`. The higher-level execution pipeline is in `backend/services/dispatch_service.py`.

The core dispatch function is `select_dispatch(incident, ambulances, hospitals, weights=None)`.

The dispatch pipeline works as follows:

1. The incident location, type, severity, city, and review fields are read.

2. Available ambulances and open hospitals are gathered from the database.

3. Routing calls estimate ambulance-to-scene ETA and scene-to-hospital ETA. Routing uses `backend/services/routing.py`, which can use OSRM-style route calls and fall back to Haversine estimates when external routing is unavailable.

4. Traffic multipliers are provided by `backend/services/traffic.py` and `backend/services/geo_service.py`. Traffic can be heuristic, cached, or externally derived depending on configuration.

5. All ambulance-hospital pair scores are computed. The scoring weights are ETA `0.40`, specialty match `0.25`, crew readiness `0.15`, capacity `0.10`, and ER wait `0.10`.

6. Specialty scoring checks whether the hospital matches the incident need. Cardiac and stroke incidents benefit from cardiac or multi-specialty hospitals. Trauma and accident incidents benefit from trauma or multi-specialty hospitals.

7. The best scoring pair becomes the AI recommendation.

8. The result includes the selected ambulance, hospital, ETA, score breakdown, baseline ETA comparison, weighted explanation text, route geometry when available, and safety metadata.

9. `full_dispatch_pipeline()` stores the dispatch, updates incident and patient state, logs the AI dispatch audit event, notifies hospital workflow, and broadcasts `dispatch_created`.

If the main scoring path fails or no ideal pair is available, fallback selection chooses a reasonable available ambulance and hospital so the system degrades safely instead of returning no response.

## 10. Human Override and Audit

The override system is in `backend/api/overrides.py`.

A dispatcher can request an override when they believe another ambulance or hospital is more appropriate. The override endpoint requires admin authentication, an active dispatch, an available replacement ambulance, an open non-diversion hospital, different selected resources, and a reason of valid length.

The flow is:

1. The admin selects replacement resources in the command center.

2. The frontend sends the override request with the dispatch ID, replacement IDs, and reason.

3. The backend validates that the dispatch is active.

4. The backend validates ambulance availability and hospital capacity/diversion state.

5. The backend updates the dispatch final choice and related resource state.

6. `log_human_override()` writes the audit event with the authenticated database user UUID.

7. A WebSocket event notifies connected admin clients.

The audit service records AI choice, final choice, actor ID, reason, incident context, score data, timestamp, and metadata. AI-generated dispatches use actor ID `system`, while human override events use the current authenticated user ID.

## 11. WebSocket Flow

The live update system is in `backend/api/websocket.py`.

The frontend calls `dispatchStore.connectWS()`. The store reads `raid_token` from localStorage, appends it as a `token` query parameter, and opens the WebSocket. The backend verifies the token before accepting the socket.

After connection, the backend sends a `state_snapshot` payload containing ambulances, hospitals, incidents, active dispatches, analytics, traffic multiplier, and simulation status. Later messages update the store incrementally.

Important message types are:

| Message Type | Meaning |
|---|---|
| `state_snapshot` | Initial full state after WebSocket connection. |
| `simulation_tick` | Periodic fleet, hospital, and incident state update. |
| `incident_created` | A new incident was created. |
| `dispatch_created` | A dispatch recommendation was generated. |
| `dispatch_overridden` | A dispatcher changed the final dispatch choice. |
| `score_update` | Analytics or dispatch score state changed. |
| `anomaly_detected` | Anomaly detector found a suspicious pattern. |
| `hospital_notification` | Hospital preparation notification was emitted. |
| `scenario_triggered` | Manual scenario started from Scenario Lab. |

The store updates arrays and maps in place so the command center, fleet page, analytics panels, and scenario lab can react without full reloads.

## 12. Background Simulation

The background simulation lives in `backend/simulation/engine.py`. It is designed to keep the demo world moving when enabled.

Each tick can:

1. Advance ambulance positions through `advance_ambulances()` in `backend/simulation/ambulance_sim.py`.

2. Move responding ambulances toward incident scenes.

3. Move transporting ambulances toward destination hospitals.

4. Resolve or clear completed assignments.

5. Fluctuate hospital occupancy and ER wait through `fluctuate_hospitals()` in `backend/simulation/hospital_sim.py`.

6. Generate random incidents through `generate_random_incident()` in `backend/simulation/incident_sim.py`.

7. Trigger dispatch pipeline behavior for new incidents when configured.

8. Broadcast `simulation_tick` snapshots to admin clients.

In the hosted demo, background simulation may be disabled to reduce server load. That means the world does not continuously create random incidents, but manual scenario routes still operate.

## 13. Manual Scenario Lab

The Scenario Lab page calls `POST /api/scenarios/run` or the compatibility path `POST /api/simulate/scenario`. The route is implemented in `backend/api/system.py` as `trigger_scenario()`.

The four primary scenario cards are:

| Scenario | What It Tests | Backend Behavior |
|---|---|---|
| Cardiac PT Dispatch | Critical cardiac routing, ALS selection, hospital pre-alert | Creates or injects a cardiac incident and validates dispatch scoring against cardiac specialty needs. |
| Hospital Overload | Capacity-aware rerouting | Pushes a hospital toward diversion or overload so dispatch selection should avoid unsafe capacity. |
| Ambulance Breakdown | Fleet resilience and fallback planning | Takes an ambulance offline for a period and confirms another unit can be selected. |
| Traffic Spike | Route and ETA sensitivity | Applies a traffic multiplier to a city so ETA-aware dispatch choices can shift. |

The scenario flow is:

1. The admin clicks `Run Scenario`.

2. The frontend sends `{ "scenario": "<scenario_id>" }`.

3. The backend validates the scenario body through `ScenarioRequest`.

4. `SimulationEngine.trigger_scenario()` applies the requested scenario.

5. The backend returns a structured result with status, effects, and scenario metadata.

6. The Scenario Lab appends the result to the event log.

7. Any relevant state changes are broadcast to live clients.

Scenario errors are formatted into readable strings on the frontend so raw objects do not appear as `[object Object]`.

## 14. Demand Heatmap

The Demand Heatmap page calls `GET /api/demand/heatmap`. This endpoint is admin-only and rate-limited.

The demand predictor is in `backend/services/demand_predictor.py`.

The heatmap flow is:

1. `build_density_grid()` loads historical synthetic training incidents from `backend/data/train_incidents.json` by default.

2. Incidents are mapped into a 20 by 20 grid for each city.

3. The grid is normalized into density values.

4. `predict_demand(city, lookahead)` applies time-of-day and lookahead adjustments to identify likely hotspots.

5. `recommend_preposition()` compares hotspots against available ambulances and checks whether each hotspot has coverage within roughly 2 km.

6. The API returns hotspots, recommendations, city, lookahead, generated timestamp, and training-source metadata.

7. The React page renders the grid, legend, and prepositioning recommendations.

The heatmap is a planning aid, not a live forecast. It is calibrated from synthetic training data and should be interpreted within the methodology limits described in `docs/data_methodology.md`.

## 15. Anomaly Detection and Rate Limiting

Adversarial defenses include rate limiting, input validation, anomaly detection, and authenticated WebSockets.

Rate limiting uses `slowapi` in `backend/main.py`. Prototype storage is in memory. Production should use Redis-backed rate-limit storage so limits survive restarts and work across multiple processes.

The anomaly detector is in `backend/services/anomaly_detector.py`. It keeps recent incidents in memory and checks:

1. Geographic clusters: multiple same-type incidents within a small radius and short time window.

2. Severity spikes: many critical incidents in the same city within a short period.

3. Rapid submitters: repeated submissions from the same IP.

When anomalies are found, the backend logs warnings, stores recent anomaly records, and broadcasts `anomaly_detected`. The command center shows the most recent anomaly alert at the top of the incident column.

## 16. Analytics and Evaluation

Analytics are split between live operational analytics and offline benchmark artifacts.

`backend/services/analytics_service.py` builds the live snapshot used by the admin dashboard. It counts incidents, dispatches, status, and operational metrics from the current database state.

`backend/scripts/benchmark.py` evaluates dispatch strategies on synthetic incident files. It supports standard split evaluation and cross-city leave-one-out evaluation. The standard benchmark can compare AI dispatch, nearest-unit dispatch, and random dispatch. Results are written to `backend/data/benchmark_results.json`.

`backend/services/fairness.py` computes fairness metrics by geographic zone. The zone classifier uses distance from city centers and divides incidents into central, mid, and peripheral groups. Metrics include average ETA, disparity ratio, and equity score.

`backend/scripts/literature_comparison.py` compares RAID Nexus simulation outputs with hardcoded published EMS optimization results. It writes `backend/data/literature_comparison.json`, which the Analytics page can display.

`backend/scripts/validate_synthetic_data.py` checks whether generated synthetic incidents match the documented target distributions for incident type, city, time-of-day, severity, and age.

## 17. Backend API Reference

| Area | Route | Function | Purpose |
|---|---|---|---|
| Auth | `POST /api/auth/login` | `login` | Returns JWT token for valid username/password. |
| Auth | `GET /api/auth/me` | `me` | Returns current user profile without password hash. |
| Incidents | `POST /api/incidents` | `create_manual_incident` | Creates a manual incident. |
| Incidents | `GET /api/incidents` | `list_incidents` | Lists incidents. |
| Patients | `POST /api/patients` | `create_patient` | Creates patient report and triaged incident. |
| Patients | `GET /api/patients/{patient_id}` | `get_patient` | Fetches patient detail. |
| Ambulances | `GET /api/ambulances` | `list_ambulances` | Lists fleet units. |
| Hospitals | `GET /api/hospitals` | `list_hospitals` | Lists hospitals. |
| Dispatch | `GET /api/dispatch/{dispatch_id}` | `get_dispatch` | Fetches dispatch detail. |
| Overrides | `POST /api/overrides/request` | `request_override` | Requests human override. |
| Overrides | `GET /api/overrides/history` | `override_history` | Lists override history. |
| Overrides | `GET /api/overrides/stats` | `override_stats` | Shows override statistics. |
| Overrides | `GET /api/dispatches/{dispatch_id}/audit` | `dispatch_audit` | Shows audit trail for dispatch. |
| System | `POST /api/scenarios/run` | `trigger_scenario` | Runs manual simulation scenario. |
| System | `POST /api/simulate/scenario` | `trigger_scenario` | Compatibility scenario route. |
| System | `GET /api/analytics` | `get_analytics` | Returns live analytics snapshot. |
| Main | `GET /api/health` | `health` | Returns service health and performance metadata. |
| Main | `GET /api/demand/heatmap` | `demand_heatmap` | Returns demand hotspots and recommendations. |
| Main | `GET /api/benchmark/results` | `benchmark_results` | Returns latest benchmark JSON. |
| Main | `GET /api/fairness` | `fairness_results` | Returns fairness analysis. |
| Main | `GET /api/literature-comparison` | `literature_comparison_results` | Returns literature comparison artifact. |
| Main | `GET /api/anomalies` | `anomaly_results` | Returns recent anomaly detections. |
| Main | `GET /api/translation/status` | `translation_status_results` | Returns loaded offline translation model status. |
| WebSocket | `WS /ws/live` | `live_feed` | Authenticated live admin/user state channel. |

## 18. Service Function Map

| File | Major Functions | What They Do |
|---|---|---|
| `backend/services/dispatch.py` | `select_dispatch`, `_score_all_pairs`, `_evaluate_pair`, `_build_explanation_text` | Computes the best ambulance-hospital pairing and score explanation. |
| `backend/services/dispatch_service.py` | `full_dispatch_pipeline` | Runs triage, dispatch selection, persistence, audit logging, notification, and WebSocket broadcast. |
| `backend/services/nlp_triage.py` | `triage_incident`, `classify_incident_type`, `classify_severity`, `get_resource_requirement` | Classifies report text and determines severity, ambulance type, review flags, and safety escalation. |
| `backend/services/language_detector.py` | `detect_language`, `get_language_review_message` | Detects report language and creates dispatcher review messages for non-English or uncertain input. |
| `backend/services/offline_translator.py` | `translate_to_english`, `_translate_sync`, `get_translation_status` | Translates supported non-English complaints into English using offline Hugging Face models or lightweight Hinglish phrase handling. |
| `backend/services/triage_service.py` | `classify_severity` | Keyword fallback for triage when NLP or translation is unavailable. |
| `backend/services/routing.py` | `get_travel_time`, `get_route_polyline` | Computes travel time and route shape with caching and fallback estimates. |
| `backend/services/traffic.py` | `get_traffic_multiplier` | Provides traffic multipliers from cache, heuristics, or external traffic services. |
| `backend/services/demand_predictor.py` | `build_density_grid`, `predict_demand`, `recommend_preposition` | Builds demand grid, predicts hotspots, and recommends ambulance prepositioning. |
| `backend/services/fairness.py` | `compute_fairness_metrics`, `compare_fairness`, `classify_zone` | Computes geographic equity and zone-level dispatch fairness metrics. |
| `backend/services/audit_service.py` | `log_ai_dispatch`, `log_human_override`, `get_audit_trail`, `get_override_stats` | Records dispatch decisions and override accountability data. |
| `backend/services/anomaly_detector.py` | `analyze_incident`, `record_incident`, `check_geographic_cluster`, `check_severity_spike`, `check_rapid_submitter` | Detects suspicious incident patterns. |
| `backend/services/notification_service.py` | `notify_hospital`, `_prep_checklist` | Creates hospital preparation messages based on incident type. |
| `backend/services/analytics_service.py` | `build_analytics_snapshot`, `broadcast_score_update` | Builds live dashboard analytics and score updates. |

## 19. Simulation Function Map

| File | Function or Class | Role |
|---|---|---|
| `backend/simulation/engine.py` | `SimulationEngine` | Owns background simulation state, scenario execution, traffic overrides, outages, overloads, snapshots, and tick loop. |
| `backend/simulation/ambulance_sim.py` | `advance_ambulances` | Moves ambulances through response, transport, and availability states. |
| `backend/simulation/ambulance_sim.py` | `_move_towards_incident`, `_move_towards_hospital` | Updates ambulance coordinates toward current targets. |
| `backend/simulation/hospital_sim.py` | `fluctuate_hospitals` | Simulates hospital capacity and ER wait variation. |
| `backend/simulation/incident_sim.py` | `generate_random_incident` | Creates random synthetic live incidents for simulation. |
| `backend/simulation/incident_sim.py` | `build_incident_payload` | Converts triage and report data into an incident database payload. |
| `backend/simulation/incident_sim.py` | `create_incident` | Inserts incidents and broadcasts incident creation events. |

## 20. Important End-to-End Walkthroughs

### 20.1 Admin Login to Command Center

1. Admin opens `/login`.

2. `LoginPage` calls `authStore.login(username, password)`.

3. `authStore` posts form data to `/api/auth/login`.

4. Backend verifies bcrypt password and returns JWT.

5. Frontend stores token, role, and username.

6. Router redirects admin to `/admin/command`.

7. `RoutedApp` hydrates auth and connects WebSocket.

8. `dispatchStore` receives `state_snapshot`.

9. Command Center renders incidents, active dispatch plan, fleet, hospitals, alerts, and override controls.

### 20.2 User Report to Dispatch Recommendation

1. User opens `/user/sos`.

2. User types or dictates emergency report.

3. UI detects whether the report should enable Priority SOS.

4. User submits the report.

5. `create_patient()` stores the patient and calls triage.

6. `triage_incident()` detects language, translates when needed, classifies incident type and severity, and sets review metadata.

7. `build_incident_payload()` prepares the linked incident record.

8. `create_incident()` inserts the incident and broadcasts `incident_created`.

9. Dispatch pipeline selects the best ambulance and hospital if invoked by that flow.

10. Admin command center sees the incident and any review warning.

### 20.3 Scenario Lab Run

1. Admin opens `/admin/scenario`.

2. Admin clicks a scenario card.

3. Frontend posts the scenario ID to `/api/scenarios/run`.

4. `trigger_scenario()` validates the request.

5. `SimulationEngine.trigger_scenario()` applies the scenario effect.

6. Backend returns a readable structured result.

7. Scenario Lab adds the event to the log.

8. Relevant state changes are broadcast over WebSocket.

### 20.4 Demand Heatmap View

1. Admin opens `/admin/heatmap`.

2. Frontend requests `/api/demand/heatmap`.

3. Backend verifies admin JWT and rate limit.

4. `predict_demand()` computes hotspots from the training density grid.

5. `recommend_preposition()` checks hotspot coverage by available ambulances.

6. Frontend renders the responsive grid and recommendation cards.

### 20.5 Human Override

1. Admin reviews an AI dispatch plan.

2. Admin selects an alternate ambulance or hospital and writes a reason.

3. Frontend posts to `/api/overrides/request`.

4. Backend validates resources and reason.

5. Dispatch final choice is updated.

6. `log_human_override()` writes audit data with admin user ID.

7. WebSocket broadcasts `dispatch_overridden`.

8. Command Center updates the dispatch detail and audit state.

## 21. Troubleshooting Guide

| Symptom | Likely Cause | Where to Check |
|---|---|---|
| Login says wrong username/password | Database still has old seeded password hash, env var mismatch, or Render service has not restarted after env update. | `backend/api/auth.py`, `backend/database.py`, Render env vars, startup logs. |
| WebSocket closes immediately | Missing, expired, or invalid JWT token. | Browser localStorage `raid_token`, `backend/api/websocket.py`, `verify_ws_token()`. |
| Scenario shows an object-like error | Backend returned structured validation error and frontend did not format it. | `frontend/src/services/api.js`, `ScenarioCard.jsx`. |
| Heatmap layout overflows | Grid or card dimensions exceed viewport constraints. | `frontend/src/pages/admin/DemandHeatmap.jsx`. |
| NLP triage is slow on first use | Hugging Face model download or CPU inference. | `backend/services/nlp_triage.py`, `RAID_LIGHTWEIGHT_TRIAGE`. |
| Translation is slow on first use | Offline translation model download or CPU inference. | `backend/services/offline_translator.py`, translation status endpoint. |
| No random live incidents appear | Background simulation is disabled. | `RAID_DISABLE_SIMULATION`, `backend/main.py`, simulation startup logs. |
| Dispatch ETA seems approximate | Routing service fallback or traffic cache was used. | `backend/services/routing.py`, `backend/services/traffic.py`. |

## 22. Reading Order for New Contributors

A new contributor should read the codebase in this order:

1. `README.md` for the product overview and setup.

2. `backend/main.py` for app creation, startup, and direct API endpoints.

3. `backend/api/auth.py` for authentication.

4. `backend/api/patients.py`, `backend/services/nlp_triage.py`, and `backend/simulation/incident_sim.py` for SOS intake.

5. `backend/services/dispatch.py` and `backend/services/dispatch_service.py` for dispatch scoring and execution.

6. `backend/api/websocket.py` and `frontend/src/store/dispatchStore.js` for live state updates.

7. `frontend/src/pages/admin/CommandCenter.jsx` for the dispatcher UI.

8. `backend/simulation/engine.py` and `frontend/src/pages/admin/ScenarioLab.jsx` for simulations.

9. `backend/services/demand_predictor.py` and `frontend/src/pages/admin/DemandHeatmap.jsx` for heatmap behavior.

10. `docs/data_methodology.md`, `docs/ethics.md`, `docs/security.md`, and `docs/production_architecture.md` for research and deployment context.
