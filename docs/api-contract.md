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

Response:
{
  "nodes": [
    {
      "id": "GW1",
      "type": "gateway",
      "label": "Upstream Gateway",
      "status": "healthy"
    }
  ],
  "links": [
    {
      "id": "L1",
      "source": "GW1",
      "target": "HOP1",
      "status": "healthy",
      "latency_ms": 20.0,
      "packet_loss_pct": 0.0,
      "throughput_mbps": 40.0
    }
  ],
  "data_source": "simulated"
}

Node types:
gateway, router, wireless_bridge, access_point

Link and measurement values may be null when unavailable.

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

## Section 5 — Predictive Fault AI (feat/predictive)

> Owner: Member 2. All prediction fields are OPTIONAL and ADDITIVE.
> No existing field is renamed or removed.

### 5.1 Gradual Degradation Scenario

`POST /api/v1/lab/run` now accepts `scenario: "gradual_degradation"`.

Request (same shape as `degrade_link`):
```json
{
  "scenario": "gradual_degradation",
  "target_link_id": "L3",
  "severity": "high"
}
```

Behaviour:
- Registers a linear ramp on the target link (RAMP_TICKS = 40 ticks ≈ 2 min).
- At tick 0 (the instant of this call) progress = 0: link is at baseline,
  `incident_id` is always `null`.
- The WebSocket streaming loop (`/ws/telemetry`) advances the ramp each tick.
- A `baseline` run clears the ramp; any subsequent `degrade_link` run also
  clears it.

Response: same `LabRunResponse` shape as all other scenarios.

---

### 5.2 GET /api/v1/topology/risk

Returns per-link current telemetry plus optional ETA-to-failure predictions.

```
GET /api/v1/topology/risk
200 OK
Content-Type: application/json
```

Response — array of `LinkRiskItem`:
```json
[
  {
    "link_id": "L3",
    "connectivity_ok": true,
    "packet_loss_pct": 8.2,
    "latency_ms": 87.4,
    "throughput_mbps": 18.1,
    "data_source": "simulated",
    "predicted_eta_minutes": 14.0,
    "prediction_confidence": "medium",
    "prediction_r2": 0.71
  }
]
```

**Optional prediction fields** (null when not available):

| Field | Type | Description |
|-------|------|-------------|
| `predicted_eta_minutes` | float \| null | Simulated minutes until D_FAIL threshold is crossed |
| `prediction_confidence` | "high"\|"medium"\|"low"\|null | R²-based confidence: high ≥ 0.8 (n≥10), medium ≥ 0.5 |
| `prediction_r2` | float \| null | Theil-Sen trend R² |

Fields are null when:
- Fewer than 6 samples stored for the link.
- Link is stable (slope ≤ MIN_SLOPE = 0.002).
- Link is already at or past D_FAIL = 0.6.
- Link has `connectivity_ok=False` (already failed).

Empty array is returned when the time-series store has no data (server just
started or no streaming ticks have occurred).

---

### 5.3 WebSocket ws://host/api/v1/ws/telemetry

Streams simulated telemetry at 3-second intervals.

Message format (flat JSON, one object per tick):
```json
{
  "tick": 12,
  "links": [
    {
      "link_id": "L3",
      "connectivity_ok": true,
      "packet_loss_pct": 8.2,
      "latency_ms": 87.4,
      "throughput_mbps": 18.1,
      "data_source": "simulated",
      "predicted_eta_minutes": 14.0,
      "prediction_confidence": "medium",
      "prediction_r2": 0.71
    }
  ]
}
```

- All `links` entries are flat objects (no nesting).
- Prediction fields follow the same null rules as §5.2.
- The streaming loop also runs the diagnostic engine and persists newly opened
  incidents to SQLite (at most one open incident per suspected component).

---

### 5.4 Prediction Design Notes

**Degradation Index (D)**:
```
D = (0.30*s_loss + 0.20*s_lat + 0.10*s_tp) / 0.60,  D ∈ [0, 1]
```
where s_loss/s_lat/s_tp use identical normalisation to DiagnosticEngine.evaluate_link.
The connectivity term is excluded (link-down ≠ about-to-fail).

**Why not risk_score?**
The time-series risk_score uses EWMA-relative metrics.  EWMA tracks slow ramps,
so risk_score stays below ~55 and never reaches 75 (the alarm threshold).
D is always relative to the documented static baseline, so it rises monotonically
with degradation and reaches D_FAIL = 0.6 at roughly "medium" fault severity.

**Lead time** (L3, high severity, RAMP_TICKS=40):
- Tick 5: first prediction issued (D ≈ 0.12, slope established)
- Tick 8: diagnostic engine opens incident (composite score > 0.10)
- Tick 23: D crosses D_FAIL = 0.6
- **Lead time ≈ 3 ticks (6 simulated minutes) before the incident opens**
