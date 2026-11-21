# HopTrace Backend — Developer Handover Guide

**Welcome to HopTrace Backend!**  
This document provides everything a new developer needs to understand, configure, run, test, and extend the backend of HopTrace independently.

---

## 1. Architecture Overview

HopTrace is an ISP network fault localisation and subscriber operations platform tailored for rural village internet providers (hackFront India · Theme T3).

```
                      +-----------------------------+
                      | React Frontend (Vite) :5173 |
                      +--------------+--------------+
                                     | HTTP REST
                                     v
                 +---------------------------------------+
                 |       FastAPI Application (:8000)     |
                 |      lifespan: init_db, seed_topology |
                 +-------------------+-------------------+
                                     |
         +---------------------------+---------------------------+
         |                           |                           |
         v                           v                           v
+------------------+       +-------------------+       +-------------------+
| Operational DB   |       | Provider Registry |       | Engine Facade     |
| SQLite           |       | (Topology,        |       | HopTraceEngine    |
| (Subscribers,    |       |  Dependencies,    |       | (Singleton)       |
|  Reminders,      |       |  Explanations)    |       +---------+---------+
|  Incidents)      |       +---------+---------+                 |
+------------------+                 |                 +---------+---------+
                                     v                 v                   v
                           +-------------------+ +-------------+ +-----------------+
                           | Sarvam AI /       | | In-Memory   | | Neo4j Aura /    |
                           | Unavailable       | | Graph Store | | Live Database   |
                           +-------------------+ +-------------+ +-----------------+
```

### 1.1 Key Modules and Responsibilities

- **FastAPI Application & Lifespan (`backend/app/main.py`):**  
  Central application factory. The lifespan context manager initializes the SQLite schema (`init_db`) and seeds the graph engine topology into memory (`seed_topology(force_in_memory=True)`) on application startup.
- **Routers (`backend/app/api/`):**  
  Modular endpoints for health, topology, subscribers, incidents, lab simulations, measurements, and natural language explanations.
- **Pydantic Schemas (`backend/app/schemas/`):**  
  Strict request and response contracts enforcing field types, constraints, and OpenAPI documentation as defined in `docs/api-contract.md`.
- **Database / Repository Layer (`backend/app/db/`):**  
  Lightweight SQLite data store handling operational business records (subscribers, payment reminders, and persisted incident records) with foreign key enforcement and relational constraints.
- **Engine Facade (`backend/app/engine/facade.py`):**  
  Stable, typed Python interface exposing graph operations, simulation execution, and fault diagnostics without leaking internal engine complexities to the API layer.
- **Shared Engine Singleton (`get_engine()`):**  
  Global module-level singleton in `facade.py`. Guarantees all API routers, dependency adapters, and topology providers interact with the exact same in-memory state.
- **Topology Provider (`backend/app/providers/engine_topology.py`):**  
  Adapts the engine's internal `NetworkTopology` model into the API schema `TopologyResponse`, normalizing statuses (`"down"` $\to$ `"failed"`).
- **Engine Dependency Adapter (`backend/app/providers/dependencies.py`):**  
  Resolves downstream affected subscribers from a suspected faulty component using graph traversal, then enriches IDs with operational details from SQLite.
- **Explanation Provider (`backend/app/providers/explanations.py`):**  
  Abstract provider interface (`ExplanationProvider`) supporting honest unavailability (`UnavailableExplanationProvider`) and live Sarvam AI chat completions (`SarvamExplanationProvider`).

---

## 2. Local Setup Instructions

### 2.1 Prerequisites
- **Python:** 3.13 (recommended: via Homebrew on macOS `brew install python@3.13` or official installer).
- **Git**

### 2.2 Setup Virtual Environment
From the repository root (`~/Documents/HopTrace`):

```bash
# 1. Create a dedicated virtual environment
python3.13 -m venv backend/.venv

# 2. Activate the virtual environment
source backend/.venv/bin/activate

# 3. Upgrade pip
pip install --upgrade pip

# 4. Install backend dependencies
pip install -r backend/requirements.txt
```

