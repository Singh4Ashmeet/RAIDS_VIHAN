# RAID Nexus User Guide

## 1. Who This Guide Is For

This guide is for people who want to use RAID Nexus without needing to understand programming, databases, APIs, or AI model code. It explains the website screen by screen, what each dashboard means, what actions are available, and what happens behind the scenes after you click a button.

RAID Nexus is an emergency dispatch decision-support web app. It helps collect emergency reports, classify the urgency, recommend an ambulance and hospital, show live fleet status, and let a human dispatcher review or override the AI recommendation.

The most important idea is simple: RAID Nexus supports human dispatchers. It does not replace them. The system can recommend actions, but emergency decisions should still be reviewed by trained people.

## 2. User Roles

RAID Nexus has two main types of users.

| Role | What They Use | Main Purpose |
|---|---|---|
| Public or patient-side user | User Portal | Submit an emergency report, use voice input, view status, and find hospitals. |
| Admin or dispatcher | Admin Dashboard | Monitor incidents, review dispatch recommendations, run simulations, inspect analytics, and manage operational decisions. |

If you log in as a normal user, you are taken to the user portal. If you log in as an admin, you are taken to the command center.

## 3. Opening the Website

Open the RAID Nexus website in your browser. The home page gives you a way to enter the app. You can either go to the login page or move toward the emergency reporting flow.

If you already have an account, choose login. Enter the username and password provided by the project owner. The password field has an eye icon so you can temporarily show or hide the password while typing.

After login, the app automatically sends you to the correct area:

| Account Type | Where You Go |
|---|---|
| Admin | Command Center |
| User | SOS Portal |

If you refresh the page, the app checks your saved login token. If it is still valid, you stay logged in. If it expired, you are sent back to login.

## 4. User Portal Overview

The user portal is meant for a person reporting an emergency. It is simpler than the admin dashboard and focuses on three tasks:

| Page | What It Does |
|---|---|
| SOS Portal | Submit an emergency report using typing or voice. |
| Dispatch Status | View the status of the submitted emergency and dispatch. |
| Hospital Finder | Look for nearby hospitals and available care options. |

## 5. SOS Portal

The SOS Portal is the main emergency report page. It asks for the emergency details and lets the user submit a report.

### 5.1 What You See

You will see a report text area where you can describe the emergency. The page may also include location fields, basic patient information, and a Priority SOS area.

The report can be typed or spoken. Voice input is intended to make the system easier to use when typing is slow or difficult.

### 5.2 How Voice Reporting Works

When you use voice reporting, the browser listens to your speech and converts it into text. The text appears in the emergency report field. You can review or edit it before submitting.

The goal is that a person can speak naturally, including mixed-language phrases. For example, if someone says something like “mujhe chest mein pain hai,” the system should treat that as a serious medical report because it contains chest pain meaning. The app is designed to understand emergency intent from the whole report, not just a single word.

Voice support depends on the browser and device. If the browser does not support speech recognition, the user can still type the report.

### 5.3 Priority SOS

Priority SOS means the system should treat the report as more urgent.

The user can turn Priority SOS on manually if they know the situation is critical. The app can also enable it automatically after reading the full report. For example, reports involving chest pain, difficulty breathing, unconsciousness, severe bleeding, stroke symptoms, or similar critical signs can automatically turn Priority SOS on.

When Priority SOS is enabled automatically, the page should show wording such as “Priority enabled from report.” This tells the user that the system detected urgency from what was written or spoken.

Priority SOS is not just based on a simple word like “pain” or “dard.” The system is meant to read the full report and decide whether the situation sounds like an emergency that needs higher priority.

### 5.4 Submitting a Report

The usual flow is:

1. Enter or speak the emergency report.

2. Check that the text looks correct.

3. Confirm location and patient details if the page asks for them.

4. Review whether Priority SOS is on or off.

5. Submit the report.

After submission, the backend creates a patient record and an incident record. The triage system reviews the report, estimates the type of emergency, estimates severity, and decides whether human review is recommended.

### 5.5 What Happens After Submission

After the report is submitted:

1. The report is saved.

2. The system classifies the emergency type, such as cardiac, trauma, respiratory, stroke, accident, or other.

3. The system classifies severity, such as low, medium, high, or critical.

4. The system may translate non-English or mixed-language input into English before classification.

