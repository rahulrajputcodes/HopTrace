# HopTrace

**ISP Network Fault Localisation, Physical Geography & Subscriber Operations**  
*hackFront India · Theme T3: Telecom & Connectivity (Running a Village Internet Business)*

HopTrace is an intelligent network diagnostic and operations system engineered for rural village Internet Service Providers (ISPs). It pairs graph-based network topology modeling with physical geographic mapping, explainable AI fault localisation, RF Fresnel zone clearance analysis, and subscriber operations to help village operators detect outages, pinpoint root causes, and notify affected community members in local languages.

---

## ✨ Key Features & Capabilities

- **🗺️ Interactive India Village Map (Leaflet)**:
  - Grounded in realistic rural topography across Sitapur / Hardoi district, UP (anchor at 27.20000° N, 80.60000° E).
  - Physical node placement for 15 network elements (Fiber Gateway, Core Router, 5.8 GHz & 60 GHz PtP Wireless Bridges, Access Points).
  - Coverage radius visualization (AP coverage footprint) styled by village health status.
  - CARTO Dark basemap with automatic offline fallback banner.
  - Layer toggles for AP coverage, links, and node labels (rendered at zoom $\ge 16$).
  - Dual-mode view toggle (`Map` ↔ `Graph` React Flow canvas) with keyboard navigation and persistent preference.

- **📡 Wireless RF & Fresnel Zone Line-of-Sight Analysis**:
  - Automated first Fresnel zone radius ($F_1 = 17.32 \times \sqrt{\frac{d_{\text{km}}}{4 \times f_{\text{GHz}}}}$) and 60% clearance calculation on PtP microwave backhauls (L3, L7, L12).
  - Frequency band parsing (5 GHz, 60 GHz) with intelligent suppression for optical fiber (L1).

- **🏘️ Village Demographics & Operations Panel**:
  - Live summary of Rampur, Bhatpur, and Daulatpur with population, network health, AP count, and registered subscriber counts.
  - Interactive `flyToBounds` camera transition focusing directly on any village cluster upon click.

- **⚡ Real-Time Fault Localisation & Blast Radius**:
  - Suspected root-cause links pulse in high-contrast red overlays.
  - Downstream blast radius APs render dashed warning outlines with affected subscriber indicators.
  - Selected elements open a full diagnostic drawer.

- **🗣️ Indic Voice & Local Language Alerts (Sarvam AI)**:
  - Audio explanations synthesized via Sarvam AI Bulbul TTS across 7 Indian languages (Hindi, Tamil, Telugu, Marathi, Kannada, Bengali, English).

---

## 🚀 Quickstart

### Prerequisites
- Python 3.13 or 3.14
- Node.js (v18+) & npm

### 1. Backend Setup
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
- **Interactive Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
- **Operator Web Dashboard:** [http://localhost:5173](http://localhost:5173)

---

## 🧪 Running Tests & Verification

### Backend Integration Tests (177 Passed, 2 Skipped)
From repository root:
```bash
python -m pytest tests -v
```

### Frontend Unit Tests (41 Passed)
From repository root:
```bash
node --test frontend/src/components/VillageMap/*.test.js frontend/src/components/NetworkView/viewPref.test.js
```

### Frontend Lint & Production Build
```bash
cd frontend
npm run lint    # 11 baseline errors, 0 new
npm run build   # Vite production build succeeds
```

---

## 🎬 60-Second Demo Walkthrough for Judges

1. **Physical Overview**: Open [http://localhost:5173](http://localhost:5173) in `Map` mode. Observe the 15 nodes and 6 AP coverage circles laid out across the 3 rural villages in UP.
2. **Fly to Village**: In the bottom-right **Villages** panel, click **Bhatpur** or **Daulatpur** $\rightarrow$ the map smoothly flies and frames the village cluster and subscribers.
3. **RF Line-of-Sight**: Click wireless link **L3** (or **L7**) $\rightarrow$ inspect the popup showing path distance ($3.2\text{ km}$), carrier band ($5\text{ GHz}$), $F_1$ radius ($6.93\text{ m}$), and 60% clearance ($4.16\text{ m}$). Click **L1** $\rightarrow$ note Fresnel details are cleanly suppressed for optical fiber.
4. **Trigger Fault**: In the **Lab Panel**, click **Degrade L3 High** $\rightarrow$ link L3 turns thick pulsing red, AP1 circle shifts to a red dashed blast indicator, and subscriber counts update.
5. **AI Audio Explanation**: Open the Incident Drawer and click **Generate Audio Explanation** (with Sarvam key configured or preview) to hear the Hindi audio alert.
6. **Heal Network**: Click **Baseline Restore** $\rightarrow$ all alerts, dashed blast circles, and pulsing rings instantly clear back to healthy emerald.
7. **Toggle Views**: Click **Graph** in the top-right view toggle $\rightarrow$ examine the logical React Flow canvas. Reload the page to confirm preference persistence.

---

## 🏛️ System Architecture

```
                      +-----------------------------+
                      | React Frontend (Vite) :5173 |
                      | - Leaflet India Village Map |
                      | - React Flow TopologyCanvas |
                      +--------------+--------------+
                                     | HTTP REST + WebSocket
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

---

## 📚 Documentation Index

- 📋 [**API Contract (`docs/api-contract.md`)**](docs/api-contract.md): Strict HTTP REST API contract for all endpoints, request bodies, geographic schemas, and response formats.
- 📘 [**Backend Handover Guide (`docs/backend-handover.md`)**](docs/backend-handover.md): Architecture, setup, endpoints, engine integration, limitations, and troubleshooting.
- 🕸️ [**Graph Model & Engine (`docs/graph-model.md`)**](docs/graph-model.md): Neo4j schema, Cypher queries, simulated telemetry model, and explainable fault localization algorithms.
- 🧪 [**Test Plan & Verification Matrix (`docs/test-plan.md`)**](docs/test-plan.md): Test suite breakdown and verification matrix.

---

## 👥 Module Ownership

- **Member 1 (Graph Engine):** Owns `backend/app/engine/` (Neo4j driver, Cypher queries, in-memory graph store, diagnostic engine, simulated telemetry generator).
- **Member 2 (Backend & Operations):** Owns `backend/app/api/`, `backend/app/providers/`, `backend/app/schemas/`, `backend/app/db/`, `backend/app/config.py`, `backend/app/main.py`, `tests/api/`, and backend documentation.
- **Member 3 (Frontend):** Owns `frontend/` (React, Leaflet VillageMap, React Flow TopologyCanvas, Vite dev server, operator dashboard UI).
