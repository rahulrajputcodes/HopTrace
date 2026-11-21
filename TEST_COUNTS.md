# HopTrace Test Counts & Quality Gate Report

Generated at: 2026-11-21 14:43 IST  
Git Tag: `finale-start`

---

## Executive Summary

| Test Suite | Total Tests | Passed | Failed | Skipped | Pass Rate | Execution Time |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Backend Unit & Integration Tests (pytest)** | 271 | **269** | 0 | 2* | **100%** | 27.48s |
| **Frontend Unit Tests (node --test)** | 57 | **57** | 0 | 0 | **100%** | 0.33s |
| **Frontend Code Quality (ESLint)** | All files | **0 errors** | 0 warnings | - | **100%** | ~15s |
| **Combined Full-Stack Total** | **328** | **326** | **0** | **2** | **100%** | - |

*\*Note: 2 skipped tests require live physical network interface hardware (tun/tap).*

---

## 1. Backend Test Breakdown (`python -m pytest tests -v`)

### Agent Tests (`tests/agent/`) - 15 Tests
- `tests/agent/test_agent_field_hardening.py`:
  - `test_agent_preflight_check_flag`: PASS (parallel node & backend API probing)
  - `test_agent_exponential_backoff`: PASS (resilience against backend outage)
  - `test_agent_ping_jitter_extraction`: PASS (mdev / jitter extraction)
  - `test_agent_graceful_shutdown`: PASS (SIGINT / SIGTERM clean exit)
- `tests/agent/test_hoptrace_agent.py`: 11 tests PASS (synthetic ping, traceroute, JSON telemetry upload)

### API Tests (`tests/api/`) - 102 Tests
- `test_agents.py`: Agent registration, heartbeat, and offline TTL tracking (5 tests)
- `test_auth.py`: Token generation, validation, and rejection (6 tests)
- `test_explanations.py`: Sarvam LLM, Bulbul TTS audio, fallback simulation (8 tests)
- `test_incidents.py`: Incident creation, state transitions, resolution (12 tests)
- `test_measurements_ingest.py`: High-throughput metric ingestion & validation (14 tests)
- `test_probes_api.py`: Probing paths, cycle detection, synthetic hop simulation (10 tests)
- `test_security.py`: Rate limiting, XSS prevention, CORS policy, header hardening (8 tests)
- `test_subscribers.py`: Subscriber CRUD, payment status, QR payload (9 tests)
- `test_telemetry_ws_live.py`: WebSocket broadcast, live streaming, reconnection (12 tests)
- `test_topology.py` & `test_topology_v2.py`: GIS endpoints, geo-coordinates, SLA metrics (18 tests)

### Engine & Analytics Tests (`tests/engine/`) - 152 Tests
- `test_baselines_learned.py`: EWMA baselines persistence in SQLite across server restarts (7 tests)
- `test_cause.py`: Root Cause Analysis, graph traversal, and fault isolation (16 tests)
- `test_diagnostics.py`: Anomaly z-scoring, network jitter, loss attribution (24 tests)
- `test_incident_persistence.py`: DB schema persistence, event log journaling (11 tests)
- `test_incident_sla.py`: Village SLA uptime %, outage duration, penalty calculations (5 tests)
- `test_live_ttl.py`: Stale telemetry decay and connectivity timeouts (8 tests)
- `test_neo4j_client.py` & `test_neo4j_store.py`: Graph DB queries and in-memory dual fallback (14 tests)
- `test_predictive.py`: Linear regression failure prediction, risk ETA derivation (18 tests)
- `test_probes_derivation.py`: Active probing path selection, hop matrix (12 tests)
- Remaining engine and mathematical model tests: (37 tests)

### Demo Runner Tests - 2 Tests
- `tests/test_demo_runner.py`: End-to-end multi-phase judging scenario simulation (2 tests)

---

## 2. Frontend Test Breakdown (`node --test ...`) - 57 Tests

### View Preferences & Storage (`frontend/src/components/NetworkView/viewPref.test.js`) - 6 Tests
- Default view recovery, valid storage retrieval, fallback on invalid storage, fault tolerance when `localStorage` throws.

### GIS Map Model & Bounds (`frontend/src/components/VillageMap/*.test.js`) - 28 Tests
- `computeBounds`: Bounding box calculation, non-finite lat/lon handling.
- `parseGHz` & `fresnelF1Metres`: Exact 60% first Fresnel zone clearance for links L3, L7, and L12.
- `getLinkMidpoint` & `getPredictedEtaMinutes`: Midpoint and risk ETA badge formatting.
- `getNodeIconConfig` & `getSuspectedRingConfig`: Distinct SVG/DivIcon markers, suspected rings, blast radius badges.
- `buildMapModel`: Healthy baseline, L3 degradation, suspected link/blast APs, instant clearing upon incident resolution.
- `buildFailurePath`: Tree traversal from gateway GW1 down to leaf wireless APs.

### Layer Controls & Telemetry History (`frontend/src/lib/*.test.js`) - 23 Tests
- `riskColor`: Threshold verification (nominal, elevated, critical).
- `getLinkRisk`: Score precedence hierarchy (snapshot > liveMap > fallback).
- `getLinkDashArray` & `getLinkStrokeWidth`: Visual styling and dashed stroke rules.
- `villageStatusColor`: Backend status mapping for Rampur, Bhatpur, and Daulatpur.
- `freshnessStyle`, `formatLastSeen`, `isHealthyForKpi`: Real-time data freshness monitoring.

---

## 3. Screenshots Archived

1. `screenshots/noc_dashboard.jpg` - NOC Operations Cockpit (Leaflet GIS, live telemetry history, signal loss/jitter/throughput, node status).
2. `screenshots/business_dashboard.jpg` - Business & Revenue Impact (Village coverage, SLA credit compensation monitor, Kirana subscriber operations).
