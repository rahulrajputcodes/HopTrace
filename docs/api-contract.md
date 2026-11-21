# HopTrace API Contract

Base path: /api/v1
Backend: Python + FastAPI

## 1. Health

GET /api/v1/health

Response:
{
  "status": "ok",
  "version": "0.1.0"
}

## 2. Network topology

GET /api/v1/topology

Returns the current network topology as a graph of nodes and links.

### Fields and Schema

#### Node fields:
- `id`: string, unique node identifier (e.g. "GW1", "R1", "AP1").
- `type`: string, one of `gateway`, `router`, `wireless_bridge`, `access_point`.
- `label`: string, human-readable display label.
- `status`: string, one of `healthy`, `degraded`, `failed`, `unknown`.
- `lat`: optional float between -90 and 90, WGS-84 latitude (`null` when absent). Note: lat/lon coordinates are illustrative placement, not surveyed.
- `lon`: optional float between -180 and 180, WGS-84 longitude (`null` when absent).
- `village`: optional string, lowercase village identifier (`null` when absent). Valid values include `rampur`, `bhatpur`, `daulatpur`, and `block_hq`. Note that `"block_hq"` is a valid node village for gateway GW1 that is not present in `/villages`.
- `coverage_radius_m`: optional integer > 0, coverage radius in metres for access points (`null` when absent; present only on `access_point` nodes).

#### Link fields:
- `id`: string, unique link identifier (e.g. "L1", "L3").
- `source`: string, source node ID.
- `target`: string, target node ID.
- `status`: string, one of `healthy`, `degraded`, `failed`, `unknown`.
- `latency_ms`: optional float, one-way latency in milliseconds (`null` when absent).
- `packet_loss_pct`: optional float, packet loss percentage (`null` when absent).
- `throughput_mbps`: optional float, throughput in megabits per second (`null` when absent).
- `distance_km`: optional float, link distance in kilometres (`null` when absent).
- `medium`: optional string, physical transmission medium: `fiber`, `wireless_ptp`, or `ethernet` (`null` when absent).
- `frequency`: optional string, wireless operating frequency such as `"5GHz"` or `"60GHz"` (`null` when absent).

All additions are backward compatible; existing clients expecting the base four fields on nodes and seven fields on links can consume responses without error, and unset optional fields serialize as explicit `null`.

#### Response Example:
```json
{
  "nodes": [
    {
      "id": "R1",
      "type": "router",
      "label": "Rampur Core Router (Tower)",
      "status": "healthy",
      "lat": 27.20000,
      "lon": 80.60000,
      "village": "rampur",
      "coverage_radius_m": null
    },
    {
      "id": "AP1",
      "type": "access_point",
      "label": "Rampur North Market AP",
      "status": "healthy",
      "lat": 27.22906,
      "lon": 80.60602,
      "village": "rampur",
      "coverage_radius_m": 300
    }
  ],
  "links": [
    {
      "id": "L3",
      "source": "WB1",
      "target": "WB2",
      "status": "healthy",
      "latency_ms": 25.0,
      "packet_loss_pct": 0.5,
      "throughput_mbps": 35.0,
      "distance_km": 3.2,
      "medium": "wireless_ptp",
      "frequency": "5GHz"
    }
  ],
  "data_source": "simulated"
}
```

data_source must be "simulated" or "measured".

## 3. Run a network test scenario

POST /api/v1/lab/run

Request:
{
  "scenario": "degrade_link",
  "target_link_id": "L2",
  "severity": "high"
}

Supported scenarios:
baseline, degrade_link, access_point_failure,
upstream_failure, ambiguous_fault

severity:
low, medium, high

target_link_id is required for degrade_link.
target_node_id is required for component failure scenarios.

Response:
{
  "run_id": "run-001",
  "data_source": "simulated",
  "measurements_count": 20,
  "incident_id": "incident-001"
}

The injected fault must remain separate from the
diagnostic engine's prediction. The diagnostic engine
must infer the likely fault from the observations.
Expected fault information must not be passed to the
diagnostic algorithm.

## 4. Latest incident

GET /api/v1/incidents/latest