5. If the language or classification confidence is uncertain, the system marks the report for human review.

6. The incident appears in the admin Command Center.

7. The dispatch system can recommend an ambulance and hospital.

## 6. Dispatch Status Page

The Dispatch Status page is for a user who wants to know what is happening after an emergency report is submitted.

It may show:

| Item | Meaning |
|---|---|
| Incident status | Whether the report is open, dispatched, or resolved. |
| Ambulance status | Whether an ambulance has been assigned or is en route. |
| Hospital destination | Which hospital was selected if a dispatch exists. |
| ETA | Estimated time for response or transport. |
| Updates | Any live status changes from the system. |

This page is meant to reduce uncertainty for the reporting user. It is not a replacement for calling emergency services in a real emergency.

## 7. Hospital Finder

The Hospital Finder page helps users view hospital options. It can show hospitals, availability, care type, or general readiness information depending on the current data.

Useful hospital information can include:

| Field | Meaning |
|---|---|
| Hospital name | The facility name. |
| Specialty | General, cardiac, trauma, or multi-specialty care. |
| Capacity | Whether the hospital has room to accept patients. |
| ER wait | Approximate emergency room wait time. |
| Diversion status | Whether the hospital should be avoided because it is overloaded. |

Hospital Finder is informational. The dispatch system still uses scoring logic and dispatcher review to choose the final destination.

## 8. Admin Dashboard Overview

The admin dashboard is used by dispatchers or operators. It has a sidebar with pages such as:

| Page | Purpose |
|---|---|
| Command Center | Main live dispatch workspace. |
| Fleet & Hospitals | View ambulance and hospital operational status. |
| Analytics | Review benchmark, fairness, and comparison results. |
| Scenario Lab | Run emergency simulations. |
| Demand Heatmap | See likely demand hotspots and prepositioning advice. |

The top bar shows system status, traffic multiplier, live connection state, and notification indicators.

## 9. Command Center

The Command Center is the most important admin page. It is where dispatchers monitor new incidents and review dispatch recommendations.

### 9.1 Left Column: Incident Feed

The left column shows incoming incidents. Each incident card may show:

| Item | Meaning |
|---|---|
| Incident type | The emergency category, such as cardiac or trauma. |
| Severity | How urgent the system thinks the incident is. |
| City or location | Where the incident is reported. |
| Review recommended | The AI is uncertain or the report needs human attention. |
| Language detected | The report may be non-English or translated. |
| Anomaly alert | The incident may be part of a suspicious pattern. |

If a report needs review, the card may show an amber warning. If the report was in a non-English language, it may show a language badge so the dispatcher understands why review is needed.

### 9.2 Center Column: Dispatch Detail

The center area shows the currently selected incident or dispatch recommendation. This is where the dispatcher can understand what the system recommends.

It may show:

| Item | Meaning |
|---|---|
| Recommended ambulance | The ambulance the AI suggests. |
| Recommended hospital | The hospital the AI suggests. |
| ETA | Estimated response or travel time. |
| Score breakdown | Why this option was selected. |
| AI reasoning | A plain-language explanation of the recommendation. |
| Review alert | Warning if the AI classification is uncertain. |
| Original complaint | If translated, the original complaint can be shown for review. |

The scoring considers response time, hospital specialty match, ambulance readiness, hospital capacity, and emergency room wait time.

### 9.3 Right Column: Fleet and Operational Context

The right side shows supporting information such as fleet state, hospitals, or operational details.

Ambulances can be available, dispatched, transporting, offline, or otherwise unavailable. Hospitals can have changing capacity, ER wait, and diversion state.

This area helps the dispatcher understand whether the AI recommendation is operationally reasonable.

### 9.4 Override Controls

If the dispatcher disagrees with the AI recommendation, they can request an override.

The override flow is:

1. Select a different ambulance or hospital.

2. Enter a reason for the override.

3. Submit the override request.

4. The backend checks whether the selected resources are valid.

5. The dispatch record is updated.

6. The audit log records who made the override and why.

Overrides are important because the system is AI-assisted, not fully automatic. Human judgment is expected.

## 10. Fleet & Hospitals

The Fleet & Hospitals page gives a wider operational view of the system.

### 10.1 Ambulance View

Ambulance cards or rows can show:

