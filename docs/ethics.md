# Ethical Framework — RAID Nexus

## 1. Overview

This document defines the ethical framework for RAID Nexus, a real-time emergency dispatch research prototype that uses algorithmic scoring, demand prediction, benchmark evaluation, human override controls, and audit logging to support ambulance and hospital allocation. It exists to make explicit how the system handles safety, equality, transparency, accountability, privacy, human oversight, and known limitations before any production deployment is considered. RAID Nexus aligns with NITI Aayog's "Responsible AI for All" (2021) framework and treats artificial intelligence as decision support for emergency operations rather than as a replacement for clinical, administrative, or dispatcher judgment.

## 2. Guiding Principles

| Principle | NITI Aayog Definition (paraphrased) | RAID Nexus Implementation |
|---|---|---|
| Safety & Reliability | AI systems should operate dependably, avoid preventable harm, and degrade safely when uncertainty or dependency failure occurs. | Fallback dispatch mode, human override system, timeout-bounded external routing and traffic calls with deterministic fallback guardrails. |
| Equality | AI systems should be evaluated for unequal outcomes across relevant population or service groups. | Fairness metrics across geographic zones, equity score, disparity ratio, and peripheral penalty measurement. |
| Inclusivity & Non-discrimination | AI systems should avoid systematic exclusion and should be assessed for patterns that disadvantage underserved groups. | Zone classifier, fairness comparison in benchmark, override rate monitoring by city. |
| Privacy & Security | AI systems should minimize unnecessary personal data exposure and protect system access and data operations. | Bearer-token mock authentication, admin authorization dependencies, audit log without patient PII, `aiosqlite` with parameterized queries. |
| Transparency | AI systems should provide understandable reasons for decisions and expose sufficient information for review. | Score breakdown per dispatch, weighted scoring formula, `explanation_text` in plain English, audit trail API. |
| Accountability | AI systems should support responsibility assignment, traceability, and review after consequential actions. | Immutable-intent audit log, mandatory override reason enforcement, override statistics endpoint, dispatch audit endpoint. |

Safety and reliability are addressed through layered fallback behavior. The dispatch service evaluates available ambulances and eligible hospitals, but if no normal candidate set is usable, it returns a fallback dispatch rather than silently failing. Routing and traffic dependencies use bounded HTTP timeouts, cached results, and deterministic Haversine or heuristic fallbacks, which are reliability guardrails rather than a full production circuit-breaker state machine. The override system further protects safety by allowing an admin dispatcher to replace an AI recommendation when operational judgment or local knowledge indicates that a different ambulance or hospital should be used.

Equality is operationalized as a measurable response-time objective rather than as a general aspiration. The fairness service computes zone-level average ETA, p90 ETA, specialty match rate, overload rate, delayed rate, disparity ratio, equity score, and peripheral penalty. These measurements make it possible to compare whether central, mid-ring, and peripheral areas receive materially different dispatch performance under the AI strategy and under baseline strategies.

Inclusivity and non-discrimination are addressed by explicitly measuring geographic service zones. RAID Nexus classifies incidents by Haversine distance from supported city centers, compares AI dispatch against nearest-unit and random baselines, and exposes override statistics that can be filtered by city. This does not eliminate structural inequality, but it gives supervisors a concrete way to detect whether peripheral locations or specific cities are receiving systematically worse service.

Privacy and security are implemented at prototype level. API access for privileged override and audit functions is controlled by bearer-token authentication and admin authorization dependencies. Database operations use `aiosqlite` and parameterized query values for record insertion, update, and lookup. The audit log records incident context and dispatch decision data, but it does not store patient names, phone numbers, or medical history.

Transparency is built into the dispatch output. The scoring service returns component-level evidence including ETA score, specialty score, crew readiness score, capacity score, ER wait score, weights used, route estimates, total score, and a plain-English `explanation_text`. This allows a dispatcher to see why an ambulance and hospital pair was preferred rather than receiving an opaque assignment.

Accountability is supported through auditability and reason capture. AI dispatch events, human overrides, and fallback dispatches can be written into `dispatch_audit_log`. Human override requests must include a reason between 20 and 500 characters, and approved override records are linked to audit entries. Supervisors can use audit and statistics endpoints to review individual decisions and broader override patterns.

## 3. Human Oversight Design