Returns the most recent diagnostic incident, or null
if no incident has been created.

## 5. Incident details

GET /api/v1/incidents/{incident_id}

Response:
{
  "id": "incident-001",
  "run_id": "run-001",
  "status": "open",
  "suspected_component_id": "L2",
  "suspected_component_type": "link",
  "summary": "Potential intermediate-link degradation",
  "confidence_score": null,
  "evidence": [],
  "uncertainty_note": null,
  "data_source": "simulated",
  "created_at": "2026-10-29T10:00:00Z"
}

confidence_score may be null until a documented
scoring method is implemented. Do not invent confidence
values or claim validated accuracy without testing.

Evidence should include observed metrics and relevant
baselines or thresholds when available.

## 6. Affected subscribers

GET /api/v1/incidents/{incident_id}/affected-subscribers

Response:
{
  "count": 2,
  "subscribers": [
    {
      "id": "SUB101",
      "display_name": "Demo Subscriber 101",
      "access_point_id": "AP1"
    }
  ]
}

The count must match the returned subscriber records.
Determine affected subscribers using network dependencies.

## 7. Run measurements

GET /api/v1/runs/{run_id}/measurements

Response:
{
  "run_id": "run-001",
  "data_source": "simulated",
  "measurements": [
    {
      "component_id": "L2",
      "timestamp_utc": "2026-10-29T10:00:00Z",
      "latency_ms": 180.0,
      "packet_loss_pct": 25.0,
      "throughput_mbps": null,
      "connectivity_ok": true
    }
  ]
}

These values are illustrative. Actual responses must contain
measurements produced by the testbed or measurement collector.
Unavailable values must be null, not fabricated.

## 8. List subscribers

GET /api/v1/subscribers

Response:
{
  "subscribers": [
    {
      "id": "SUB101",
      "display_name": "Demo Subscriber 101",
      "plan": "Basic",
      "access_point_id": "AP1",
      "status": "active",
      "payment_status": "paid",
      "due_date": "2026-11-01"
    }
  ]
}

Subscriber and payment records in the prototype may use
clearly labelled demo business data.

## 9. Record a payment reminder

POST /api/v1/subscribers/{subscriber_id}/remind

Request:
{
  "language": "hi"
}

Response:
{
  "subscriber_id": "SUB101",
  "status": "recorded",
  "delivery_status": "not_sent"
}

The initial prototype records a reminder action.
It must not claim an SMS or WhatsApp message was delivered
unless a real messaging integration confirms delivery.

## 10. Explain an incident in Hindi

POST /api/v1/incidents/{incident_id}/explain

Request:
{
  "language": "hi"
}

Response:
{
  "incident_id": "incident-001",
  "language": "hi",
  "explanation": "Hindi explanation based on verified incident data",
  "provider": "sarvam"
}

Use Sarvam for the language interaction. The explanation
must be grounded in the actual incident result, not invented
measurements or subscriber counts.

## Shared implementation rules

1. Neo4j stores network topology and relationships.
2. The graph engine performs fault localization and dependency analysis.
3. FastAPI exposes the API contract above.
4. SQLite stores initial operational records.
5. React and TypeScript consume API responses.
6. Sarvam explains verified application results.
7. All timestamps use ISO 8601 UTC.
8. Missing measurements must remain null.
9. Simulated and measured data must be clearly distinguished.
10. API keys and credentials must never be committed to GitHub.

All members must communicate contract changes before
implementing incompatible interfaces.


---

## Part 1 Contract Additions (Live Truth Pipeline & Monitoring Blind-Spot)

### 11. Configuration & Freshness Semantics

#### Environment Settings
- `DATA_MODE`: `"demo"` (default) | `"live"`. In `live` mode, unmonitored links receive no simulated fill (`no_data`).
- `LIVE_TTL_SECONDS`: integer, default `30`. Age threshold for `live` measurements.
- `AGENT_SILENT_SECONDS`: integer, default `20`. Inactivity threshold before an agent is marked `silent`.