| Field | Meaning |
|---|---|
| Ambulance ID | The unit identifier. |
| Type | ALS or BLS. ALS is advanced life support. BLS is basic life support. |
| Status | Available, dispatched, transporting, offline, or similar. |
| Crew readiness | How ready the unit is for assignment. |
| Location | Current city or map position. |

Dispatchers use this page to understand fleet availability.

### 10.2 Hospital View

Hospital cards or rows can show:

| Field | Meaning |
|---|---|
| Hospital name | Facility name. |
| Specialty | General, cardiac, trauma, or multi-specialty. |
| Capacity | Number of available emergency resources. |
| ER wait | Approximate waiting time. |
| Diversion | Whether the hospital should be avoided. |

This page helps explain why the dispatch engine may choose one hospital over another.

## 11. Analytics Dashboard

The Analytics page is for reviewing system performance and research outputs.

It can show:

| Section | Meaning |
|---|---|
| Benchmark results | How different dispatch strategies performed on synthetic incidents. |
| AI vs nearest unit | Whether AI dispatch improved ETA compared with simply choosing the nearest ambulance. |
| Specialty match | How often the chosen hospital matched the emergency type. |
| Fairness metrics | Whether central, mid, and peripheral zones received similar service quality. |
| Literature comparison | How RAID Nexus simulation results compare with published EMS optimization research. |

These results are not proof of real-world performance. They are simulation and benchmark results. The data methodology document explains the limits.

## 12. Scenario Lab

Scenario Lab lets an admin test how the system behaves under stressful situations.

The page contains scenario cards. Each card has a title, a short explanation, affected system areas, duration, and a Run Scenario button.

### 12.1 Cardiac PT Dispatch

This scenario tests a critical cardiac emergency. It checks whether the system prioritizes advanced support and routes toward a suitable hospital.

What happens:

1. A cardiac emergency is injected or simulated.

2. The dispatch system evaluates available ambulances.

3. The hospital specialty match becomes important.

4. The system should prefer ALS routing and cardiac-capable care when available.

### 12.2 Hospital Overload

This scenario tests what happens when a hospital becomes overloaded.

What happens:

1. A hospital is pushed into high load or diversion.

2. The dispatch system should avoid sending more patients there if safer options exist.

3. The dispatcher can see capacity-aware rerouting behavior.

### 12.3 Ambulance Breakdown

This scenario tests what happens when an ambulance becomes unavailable.

What happens:

1. One ambulance is taken offline for a period of time.

2. The fleet state updates.

3. The dispatch system must choose another unit if needed.

4. This tests fallback behavior and fleet resilience.

### 12.4 Traffic Spike

This scenario tests what happens when traffic suddenly worsens.

What happens:

1. A city receives a higher traffic multiplier.

2. Travel times increase.

3. The dispatch system may choose a different ambulance or hospital because ETA changed.

4. The dispatcher can observe whether the system reacts to traffic conditions.

### 12.5 Scenario Results

After a scenario runs, the page shows the result in an event log. If something fails, the page should show a readable error instead of technical text.

## 13. Demand Heatmap

The Demand Heatmap page shows where emergency demand is expected to be higher.

### 13.1 What the Map Means

The page uses a grid. Each square represents an area. Colors indicate demand level.

| Level | Meaning |
|---|---|
| Quiet | Low predicted demand. |
| Watch | Medium predicted demand. |
| Surge | High predicted demand. |

This helps dispatchers think ahead. If one area is likely to have more incidents, the system may recommend moving an available ambulance closer to that area.

### 13.2 How Recommendations Work

The backend looks at synthetic historical incident patterns and current ambulance availability. If a hotspot is not covered by a nearby ambulance, the system may recommend prepositioning a unit.

Prepositioning means moving an ambulance before an emergency occurs so response time may be lower later.

### 13.3 How to Use It

1. Open Demand Heatmap.

2. Review the colored grid.

3. Look for Watch or Surge areas.

4. Read the prepositioning recommendation.

5. Use dispatcher judgment before moving a unit.

The heatmap is a planning tool, not a guaranteed prediction.

## 14. Live Updates and Notifications

RAID Nexus uses a live connection between the browser and backend. This means admin pages can update without refreshing.

Live updates can include:

| Update | What It Means |
|---|---|
| New incident | A user or simulation created a new emergency. |
| New dispatch | The system generated an ambulance-hospital recommendation. |
| Simulation tick | The simulated world moved forward. |
| Anomaly detected | Suspicious incident pattern was found. |
| Override completed | A human dispatcher changed the dispatch decision. |
| Hospital notification | A hospital preparation message was generated. |