RAID Nexus is designed as an AI-assisted system, not an autonomous emergency medical authority. The AI dispatch service produces a recommendation by scoring ambulance and hospital pairs using response ETA, clinical specialty match, crew readiness, hospital capacity, and emergency-room wait time. The active default weights are 0.40 for ETA, 0.25 for specialty match, 0.15 for crew readiness, 0.10 for capacity, and 0.10 for ER wait. The recommendation includes a selected ambulance, selected hospital, ETA estimate, score breakdown, and explanation text, but a human dispatcher retains authority to accept the recommendation or override it. The `POST /api/overrides/request` endpoint requires admin authentication, an active dispatch, an available replacement ambulance, a non-diversion replacement hospital, and a different ambulance or hospital choice from the current assignment. The endpoint also enforces a mandatory reason field with a minimum of 20 characters and a maximum of 500 characters, so overrides are not treated as unexplained manual edits.

The audit trail records the operational history of dispatch decisions so that later review does not depend on memory or screen state. Audit entries capture the event type, dispatch and incident identifiers, actor identity and role, AI-selected ambulance and hospital, AI ETA, score and explanation when available, final ambulance and hospital, final ETA, override reason and override targets when relevant, incident latitude, longitude, type, severity and city, creation time, and structured metadata. Records are intended to be immutable in production: the current service path appends audit entries and exposes no audit update workflow for supervisors or dispatchers. Supervisors can use `GET /api/dispatches/{id}/audit` to retrieve the ordered audit trail for any dispatch decision and compare the AI recommendation, human override, final dispatch state, and reason text.

## 4. Algorithmic Fairness

### 4.1 Fairness Definition

RAID Nexus defines geographic fairness as approximate equality of average emergency response time across central, mid-ring, and peripheral zones within supported cities. The primary quantitative measure is the disparity ratio, calculated as the highest zone average ETA divided by the lowest non-zero zone average ETA. A ratio of 1.0 indicates perfect equality across measured zones, while larger values indicate greater disparity. The equity score transforms this ratio into a 0 to 100 score using `100 - (disparity_ratio - 1.0) * 50`, capped between 0 and 100. The system labels scores above 80 as equitable, scores from 60 through 80 as moderate disparity, and scores below 60 as significant disparity. The operational fairness threshold is that peripheral zones should receive no more than 30 percent longer ETAs than central zones, so a peripheral penalty below 30 percent is considered acceptable for benchmark review.

### 4.2 Measurement Methodology

The zone classifier uses Haversine distance from a hardcoded city center for Delhi, Mumbai, Bengaluru, Chennai, and Hyderabad. Incidents less than 5 km from the city center are classified as central, incidents from 5 km up to 12 km are classified as mid, and incidents at or beyond 12 km are classified as peripheral. City bounding boxes are also used elsewhere in the platform for demand prediction and reflect an urban-center scope for the current prototype.

For each strategy, the fairness calculator groups benchmark incidents by zone and computes count, average ETA, average total time, specialty match rate, hospital overload rate, delayed rate, and p90 ETA. It then calculates disparity ratio, equity score, equity label, fairness win, and peripheral penalty percentage. Fairness is measured at benchmark time across all three implemented strategies: `ai_dispatch`, `nearest_unit`, and `random_dispatch`. The benchmark itself simulates mutable city state, ambulance availability, hospital occupancy events, delayed incidents when all ambulances are busy, specialty matching, and per-incident outcome records. The existing benchmark output generated on 2026-04-25T11:55:21.511880+00:00 contains 20 incidents and should be interpreted only as a sample run, not as a production guarantee. In that sample, AI dispatch reported average ETA 50.44 minutes, specialty match rate 100.0 percent, equity score 64.9, and disparity ratio 1.703, while nearest-unit dispatch reported average ETA 13.93 minutes, specialty match rate 60.0 percent, equity score 58.5, and disparity ratio 1.83. These values show why fairness and clinical suitability must be evaluated together rather than reduced to a single headline metric.

### 4.3 Known Fairness Risks

The first fairness risk is synthetic data dependency. Synthetic incident data may not reflect the true geographic distribution of emergency calls, including seasonal variation, informal settlements, peri-urban growth, accident corridors, and underreported neighborhoods. If peripheral zones are underrepresented in the synthetic set, the system may underestimate demand or overstate the equity of dispatch outcomes.

