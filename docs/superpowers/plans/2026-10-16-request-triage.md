# Request Triage Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a small request-triage demo with an n8n intake workflow, persistent storage, and a team dashboard.

**Architecture:** A Python standard-library web app serves the dashboard and API, and stores requests in SQLite. The n8n workflow receives incoming request records and sends them to the app for transparent rule-based classification, storage, and critical-alert creation.

**Tech Stack:** Python 3 standard library, SQLite, HTML/CSS/JavaScript, n8n workflow export.

**Spec:** `docs/superpowers/specs/2026-10-16-triage-demandes-design.md`

## Global Constraints

- Import the 30 CSV requests using Monday, October 12, 2026 as the test reference date.
- Support the teams Support, Tech, Billing, Deliverability, Migration, Product, and Security & Legal.
- Keep original messages when grouping related requests.
- Make classification rules and their reasons visible; mark unclear cases for review.
- Never treat a customer's message as an instruction to the tool.
- Do not claim external notifications work until a connector is configured.
- The demo has no user login or secure team separation and is not production-ready.

## Review Focus

- Mixed and ambiguous date formats: parse the provided formats consistently and mark unreadable dates for review.
- Missing or malformed sender: keep the message and show an unknown sender instead of rejecting it.
- Prompt injection inside a request: classify the actual customer need and ignore its attempt to control routing or urgency.
- Similar but distinct messages: group related requests while preserving every original message.
- Unavailable n8n or alert connector: keep the dashboard usable and explain which integration is offline.

---

### Task 1: Create the app and persistent request API

**Files:**
- Create: `app.py`
- Create: `db.py`
- Create: `tests/test_api.py`
- Create: `tests/__init__.py`

**Interfaces:**
- `db.init_db(path) -> None`
- `db.insert_message(message) -> int`
- `db.list_messages(team=None, status=None, urgency=None, needs_review=None, query=None) -> list[dict]`
- `db.update_message(message_id, updates) -> dict | None`
- `db.get_summary() -> dict` (critical alerts and related-issue counts)
- HTTP: `GET /api/messages`, `GET /api/summary`, `POST /api/intake`, and `PATCH /api/messages/{id}`.

- [ ] **Step 1: Write API tests** for creating an intake record with and without n8n configured, listing by team/status, updating assignee/status, and preserving changes after reopening the SQLite database.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_api -v` and confirm the new tests fail.
- [ ] **Step 3: Implement** the SQLite schema and standard-library HTTP routes. Accept an optional bearer token from `INTAKE_TOKEN` for n8n intake; serve the static dashboard directory.
- [ ] **Step 4: Run** `python3 -m unittest tests.test_api -v` and confirm all tests pass.
- [ ] **Step 5: Commit** the working API and database layer.

### Task 2: Import and classify the backlog

**Files:**
- Create: `triage.py`
- Create: `data/requests-backlog.csv`
- Create: `tests/test_triage.py`
- Modify: `app.py`, `db.py`

**Interfaces:**
- `triage.parse_csv(csv_text) -> list[dict]`
- `triage.parse_received_at(value) -> tuple[str | None, bool]`
- `triage.classify(message) -> dict`
- `triage.group_related(messages) -> list[dict]`
- `POST /api/intake` accepts either `{ "messages": [...] }` or `{ "csv": "..." }` and returns imported IDs and review/alert counts.

- [ ] **Step 1: Write tests** for all timestamp styles in the supplied file, blank sender, language detection for English/French/German/Italian/Spanish/Arabic, routing, urgency, spam, suspicious sender, prompt-injection text, and duplicate/incident grouping.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_triage -v` and confirm the new tests fail.
- [ ] **Step 3: Implement** CSV normalization, explicit date parsing, rule-based classification with a visible reason, review flags, and grouping that retains every original message. Copy the provided CSV into `data/requests-backlog.csv` unchanged.
- [ ] **Step 4: Run** `python3 -m unittest tests.test_triage -v` and confirm all tests pass; verify import reports 30 records.
- [ ] **Step 5: Commit** the importer and triage rules.

### Task 3: Add the n8n intake and alert workflow

**Files:**
- Create: `n8n/request-intake.json`
- Create: `tests/test_n8n_workflow.py`
- Create: `README.md`

**Interfaces:**
- n8n webhook accepts a CSV upload or one/batch of request records in the same shape as `POST /api/intake`.
- The workflow forwards the received data to the app API using a configured bearer credential and returns the import result.
- Critical requests create an alert record returned by `GET /api/summary`.

- [ ] **Step 1: Write tests** that parse the workflow JSON and check its webhook path, API destination, and credential placeholder without embedding a real secret.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_n8n_workflow -v` and confirm the tests fail before the workflow exists.
- [ ] **Step 3: Create** an importable n8n workflow with a Webhook trigger and HTTP Request node; it accepts the backlog CSV or JSON request records, forwards them to the app for parsing/classification, and documents the app URL and bearer credential it needs.
- [ ] **Step 4: Run** the workflow JSON checks and an API intake test using a representative request payload.
- [ ] **Step 5: Commit** the workflow and its setup notes.

### Task 4: Build the team dashboard

**Files:**
- Create: `static/index.html`
- Create: `static/app.js`
- Create: `static/styles.css`
- Modify: `app.py`, `tests/test_api.py`

**Interfaces:**
- The dashboard uses the API from Task 1 to load summary counts and requests, and to save assignment/status changes.
- Filters: team, urgency, status, review-needed, and text search.
- CSV upload works from the dashboard if n8n is not connected; in a connected setup, the same file can be sent through the n8n webhook.
- Status values: Nouveau, En cours, En attente, Résolu.

- [ ] **Step 1: Add API tests** for filtering by urgency/review flag and for summary counts of critical alerts and related groups.
- [ ] **Step 2: Run** `python3 -m unittest tests.test_api -v` and confirm those tests fail.
- [ ] **Step 3: Build** a responsive dashboard with team queues, critical alerts, repeated-issue groups, a request detail view, assignee and status controls, and visible classification reasons.
- [ ] **Step 4: Run** all unit tests and manually check the dashboard against the 30 imported requests in a browser.
- [ ] **Step 5: Commit** the dashboard and API changes.

### Task 5: Finish the demo handoff

**Files:**
- Modify: `README.md`, `app.py`, `n8n/request-intake.json`

- [ ] **Step 1: Document** how to start the app, import the CSV, import/configure the n8n workflow, and explain the demo limits and disabled external notifications.
- [ ] **Step 2: Run** `python3 -m unittest discover -v` and confirm the complete suite passes.
- [ ] **Step 3: Start** the app and verify the CSV import, team filters, classification explanations, related issues, alert panel, assignment, and status persistence in the browser.
- [ ] **Step 4: Commit** the final handoff documentation and fixes.