### 2.3 Configure Environment Variables
Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```
*(The defaults in `.env.example` work out of the box for local development with zero external dependencies).*

### 2.4 Start the FastAPI Server
Run the development server with hot reload:

```bash
backend/.venv/bin/uvicorn app.main:app --reload --port 8000 --app-dir backend
```

### 2.5 Access Interactive Documentation
Once the server is running, open your browser:
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health check:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

---

## 3. Environment Configuration

All settings are managed via Pydantic Settings in `backend/app/config.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_VERSION` | `0.1.0` | API version returned by `/health`. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Allowed origins for React Vite dev server. |
| `TOPOLOGY_PROVIDER` | `engine` | `engine` uses HopTrace graph engine; `simulated` uses standalone mock. |
| `DEPENDENCY_ADAPTER` | `engine` | `engine` uses graph engine; `unavailable` returns 503; `simulated` uses static map. |
| `EXPLANATION_PROVIDER` | `unavailable` | `unavailable` returns 503; `sarvam` invokes Sarvam AI chat completions. |
| `SARVAM_API_KEY` | `""` | API key for Sarvam AI (required when `EXPLANATION_PROVIDER=sarvam`). |
| `SARVAM_MODEL` | `sarvam-105b` | LLM model identifier for Sarvam. |
| `SARVAM_TIMEOUT_SECONDS` | `30.0` | HTTP request timeout for Sarvam API. |
| `NEO4J_URI` | `bolt://localhost:7687` | Connection URI for Neo4j (optional for in-memory development). |
| `NEO4J_USER` | `neo4j` | Username for Neo4j. |
| `NEO4J_PASSWORD` | `""` | Password for Neo4j. |
| `SQLITE_DB_PATH` | `hoptrace.db` | Local path to SQLite operational database file. |
| `SEED_DEMO_SUBSCRIBERS` | `true` | Seed 5 canonical village subscribers on startup. |
| `SEED_DEMO_INCIDENTS` | `true` | Seed initial demo incident on startup. |

---

## 4. API Endpoint Overview

All endpoints use base path `/api/v1`:

### 4.1 System & Topology
- **`GET /api/v1/health`**
  - **Purpose:** Service health check.
  - **Response 200:** `{"status": "ok", "version": "0.1.0"}`
- **`GET /api/v1/topology`**
  - **Purpose:** Current network topology devices and links.
  - **Response 200:** Nodes (`GW1`, `R1`, `WB1`, `WB2`, `AP1`, `AP2`), links (`L1`–`L5`), `data_source: "simulated"`.

### 4.2 Subscribers & Payments
- **`GET /api/v1/subscribers`**
  - **Purpose:** List all village subscribers.
  - **Response 200:** List of 5 subscribers with plans, AP connections, and payment statuses.
- **`POST /api/v1/subscribers/{subscriber_id}/remind`**
  - **Purpose:** Record payment reminder action.
  - **Body:** `{"language": "hi"}`
  - **Response 200:** `{"subscriber_id": "...", "status": "recorded", "delivery_status": "not_sent"}`
  - **Errors:** 404 (Unknown subscriber), 422 (Blank/invalid language).

### 4.3 Simulation Lab & Measurements
- **`POST /api/v1/lab/run`**
  - **Purpose:** Execute a network test scenario (`baseline`, `degrade_link`, `access_point_failure`, `upstream_failure`).
  - **Body:** `{"scenario": "degrade_link", "target_link_id": "L3", "severity": "high"}` or `{"scenario": "upstream_failure", "target_node_id": "GW1", "severity": "high"}`
  - **Response 200:** `{"run_id": "run-...", "data_source": "simulated", "measurements_count": 5, "incident_id": "inc-..."}`
  - **Errors:** 422 (Invalid targets/scenario), 500 (Execution failure), 503 (Topology unavailable).
- **`GET /api/v1/runs/{run_id}/measurements`**
  - **Purpose:** Retrieve component telemetry observations for a test run.
  - **Response 200:** `{"run_id": "...", "data_source": "simulated", "measurements": [...]}`
  - **Errors:** 404 (Run not found).

### 4.4 Incidents, Dependencies & Explanations
- **`GET /api/v1/incidents/latest`**
  - **Purpose:** Get the most recent diagnostic incident.
  - **Response 200:** Incident object or `null` if no incident exists.
- **`GET /api/v1/incidents/{incident_id}`**
  - **Purpose:** Get incident details by ID.
  - **Response 200:** Incident record with evidence, confidence score, and uncertainty note.
  - **Errors:** 404 (Incident not found).
- **`GET /api/v1/incidents/{incident_id}/affected-subscribers`**
  - **Purpose:** Retrieve subscribers downstream of the incident's suspected component.
  - **Response 200:** `{"count": 2, "subscribers": [{"id": "SUB101", ...}]}`
  - **Errors:** 404 (Incident not found), 503 (Graph engine adapter unavailable).