If the live connection is lost, the app may try to reconnect. If your login token expired, you may be sent back to login.

## 15. Common Labels

| Label | Meaning |
|---|---|
| ALS | Advanced Life Support ambulance. Used for more serious emergencies. |
| BLS | Basic Life Support ambulance. Used for lower-acuity emergencies. |
| Critical | Highest urgency. Immediate attention required. |
| High | Serious and urgent. |
| Medium | Needs medical care but may not be immediately life-threatening. |
| Low | Lower urgency. |
| Diversion | Hospital should be avoided because it is overloaded or unavailable. |
| ETA | Estimated time of arrival. |
| Review recommended | Human dispatcher should check the AI result carefully. |
| Translated | The original report was translated before AI classification. |
| Anomaly | Pattern may be suspicious, duplicate, or unusual. |

## 16. End-to-End Example: Normal Emergency Report

1. A user opens the SOS Portal.

2. The user types: “Patient has chest pain and difficulty breathing.”

3. The app reads the report and enables Priority SOS.

4. The user submits the report.

5. The backend classifies it as likely cardiac or respiratory and high or critical severity.

6. An incident appears in the Command Center.

7. The dispatch engine compares ambulance and hospital options.

8. The AI recommends an ambulance and hospital.

9. The dispatcher reviews the recommendation.

10. The dispatcher accepts it or submits an override.

## 17. End-to-End Example: Mixed-Language Voice Report

1. A user opens the SOS Portal and starts voice input.

2. The user says: “Mujhe chest mein pain hai aur saans lene mein dikkat hai.”

3. The browser converts speech to text.

4. The app understands the report as potentially serious.

5. Priority SOS is enabled from the report.

6. The backend detects language or mixed-language content.

7. The backend translates or uses fallback safety signals where available.

8. The report is marked for human review because translated emergency text should be verified.

9. The Command Center shows review and language indicators.

10. The dispatcher reviews the original and translated report before confirming dispatch.

## 18. End-to-End Example: Admin Runs a Simulation

1. Admin opens Scenario Lab.

2. Admin clicks Ambulance Breakdown.

3. The backend takes one ambulance offline temporarily.

4. Fleet state updates.

5. If a dispatch is needed, the system should avoid the unavailable unit.

6. The event log records the scenario result.

7. Command Center and Fleet pages show the changed operational state.

## 19. Safety Notes

RAID Nexus is a prototype and research system. It is not a certified emergency medical dispatch system.

Important safety points:

1. In a real emergency, users should call the official emergency number.

2. AI recommendations should be reviewed by a human dispatcher.

3. Translation can be imperfect, especially for medical slang or mixed-language speech.

4. Benchmark and heatmap results come from synthetic data and simulation.

5. The system is useful for demonstration, research, and evaluation, but production use would require regulatory, clinical, and security validation.

## 20. Basic Troubleshooting

| Problem | What To Try |
|---|---|
| Login fails | Check username and password carefully. Use the eye icon to verify the password while typing. |
| Page is blank after login | Refresh once. If still blank, log out and log in again. |
| Voice input does not start | Try Chrome or Edge, allow microphone permission, or type the report manually. |
| SOS priority did not turn on | Make sure the report clearly describes the emergency. You can still turn priority on manually if available. |
| Admin data does not update | Check the live indicator. Refresh if the live connection dropped. |
| Scenario button shows an error | Try again after a few seconds. If it continues, the backend may be restarting or the scenario input may be rejected. |
| Heatmap looks too large or clipped | Zoom the browser to 90 percent or refresh. The page is designed to resize, but very narrow screens may still need scrolling. |

## 21. Suggested Learning Path

For a first-time non-technical user, use the app in this order:

1. Log in as a normal user and open the SOS Portal.

2. Submit a simple test report.

3. Log in as an admin and open Command Center.

4. Find the incident in the feed.

5. Review the dispatch recommendation.

6. Open Fleet & Hospitals to understand available resources.

7. Open Scenario Lab and run one scenario.

8. Open Demand Heatmap to understand demand prediction.

9. Open Analytics to see how the system is evaluated.

10. Read the safety notes before treating any result as operationally meaningful.

