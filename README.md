# HopTrace

**ISP Network Fault Localisation, Physical Geography & Subscriber Operations**  
*hackFront India · Theme T3: Telecom & Connectivity (Running a Village Internet Business)*

HopTrace is an intelligent network diagnostic and operations system engineered for rural village Internet Service Providers (ISPs). It pairs graph-based network topology modeling with physical geographic mapping, explainable AI fault localisation, RF Fresnel zone clearance analysis, business revenue-at-risk analysis, and multi-language subscriber outage notifications to help village operators detect outages, pinpoint root causes, and notify affected community members in local languages.

---

## ⚡ One-Command Quickstart (Judges & Evaluation)

### Option A: Docker Compose (Recommended — Zero Setup)

Run the entire system (backend with in-memory graph store and SQLite persistence + frontend with production Nginx reverse proxy) in a single command:

```bash
docker compose up --build
```

- **Operator Web Dashboard:** [http://localhost:5173](http://localhost:5173)
- **FastAPI Interactive Docs (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Health Check:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

*(To stop: `docker compose down`)*

---

### Option B: Local Development (Make / npm)

```bash
# Using Make:
make dev

# Or using npm:
npm run dev
```

Both commands start the FastAPI backend on port `8000` and the Vite frontend on port `5173` concurrently.

<details>
<summary>Manual Step-by-Step Setup</summary>

#### 1. Backend Setup
```bash
# Setup virtual environment
python -m venv backend/.venv
# Windows PowerShell:
.\backend\.venv\Scripts\Activate.ps1
# macOS/Linux:
source backend/.venv/bin/activate

pip install -r backend/requirements.txt
cp .env.example .env

# Run FastAPI development server
python -m uvicorn app.main:app --reload --port 8000 --app-dir backend
```

#### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
</details>

---

## ✨ Key Features & Capabilities

- **🗺️ Interactive India Village Map (Leaflet) & Logical Graph (React Flow)**:
  - Grounded in realistic rural topography across Sitapur / Hardoi district, UP (anchor at 27.20000° N, 80.60000° E).
  - Physical node placement for 15 network elements (Fiber Gateway, Core Router, 5.8 GHz & 60 GHz PtP Wireless Bridges, Access Points).
  - Coverage radius visualization (AP coverage footprint) styled by village health status.
  - CARTO Dark basemap with automatic offline fallback banner.
  - Layer toggles for AP coverage, links, and node labels (rendered at zoom $\ge 16$).
  - Dual-mode view toggle (`Map` ↔ `Graph` React Flow canvas) with keyboard navigation and persistent preference.

- **📡 Wireless RF & Fresnel Zone Line-of-Sight Analysis**:
  - Automated first Fresnel zone radius ($F_1 = 17.32 \times \sqrt{\frac{d_{\text{km}}}{4 \times f_{\text{GHz}}}}$) and 60% clearance calculation on PtP microwave backhauls (L3, L7, L12).
  - Frequency band parsing (5 GHz, 60 GHz) with intelligent suppression for optical fiber (L1).

- **🌐 Real Telemetry Ingestion & Live Agent (`agent/hoptrace_agent.py`)**:
  - `POST /api/v1/measurements/ingest` accepts live link telemetry with schema validation and optional `X-API-Key` auth.
  - Ingested metrics flow into the time-series store and WebSocket telemetry stream, tagging data as `data_source="live"`.
  - Live vs. Simulated visual badges per link and in the TopBar.
  - Standalone zero-dependency Python monitoring agent pinging targets and posting metrics every $N$ seconds.

- **⚡ Graph-Derived Fault Cascade & Flapping Detection**:
  - Cascading faults detected dynamically from topology interior link sets downstream of gateway children.
  - Flapping link detection tracking jitter and oscillation across sliding time-series windows.
  - Strict evaluation separation: Diagnostic engine never receives injected scenario names or fault ground truth.

- **💼 Business Mode & Revenue-at-Risk Analytics**:
  - One-click toggle between **NOC Mode** (engineering telemetry, RF links, map) and **Business Mode** (revenue, SLA credits, subscribers).
  - `GET /api/v1/incidents/{id}/business-impact` calculates active outage duration, monthly revenue at risk in ₹, estimated SLA credits owed, and affected households grouped by village.
  - Direct subscriber actions: send payment or outage reminders via SMS/WhatsApp with UPI QR collection modal.

- **🗣️ Indic Voice & Local Language Explanations (Sarvam AI)**:
  - Grounded natural-language incident explanations across 7 Indian languages (Hindi, Tamil, Telugu, Marathi, Kannada, Bengali, English).
  - Audio explanation synthesis with Sarvam AI Bulbul TTS.

- **📢 Multi-Language Outage Notifications (Twilio & Console)**:
  - Provider pattern with honest defaults: returns HTTP 503 when external services are unconfigured.
  - `ConsoleNotificationProvider` for demo environments and automated testing.
  - `TwilioNotificationProvider` for live SMS and WhatsApp broadcast alerts.
  - Preview endpoint `GET /api/v1/incidents/{id}/notifications/preview` renders personalized alerts in each subscriber's preferred language.
  - Dispatch endpoint `POST /api/v1/incidents/{id}/notify` sends notifications with optional subscriber filtering.

- **💾 SQLite Persistence & Resilience**:
  - All lab runs, incidents, and telemetry measurements persist in SQLite with automatic 1,000-run retention.
  - State and historical time-series survive app and server restarts.

---

## 🧪 Running Tests & Verification

HopTrace maintains 100% clean verification across backend and frontend suites:

```bash
# Run full suite (both backend and frontend):
make test
# or:
npm test
```

### Backend Integration & Unit Tests (202 Passed, 2 Skipped)
```bash
python -m pytest tests -v
# or:
npm run test:backend
```

### Frontend Component & Geometry Tests (42 Passed)
```bash
node --test frontend/src/components/VillageMap/*.test.js frontend/src/components/NetworkView/viewPref.test.js
# or:
npm run test:frontend
```

### Frontend Code Quality (ESLint & Vite Build)
```bash
npm run lint    # 0 errors, 0 warnings (100% clean)
npm run build   # Production Vite bundle compiled in ~1s
```

---

## 🎬 Final Judge Demo Script

Follow this 90-second demo script to see every major capability in action:

1. **Physical Overview & Villages**:
   - Open [http://localhost:5173](http://localhost:5173) in **Map** mode.
   - Observe the 15 network elements (Fiber Gateway, PtP wireless bridges, Access Points) connecting Rampur, Bhatpur, and Daulatpur.
   - In the bottom-right **Villages** panel, click **Bhatpur** $\rightarrow$ the map smoothly flies and frames the village AP cluster.

2. **RF Fresnel Clearance & Band Analysis**:
   - Click wireless bridge link **L3** (or **L7**) on the map $\rightarrow$ examine the popup displaying path distance ($3.2\text{ km}$), carrier band ($5\text{ GHz}$), $F_1$ radius ($6.93\text{ m}$), and 60% clearance ($4.16\text{ m}$).
   - Click fiber backhaul **L1** $\rightarrow$ note Fresnel calculations are cleanly suppressed for optical fiber.

3. **Simulate a Network Outage**:
   - In the **Scenario Lab** at the bottom, select **Degrade L3 High** (or click the quick preset button).
   - Click **Run Scenario** $\rightarrow$ link L3 pulses red, downstream AP1 and AP2 highlight with dashed blast-radius warnings, and fault alarms fire.

4. **NOC Diagnostic & Multilingual AI Explanation**:
   - In the **Fault Detection** drawer, observe the diagnostic confidence score and evidence chain.
   - Click language tabs (e.g. **हिंदी**, **தமிழ்**, **English**) to generate grounded Sarvam AI explanations and listen to the voice briefing.

5. **Business Mode & Revenue at Risk**:
   - In the TopBar, switch from **NOC** to **Business** mode.
   - Review the **Business Impact Panel**:
     - Total Monthly Revenue at Risk (in ₹).
     - Outage duration so far and estimated SLA credit owed.
     - Affected households breakdown by village (Rampur, Bhatpur, Daulatpur).
   - In the subscriber list, click **Send Reminder** or open the **UPI QR Modal** for quick payment collection.

6. **Outage Notifications (Preview & Trigger)**:
   - In the Swagger docs ([http://localhost:8000/docs](http://localhost:8000/docs)), test:
     - `GET /api/v1/incidents/{incident_id}/notifications/preview` $\rightarrow$ inspect personalized SMS/WhatsApp alert drafts translated into each subscriber's preferred language (Hindi/English).
     - `POST /api/v1/incidents/{incident_id}/notify` $\rightarrow$ trigger outage broadcast (dispatched via Console provider in demo mode or Twilio when credentials are provided).

7. **Live Telemetry Ingestion**:
   - Run the standalone telemetry agent: `python agent/hoptrace_agent.py`.
   - The TopBar badge shifts from `Simulated` to `Live` as real measurements stream into the diagnostic engine and WebSocket charts.

8. **Heal Network**:
   - In the Scenario Lab, click **Baseline Restore** $\rightarrow$ all alerts, dashed blast circles, and risk scores instantly return to healthy emerald.

---

## 🏛️ System Architecture

```
                      +-----------------------------+
                      | React Frontend (Vite) :5173 |
                      | - Leaflet India Village Map |
                      | - React Flow TopologyCanvas |
                      | - NOC & Business Mode Views |
                      +--------------+--------------+
                                     | HTTP REST + WebSocket
                                     v
                      +-----------------------------+
                      |  Nginx Reverse Proxy (:80)  |
                      |  (Docker Container Bundle)  |
                      +--------------+--------------+
                                     |
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
|  Incidents,      |       |  Explanations,    |       +---------+---------+
|  Measurements)   |       |  Notifications)   |                 |
+------------------+       +---------+---------+       +---------+---------+
                                     |                 | In-Memory Graph   |
                                     v                 | Store (Fallback)  |
                         +-----------------------+     +-------------------+
                         | Sarvam AI / Twilio /  |               |
                         | Console Providers     |     +-------------------+
                         +-----------------------+     | Neo4j Database    |
                                                       | (Optional Aura)   |
                                                       +-------------------+
```

---

## 📚 Documentation Index

- 📋 [**API Contract (`docs/api-contract.md`)**](docs/api-contract.md): Strict HTTP REST API contract for all endpoints, request bodies, geographic schemas, and response formats.
- 📘 [**Backend Handover Guide (`docs/backend-handover.md`)**](docs/backend-handover.md): Architecture, setup, endpoints, engine integration, limitations, and troubleshooting.
- 🕸️ [**Graph Model & Engine (`docs/graph-model.md`)**](docs/graph-model.md): Neo4j schema, Cypher queries, simulated telemetry model, and explainable fault localization algorithms.
- 🧪 [**Test Plan & Verification Matrix (`docs/test-plan.md`)**](docs/test-plan.md): Test suite breakdown and verification matrix.

---

## 👥 Module Ownership

- **Member 1 (Graph Engine):** Owns `backend/app/engine/` (graph store, topology, diagnostic engine, simulated telemetry generator).
- **Member 2 (Backend & Operations):** Owns `backend/app/api/`, `backend/app/providers/`, `backend/app/schemas/`, `backend/app/db/`, `backend/app/config.py`, `backend/app/main.py`, `tests/api/`, and backend documentation.
- **Member 3 (Frontend):** Owns `frontend/` (React, Leaflet VillageMap, React Flow TopologyCanvas, Vite dev server, operator dashboard UI).
