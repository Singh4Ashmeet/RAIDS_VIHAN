# Security Architecture — RAID Nexus

## Implemented Defenses

### 1. Authentication and Authorization
RAID Nexus uses JWT-based authentication with token expiry and role enforcement. Admin-only endpoints return `403` for non-admin users, and the live WebSocket feed now validates a bearer token supplied as a query parameter before accepting the connection. Invalid or expired WebSocket tokens are rejected with close code `1008`.

### 2. Rate Limiting
The SOS incident submission endpoint is limited to `5/minute` per IP using `slowapi`. Login is limited to `10/minute`, and expensive compute surfaces such as demand heatmap generation and scenario execution are throttled as well. The current implementation uses in-memory counters for development; production should use Redis-backed storage so limits survive restarts and work across multiple processes.

### 3. Input Validation
Incident creation validates coordinates against an India-wide bounding box, sanitizes free-text inputs by stripping HTML and unescaping entities, and enforces field length caps at the API layer. Incident type and severity values are validated against explicit allow-lists before persistence and dispatch.

### 4. Anomaly Detection
RAID Nexus now detects suspicious incident patterns with simple statistical rules. It flags geographic clustering when three or more same-type incidents appear within `500m` in `10` minutes, severity spikes when five or more critical incidents occur in one city within `30` minutes, and rapid submitters when one IP sends three or more incidents within `5` minutes. Detections are logged and broadcast to authenticated admin WebSocket clients.

## Known Gaps (Future Work)

### Data Poisoning
The ML models used by the platform, including NLP triage and demand prediction, are not yet hardened against adversarial examples crafted to manipulate classification or routing. The mitigation path is adversarial training inspired by Goodfellow et al. (2014), model signing with SHA-256 checksums, and explicit model versioning with rollback support.

### DDoS Protection
Current rate limiting is per-IP and in-memory, which is useful for prototype hardening but insufficient against rotating-IP attacks or distributed botnets. Production deployment should place the app behind a managed edge layer such as Cloudflare or AWS WAF and move rate-limit counters into Redis for shared enforcement.

### Audit Log Tampering
The SQLite audit store is not cryptographically protected. Anyone with direct database access could alter historical records. A production-grade mitigation would use an append-only log with SHA-256 hash chaining so each record includes the hash of the prior record.

### Supply Chain
Core dependencies such as `transformers`, `fastapi`, and related packages are version-pinned but not hash-pinned. That leaves room for supply-chain compromise through the package ecosystem. The mitigation path is `pip-compile --generate-hashes`, a private package mirror, and automated dependency monitoring such as Dependabot.