#### Freshness States
Let `age` = `now_utc` - `last_seen_utc` of measurement:
- `age <= LIVE_TTL_SECONDS` -> `"live"`
- `LIVE_TTL_SECONDS < age <= 3 * LIVE_TTL_SECONDS` -> `"stale"`
- older, or never seen in `live` mode -> `"no_data"`
- `DATA_MODE=demo` and link never had live data -> `"simulated"`

### 12. WebSocket Telemetry Stream Extension

Endpoint: `WS /ws/telemetry`

Message type: `telemetry_batch`

Extended batch fields:
- `data_mode`: `"demo"` | `"live"`
- `agents`: array of agent status objects (see `GET /api/v1/agent/status`)
- `measurements[].freshness`: `"live"` | `"stale"` | `"no_data"` | `"simulated"`
- `measurements[].last_seen_utc`: ISO 8601 UTC string or `null`

```json
{
  "type": "telemetry_batch",
  "tick": 42,
  "timestamp_utc": "2026-11-15T10:42:11Z",
  "data_mode": "live",
  "measurements": [
    {
      "link_id": "L3",
      "latency_ms": 25.0,
      "packet_loss_pct": 0.5,
      "throughput_mbps": 35.0,
      "connectivity_ok": true,
      "freshness": "live",
      "last_seen_utc": "2026-11-15T10:42:11Z"
    }
  ],
  "agents": [
    {
      "agent_id": "agent-rampur-1",
      "site_id": "rampur",
      "last_seen_utc": "2026-11-15T10:42:11Z",
      "status": "online",
      "silent_for_seconds": 0,
      "buffered_count": 0
    }
  ]
}
```

### 13. Path Probes

POST /api/v1/probes/path

Header (optional): `X-API-Key` (matches `INGEST_API_KEY`)

Request:
```json
{
  "agent_id": "agent-rampur-1",
  "vantage_node_id": "GW1",
  "timestamp": "2026-11-15T10:42:11Z",
  "results": [
    {
      "node_id": "R1",
      "reachable": true,
      "latency_ms": 12.4,
      "packet_loss_pct": 0.0
    },
    {
      "node_id": "WB3",
      "reachable": false,
      "latency_ms": null,
      "packet_loss_pct": 100.0
    }
  ]
}
```

Response:
```json
{
  "status": "ok",
  "derived_links": 14,
  "first_failed_nodes": ["WB3"],
  "incident_id": "inc-001"
}
```
Validation: unknown `node_id` returns HTTP 422.

### 14. Agent Heartbeat & Status

POST /api/v1/agent/heartbeat

Header (optional): `X-API-Key` (matches `INGEST_API_KEY`)

Request:
```json
{
  "agent_id": "agent-rampur-1",
  "site_id": "rampur",
  "timestamp": "2026-11-15T10:42:11Z",
  "buffered_count": 0,
  "version": "2.1"
}
```

Response:
```json
{
  "status": "ok",
  "agent_id": "agent-rampur-1"
}
```

---

GET /api/v1/agent/status

Response:
```json
{
  "agents": [
    {
      "agent_id": "agent-rampur-1",
      "site_id": "rampur",
      "last_seen_utc": "2026-11-15T10:42:11Z",
      "status": "online",
      "silent_for_seconds": 0,
      "buffered_count": 0
    }
  ]
}
```
Note: Agent status `silent` represents a monitoring blind-spot warning, not a network fault incident.

### 15. Incident Details Schema Additions

Fields added to `IncidentDetails`:
- `cause`: optional string (`"power_outage"` | `"fiber_cut"` | `"rf_degradation"` | `"upstream_failure"` | `"unknown"`)
- `cause_confidence`: optional float (`0.0` to `0.85`)
- `cause_reasoning`: list of deterministic human-readable explanation strings
- `hop_trace`: list of `HopResult` objects:
  - `node_id`: string
  - `link_id`: optional string (inbound link to node; null for vantage node)
  - `depth`: integer hops from vantage node
  - `reachable`: boolean
  - `latency_ms`: optional float cumulative RTT
  - `packet_loss_pct`: optional float
  - `status`: string (`"ok"` | `"degraded"` | `"failed"` | `"behind_failure"` | `"no_data"`)