- **`POST /api/v1/incidents/{incident_id}/explain`**
  - **Purpose:** Natural language explanation of an incident in Hindi/English.
  - **Body:** `{"language": "hi"}`
  - **Response 200:** `{"incident_id": "...", "language": "hi", "explanation": "...", "provider": "sarvam"}`
  - **Errors:** 404 (Incident not found), 422 (Empty language), 503 (Provider offline or unconfigured).

---

## 5. Engine Integration & Request Flow

When a lab scenario runs:
1. **Request Received:** `POST /api/v1/lab/run` validates the target link or AP against the active topology.
2. **Telemetry Generation:** `facade.run_scenario()` invokes `SimulatedTelemetryGenerator` to generate deterministic link observations.
3. **Fault Diagnosis:** `DiagnosticEngine.diagnose()` evaluates anomaly scores ($S \ge 0.10$). **Crucially, the diagnostic engine receives only observed telemetry and graph topology—it never receives the injected target ID or scenario.**
4. **Incident Creation:** If $S \ge 0.10$, an incident is opened in memory and persisted into SQLite.
5. **Affected Subscribers Analysis:** When `GET /api/v1/incidents/{id}/affected-subscribers` is called, `EngineDependencyAdapter` traces downstream access points from the suspected component using the graph store, then fetches live subscriber records from SQLite.

---

## 6. Testing Instructions

From repository root:

```bash
# Run all tests (167 unit tests offline in ~0.7s, 2 skipped)
backend/.venv/bin/python -m pytest -v

# Run only API engine integration tests
backend/.venv/bin/python -m pytest tests/api/test_engine_integration.py -v
```

See [`docs/test-plan.md`](file:///Users/rahulrajput/Documents/HopTrace/docs/test-plan.md) for full coverage details.

---

## 7. Current Limitations & Developer Caveats

1. **In-Memory Development Mode (`force_in_memory=True`):**  
   The application currently forces `force_in_memory=True` during startup and lab runs. This mirrors the full graph model in memory so the application runs offline without a live Neo4j database.
2. **Simulated vs. Live Data Source:**  
   Telemetry produced by scenario simulations carries `"data_source": "simulated"`, whereas real telemetry ingested via `/api/v1/measurements/ingest` carries `"data_source": "live"`.
3. **Live External Services Unverified:**  
   - Live Neo4j database connectivity has not been verified against a remote cloud instance (2 integration tests skip when offline).
   - Live Sarvam AI API calls require a valid `SARVAM_API_KEY`. Without it, `/explain` honestly returns 503.
4. **Persistent Run & Measurement History:**  
   All lab test runs and telemetry observations persist in SQLite (`runs` and `measurements` tables) and survive application restarts. Past run measurements are retrieved via `GET /runs/{id}/measurements` from memory or SQLite, and older runs are automatically pruned according to `RUNS_RETENTION_LIMIT` (default: 1000).

---

## 8. Future Work & Next Steps

1. **Neo4j Production Wiring:**  
   Switch `force_in_memory=False` when `NEO4J_URI` and credentials are authenticated to enable live Cypher graph queries.
2. **Predictive Analytics Expansion:**  
   Extend the EWMA time-series engine with ARIMA or deep-learning forecasting models for preemptive fault alerting.

---

## 9. Troubleshooting Guidance

- **Port 8000 already in use:**  
  Run `lsof -i :8000` and kill the conflicting process, or specify `--port 8001`.
- **Database locked / `sqlite3.OperationalError: database is locked`:**  
  Ensure no stale process holds a lock on `hoptrace.db`. The test suite uses isolated temporary databases (`tmp_path`) to avoid locking.
- **Provider returns 503:**  
  Check `.env`. If `EXPLANATION_PROVIDER=unavailable` or `DEPENDENCY_ADAPTER=unavailable`, 503 is the expected, honest response.
- **Import errors when running tests:**  
  Always run pytest from the repo root via `backend/.venv/bin/python -m pytest` so `pyproject.toml`'s `pythonpath = ["backend"]` takes effect.

---

## 10. Team Ownership Boundaries

- **Member 1 (Graph Engine):**  
  Owns `backend/app/engine/` (Neo4j driver, Cypher queries, in-memory graph store, diagnostic engine, simulated telemetry generator).
- **Member 2 (Backend & Operations - This Module):**  
  Owns `backend/app/api/`, `backend/app/providers/`, `backend/app/schemas/`, `backend/app/db/`, `backend/app/config.py`, `backend/app/main.py`, `tests/api/`, and backend documentation.
- **Member 3 (Frontend):**  
  Owns `frontend/` (React, TypeScript, Vite dev server, operator dashboard UI).