The second fairness risk is structural hospital inequality. Indian cities do not distribute hospitals, specialty care, ICU capacity, and trauma readiness evenly across geography. Central areas often have more specialty hospitals, which means peripheral incidents may face lower specialty match rates regardless of the dispatch algorithm. An algorithm can route efficiently within the available infrastructure, but it cannot by itself create hospital capacity where no capacity exists.

The third fairness risk is coarse traffic modeling. The current traffic service can use TomTom flow data when configured, but its fallback is an India-focused city-level heuristic with city boosts and time-window multipliers. Peripheral corridors in cities such as Bengaluru may experience congestion patterns that are worse than the heuristic assumes, and neighborhood-level differences may be missed.

### 4.4 Mitigation

For synthetic data dependency, the current system mitigates risk by reporting benchmark results as benchmark observations rather than as production guarantees, and by exposing fairness metrics alongside performance metrics. Future work should incorporate de-identified real incident data, stratified sampling by ward or service zone, and periodic recalibration against observed dispatch outcomes. A production system should also document data provenance and compare synthetic coverage against official EMS or municipal incident distributions.

For structural hospital inequality, the current system measures specialty match rate and overload rate by zone, which helps distinguish dispatch algorithm behavior from hospital availability constraints. Future work should add hospital accessibility mapping, specialty-capacity heatmaps, and policy-level reporting that identifies zones where infrastructure shortage, not routing logic, is the limiting factor. This would allow system operators to recommend ambulance staging changes while also flagging where hospital network expansion or transfer protocols are needed.

For coarse traffic modeling, the current system uses timeout-bounded external traffic lookup when an API key is available and otherwise applies city-level heuristic congestion. Future work should add neighborhood-level traffic sampling, corridor-specific travel-time calibration, historical route observations, and incident-time traffic validation. A production deployment should monitor route prediction error by zone and feed that error back into both fairness analysis and dispatch scoring.

## 5. Known Limitations

5.1 **Synthetic Data Dependency.** RAID Nexus currently relies on synthetic incidents for benchmark evaluation and demand density estimation. This may cause benchmark metrics to diverge from real EMS demand, especially in neighborhoods with atypical reporting patterns or underserved populations. The proposed mitigation is to validate synthetic distributions against de-identified real incident data and update benchmark sampling by city zone.

5.2 **Keyword-based Triage.** The current triage layer is primarily rule and keyword based, although Tier 2 work is intended to improve clinical classification. This may misclassify ambiguous complaints, multilingual descriptions, or symptoms expressed in local phrasing. The proposed mitigation is a clinically reviewed triage model with calibrated uncertainty and a fallback path that escalates uncertain cases to human review.

5.3 **Urban-centric Coverage.** The current geographic model uses city-center bounding boxes for Delhi, Mumbai, Bengaluru, Chennai, and Hyderabad. This limits applicability to rural regions, intercity highways, and peri-urban areas outside the configured boxes. The proposed mitigation is to add district-level geographies, rural ambulance bases, and state-specific EMS coverage maps.

5.4 **Single-connection Database.** The prototype uses SQLite with `aiosqlite` and a single managed connection. This is suitable for a local research prototype but limits write concurrency, operational resilience, and horizontal scalability. The proposed mitigation is migration to a production database with connection pooling, backups, role-based access control, and auditable migrations.

5.5 **No Multilingual Support.** The current user and admin workflows do not provide multilingual intake or explanation generation. This may reduce accessibility for patients or operators who are more comfortable in Indian languages other than English. The proposed mitigation is multilingual SOS intake, translation review, locale-aware medical terminology, and language-specific usability testing.

5.6 **Static Hospital Data.** The current hospital capacity and specialty data are seeded or locally updated and do not integrate with live EMR or hospital operations systems. This may cause dispatch decisions to use stale capacity, diversion, or ER wait information. The proposed mitigation is secure integration with hospital information systems, live diversion feeds, and validation against manual capacity confirmations.

## 6. Audit and Accountability

RAID Nexus uses a two-table audit system composed of `dispatch_audit_log` and `override_requests`. The audit log table records decision events, while the override table records the workflow by which a dispatcher requests and receives approval for a human override. Together, they provide both a chronological record of dispatch outcomes and a structured record of why a human changed an AI recommendation.

| Audit Element | Captured Fields | Accountability Purpose |
|---|---|---|
| Decision event identity | `id`, `event_type`, `dispatch_id`, `incident_id`, `created_at` | Identifies the audit entry, the operational event type, the dispatch, the incident, and the time of record creation. |
| Actor context | `actor_id`, `actor_role` | Establishes whether the action came from the system, an admin, or a dispatcher. |
| AI recommendation | `ai_ambulance_id`, `ai_hospital_id`, `ai_eta_minutes`, `ai_score`, `ai_explanation` | Preserves what the AI originally recommended and why it made that recommendation. |
| Final dispatch outcome | `final_ambulance_id`, `final_hospital_id`, `final_eta_minutes` | Records what was actually dispatched after AI selection, fallback, or override. |
| Override context | `override_reason`, `override_ambulance_id`, `override_hospital_id` | Connects a human override to the dispatcher-provided justification and proposed resources. |
| Incident context | `incident_lat`, `incident_lng`, `incident_type`, `incident_severity`, `incident_city` | Enables fairness, supervision, and operational review without storing patient PII. |
| Extra metadata | `metadata` | Stores structured score breakdowns or override request snapshots for deeper review. |

The `override_requests` table captures `requested_by`, `requested_at`, original and proposed ambulance and hospital identifiers, reason, reason category, status, reviewer identity, review time, rejection reason if any, and the linked audit log identifier once processed. Override reasons are mandatory and enforced at the API level with a minimum length of 20 characters, which discourages unexplained resource changes. The production retention intention is that audit records should be retained for a minimum of five years, subject to applicable legal, operational, and institutional requirements. Access to individual audit trails is intended for admin-authenticated users only through `GET /api/dispatches/{id}/audit`.

## 7. Data Privacy

No patient personally identifiable information is stored in the `dispatch_audit_log` table. The audit log records incident type, severity, city, geographic coordinates, dispatch identifiers, actor identifiers, recommendations, final choices, and explanation or metadata fields. It does not record patient names, contact numbers, personal addresses, or longitudinal medical history.

The prototype does contain patient records elsewhere in the application for SOS intake and dispatch status workflows, so audit privacy should not be confused with whole-system privacy compliance. Any future integration with hospital patient records, EMR systems, or longitudinal medical data would require a privacy impact assessment and compliance with India's Digital Personal Data Protection Act 2023. Production use would also require data minimization, access logging, retention controls, encryption policy, consent or lawful-use analysis, and incident response procedures.

## 8. Adversarial Robustness (Acknowledged Limitation)

The current RAID Nexus prototype does not include dedicated defenses against adversarial inputs, data poisoning, model tampering, or coordinated misuse. It validates selected API fields in places such as overrides, and it uses authenticated admin access for privileged endpoints, but those controls are not a complete adversarial robustness program. Future mitigations should include: a) input validation and rate-limiting on the SOS submission endpoint, b) anomaly detection on incident patterns using statistical outlier detection over location, time, severity, and complaint distribution, and c) model versioning with signed model files to detect tampering. These mitigations should be tested through abuse-case simulations before any production deployment.

## 9. Compliance Acknowledgement

RAID Nexus is a research prototype and does not currently comply with production healthcare, emergency services, or information-security regulations. Production deployment would require compliance work for India DPDPA 2023 for data privacy, NITI Aayog's Responsible AI framework for governance and evaluation, state-level EMS regulations that vary by state, and ISO 27001 or comparable information-security controls for production infrastructure. Compliance would also require institutional approvals, operational standard operating procedures, cybersecurity review, and clinical governance before the system could influence real emergency dispatch.

## 10. Conclusion

The ethical design philosophy of RAID Nexus is that AI should support faster, more explainable, and more measurable emergency dispatch decisions while preserving human authority. The system exposes weighted score components, explanation text, fairness reports, benchmark comparisons, override workflows, and audit records so that recommendations can be questioned and reviewed. This structure is especially important in emergency response, where a superficially optimal route may still be inappropriate because of local knowledge, resource conflicts, hospital constraints, or equity concerns.

Responsible production deployment would require more than improving model accuracy. RAID Nexus would need real-world validation, de-identified operational data, stronger authentication and privacy controls, multilingual support, adversarial robustness, live hospital integration, scalable persistence, and formal compliance review. The current prototype is therefore best understood as a technical foundation for responsible AI-assisted dispatch, not as a finished medical or EMS authority.
