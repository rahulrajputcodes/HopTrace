# HopTrace Graph Model & Network Intelligence Engine

**Project:** HopTrace  
**Hackathon:** hackFront India — T3.2, Running a Village Internet Business  
**Module:** Network Intelligence Engine (`backend/app/engine`)  
**Specification:** Aligned with [`docs/api-contract.md`](file:///c:/Users/rajva/Documents/HopTrace/docs/api-contract.md)

---

## 1. Graph Model & Schema

HopTrace uses Neo4j to model the physical and logical backhaul infrastructure of a rural village internet service provider. Network components and subscriber dependencies are represented as native graph nodes and relationships.

### 1.1 Node Labels and Properties

#### `Device` Nodes
Every physical network equipment item carries the primary label `:Device` and a secondary type label:

1. **`:Gateway:Device`**
   - **Role:** Point of Presence (PoP) upstream fiber backhaul termination.
   - **Properties:**
     - `id: STRING` (e.g., `"GW1"`, unique key)
     - `label: STRING` (e.g., `"Upstream Gateway (Fiber PoP)"`)
     - `type: STRING` (`"gateway"`)
     - `status: STRING` (`"healthy"`, `"degraded"`, `"down"`)

2. **`:Router:Device`**
   - **Role:** Core village distribution router (e.g. mounted on a panchayat tower).
   - **Properties:** `id`, `label`, `type` (`"router"`), `status`

3. **`:WirelessBridge:Device`**
   - **Role:** Point-to-Point (PtP) wireless transmission bridge (e.g. 5GHz/60GHz link across village terrain).
   - **Properties:** `id`, `label`, `type` (`"wireless_bridge"`), `status`

4. **`:AccessPoint:Device`**
   - **Role:** Wireless access point serving local village wards, markets, and panchayats.
   - **Properties:** `id`, `label`, `type` (`"access_point"`), `status`

#### `Subscriber` Nodes
Represents village businesses, institutions, and community members receiving internet service:
- **Label:** `:Subscriber`
- **Properties:**
  - `id: STRING` (e.g., `"SUB101"`, unique key)
  - `display_name: STRING` (e.g., `"Ramesh Patel (Kishan Kirana)"`)
  - `access_point_id: STRING` (e.g., `"AP1"`)
  - `plan: STRING` (`"Basic"`, `"Enterprise"`, `"Community"`)
  - `status: STRING` (`"active"`, `"suspended"`)
  - `payment_status: STRING` (`"paid"`, `"due"`)
  - `due_date: STRING` (ISO 8601 date, e.g., `"2026-11-01"`)

---

### 1.2 Relationship Types

#### 1. `[:LINK]`
Connects two devices from upstream source to downstream target:
```cypher
(source:Device)-[:LINK {
  id: "L3",
  status: "healthy",
  latency_ms: 25.0,
  packet_loss_pct: 0.5,
  throughput_mbps: 35.0
}]->(target:Device)
```
- **Properties:**
  - `id: STRING` (stable link identifier, e.g., `"L1"`, `"L2"`)
  - `status: STRING` (`"healthy"`, `"degraded"`, `"down"`)
  - `latency_ms: FLOAT`
  - `packet_loss_pct: FLOAT`
  - `throughput_mbps: FLOAT`

#### 2. `[:SERVES]`
Connects an access point to a subscriber:
```cypher
(ap:AccessPoint:Device)-[:SERVES]->(sub:Subscriber)
```

---

### 1.3 Graph Constraints

Unique identity constraints ensure idempotent operations:

```cypher
CREATE CONSTRAINT device_id_unique IF NOT EXISTS
FOR (d:Device) REQUIRE d.id IS UNIQUE;

CREATE CONSTRAINT subscriber_id_unique IF NOT EXISTS
FOR (s:Subscriber) REQUIRE s.id IS UNIQUE;
```

---

## 2. Initial Topology

The initial testbed models a rural village internet setup:

```
[GW1: Upstream Gateway]
         |
         | L1 (Fiber Backhaul)
         v
  [R1: Village Core Router]
     |                 |
     | L2              | L5 (Ethernet Distribution)
     v                 v
[WB1: Bridge Tx]   [AP2: South Village AP]
     |                 |
     | L3 (PtP Hop)    +---> SUB201 (Primary Health Centre)
     v                 +---> SUB202 (Govt Secondary School)
[WB2: Bridge Rx]       +---> SUB203 (Manoj CSC Center)
     |
     | L4 (Ethernet)
     v
[AP1: North Village AP]
     |
     +---> SUB101 (Ramesh Patel - Kishan Kirana)
     +---> SUB102 (Gram Panchayat e-Seva Kendra)
```

### Topology Routing Assumption
**Single-path routing:** Subscribers do not have alternate redundant paths unless explicitly represented in the graph. Therefore, failure or severe degradation on an intermediate backhaul link (e.g., `L3`) severs or degrades backhaul for all access points and subscribers located topologically downstream from the link target.

---

## 3. Parameterized Cypher Queries

### 3.1 Idempotent Seeding Query
Running this query multiple times does not duplicate nodes or relationships:

```cypher
// 1. Upsert Devices
UNWIND $devices AS dev
MERGE (d:Device {id: dev.id})
SET d.label = dev.label,
    d.type = dev.type,
    d.status = dev.status
FOREACH (_ IN CASE WHEN dev.type = 'gateway' THEN [1] ELSE [] END | SET d:Gateway)
FOREACH (_ IN CASE WHEN dev.type = 'router' THEN [1] ELSE [] END | SET d:Router)
FOREACH (_ IN CASE WHEN dev.type = 'wireless_bridge' THEN [1] ELSE [] END | SET d:WirelessBridge)
FOREACH (_ IN CASE WHEN dev.type = 'access_point' THEN [1] ELSE [] END | SET d:AccessPoint);

// 2. Upsert Subscribers
UNWIND $subscribers AS sub
MERGE (s:Subscriber {id: sub.id})
SET s.display_name = sub.display_name,
    s.access_point_id = sub.access_point_id,
    s.plan = sub.plan,
    s.status = sub.status,
    s.payment_status = sub.payment_status,
    s.due_date = sub.due_date;

// 3. Upsert Links
UNWIND $links AS lk
MATCH (src:Device {id: lk.source})
MATCH (tgt:Device {id: lk.target})
MERGE (src)-[r:LINK {id: lk.id}]->(tgt)
SET r.status = lk.status,
    r.latency_ms = lk.latency_ms,
    r.packet_loss_pct = lk.packet_loss_pct,
    r.throughput_mbps = lk.throughput_mbps;

// 4. Upsert AccessPoint -> Subscriber relationships
UNWIND $subscribers AS sub
MATCH (ap:Device {id: sub.access_point_id})
MATCH (s:Subscriber {id: sub.id})
MERGE (ap)-[r:SERVES]->(s);
```

### 3.2 Retrieve Topology Query
```cypher
MATCH (d:Device)
RETURN d.id AS id, d.type AS type, d.label AS label, d.status AS status
ORDER BY d.id;

MATCH (src:Device)-[r:LINK]->(tgt:Device)
RETURN r.id AS id, src.id AS source, tgt.id AS target, r.status AS status,
       r.latency_ms AS latency_ms, r.packet_loss_pct AS packet_loss_pct,
       r.throughput_mbps AS throughput_mbps
ORDER BY r.id;
```

### 3.3 Affected Subscribers Dependency Query
Finds all subscribers whose connection depends on a suspected link:

```cypher
MATCH (src:Device)-[rel:LINK {id: $component_id}]->(tgt:Device)
MATCH (tgt)-[:LINK*0..]->(ap:Device)-[:SERVES]->(sub:Subscriber)
WHERE ap.type = 'access_point'
RETURN DISTINCT sub.id AS id, sub.display_name AS display_name, ap.id AS access_point_id
ORDER BY sub.id;
```

When querying a suspected node (e.g. an access point or core router):
```cypher
MATCH (n:Device {id: $component_id})-[:LINK*0..]->(ap:Device)-[:SERVES]->(sub:Subscriber)
WHERE ap.type = 'access_point'
RETURN DISTINCT sub.id AS id, sub.display_name AS display_name, ap.id AS access_point_id
ORDER BY sub.id;
```

---

## 4. Simulated Telemetry Model

All telemetry produced by the engine is explicitly marked with `"data_source": "simulated"`. Measurements are deterministic and generated using a documented mathematical baseline model. **No LLM is used to generate measurements, and they are not claimed to be from a live ISP.**

### 4.1 Documented Baselines
- **`L1` (Fiber Backhaul):** Latency = 15.0 ms, Packet Loss = 0.0%, Throughput = 100.0 Mbps, Connectivity = OK
- **`L2` (Tower Ethernet):** Latency = 2.0 ms, Packet Loss = 0.0%, Throughput = 80.0 Mbps, Connectivity = OK
- **`L3` (PtP Wireless Bridge):** Latency = 25.0 ms, Packet Loss = 0.5%, Throughput = 35.0 Mbps, Connectivity = OK
- **`L4` (North AP Ethernet):** Latency = 3.0 ms, Packet Loss = 0.0%, Throughput = 50.0 Mbps, Connectivity = OK
- **`L5` (South AP Ethernet):** Latency = 5.0 ms, Packet Loss = 0.0%, Throughput = 60.0 Mbps, Connectivity = OK

### 4.2 Controlled Degradation Scaling
When a scenario injects a fault into a link, the metrics scale predictably:
- **Low severity:** Latency +35 ms, Packet Loss +5.0%, Throughput $\times 0.70$ (-30%)
- **Medium severity:** Latency +90 ms, Packet Loss +15.0%, Throughput $\times 0.40$ (-60%)
- **High severity:** Latency +175 ms, Packet Loss +25.0%, Throughput $\times 0.15$ (-85%)

---

## 5. Explainable Fault Localization Engine

### 5.1 CRITICAL VALIDATION RULE
The diagnostic function **does not receive** the injected fault ID, scenario name, or ground truth label as input. It inspects **solely** the observed measurements, documented baselines, and graph topology. The test harness compares the prediction with the ground truth only in the evaluation assertion layer.

### 5.2 Metric Anomaly Normalization
For each link $l$:
1. **Connectivity Failure ($s_{\text{conn}}$):**
   $$s_{\text{conn}} = \begin{cases} 1.0 & \text{if } \text{connectivity\_ok is False} \\ 0.0 & \text{otherwise} \end{cases}$$
2. **Packet Loss Abnormality ($s_{\text{loss}}$):**
   $$\Delta_{\text{loss}} = \max(0, \text{loss}_{\text{obs}} - \text{loss}_{\text{base}})$$
   $$s_{\text{loss}} = \begin{cases} 0.0 & \text{if } \Delta_{\text{loss}} \le 1.0\% \\ \min(1.0, \frac{\Delta_{\text{loss}}}{25.0}) & \text{otherwise} \end{cases}$$
3. **Latency Inflation ($s_{\text{lat}}$):**
   $$\Delta_{\text{lat}} = \max(0, \text{latency}_{\text{obs}} - \text{latency}_{\text{base}})$$
   $$s_{\text{lat}} = \begin{cases} 0.0 & \text{if } \Delta_{\text{lat}} \le 10.0\text{ ms} \\ \min(1.0, \frac{\Delta_{\text{lat}}}{150.0}) & \text{otherwise} \end{cases}$$
4. **Throughput Degradation ($s_{\text{tp}}$):**
   $$\Delta_{\text{drop}} = \max(0, \frac{\text{tp}_{\text{base}} - \text{tp}_{\text{obs}}}{\text{tp}_{\text{base}}})$$
   $$s_{\text{tp}} = \begin{cases} 0.0 & \text{if } \Delta_{\text{drop}} \le 0.15 \\ \min(1.0, \frac{\Delta_{\text{drop}} - 0.15}{0.70}) & \text{otherwise} \end{cases}$$

### 5.3 Composite Diagnostic Score
The overall anomaly score $S \in [0.0, 1.0]$ combines the normalized metrics with explainable weights:
$$S = (0.40 \cdot s_{\text{conn}}) + (0.30 \cdot s_{\text{loss}}) + (0.20 \cdot s_{\text{lat}}) + (0.10 \cdot s_{\text{tp}})$$

- **Detection Threshold:** $S \ge 0.10$ marks a degraded component.
- **Normal Baseline:** $S < 0.10$ indicates normal operation (incident not opened).

### 5.4 Ambiguity & Missing Telemetry Rules
- **Ambiguous Evidence:** If the top two suspect links both score $\ge 0.10$ and $|S_1 - S_2| \le 0.08$, the engine reports ambiguity:
  - `uncertainty_note`: `"Ambiguous evidence: Link 'L2' (score 0.42) and Link 'L3' (score 0.42) show comparable degradation..."`
  - `confidence_score`: Proportional to score difference, avoiding false claims of certainty.
- **Missing Telemetry:** If measurements are null or omitted, the link is **never assumed healthy**. It is marked unmonitored and an uncertainty warning is attached to the incident.

---

## 6. Python Engine Interfaces for Backend Integration

The backend developer can import stable, typed functions directly from `backend.app.engine`:

```python
from backend.app.engine import (
    seed_topology,
    get_topology,
    run_scenario,
    get_latest_incident,
    get_incident_details,
    get_affected_subscribers,
    get_run_measurements,
    check_neo4j_health,
)
```

### Interface Signatures

#### 1. `seed_topology(force_in_memory: bool = False) -> Dict[str, Any]`
Idempotently seeds nodes, links, and subscribers.
- **Returns:** `{"status": "seeded", "nodes_count": 6, "links_count": 5, "subscribers_count": 5}`

#### 2. `get_topology(force_in_memory: bool = False) -> NetworkTopology`
Returns topology matching `GET /api/v1/topology`.
- **Returns:** Pydantic `NetworkTopology` (`nodes`, `links`, `data_source="simulated"`).

#### 3. `run_scenario(scenario: str, target_link_id: Optional[str] = None, severity: str = "medium", ...) -> ScenarioRunResponse`
Executes simulated testbed, triggers fault localization, and registers run & incident.
- **Returns:** `ScenarioRunResponse(run_id="run-001", data_source="simulated", measurements_count=5, incident_id="incident-001")`

#### 4. `get_incident_details(incident_id: str) -> Optional[IncidentDetails]`
Retrieves incident matching `GET /api/v1/incidents/{incident_id}`.
- **Returns:** Pydantic `IncidentDetails` containing `suspected_component_id`, `evidence`, `uncertainty_note`, `confidence_score`.

#### 5. `get_latest_incident() -> Optional[IncidentDetails]`
Retrieves the most recent incident or `None` if no incident has been opened.

#### 6. `get_affected_subscribers(incident_id: str, force_in_memory: bool = False) -> AffectedSubscribersResponse`
Traces downstream subscribers matching `GET /api/v1/incidents/{incident_id}/affected-subscribers`.
- **Returns:** `AffectedSubscribersResponse(count=2, subscribers=[...])`

#### 7. `get_run_measurements(run_id: str) -> Optional[RunMeasurementsResponse]`
Retrieves telemetry measurements matching `GET /api/v1/runs/{run_id}/measurements`.

#### 8. `check_neo4j_health() -> Dict[str, Any]`
Verifies Neo4j connectivity.
- **Returns:** `{"connected": True/False, "uri": "...", "error": ...}`

---

## 7. Setup & Execution Commands

### Environment Variables & Neo4j Aura Configuration
Configure Neo4j credentials in `.env` (or OS environment):
```bash
# For Neo4j Aura (Cloud):
NEO4J_URI=neo4j+s://<dbid>.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_aura_password_here

# Or for local development:
# NEO4J_URI=neo4j://localhost:7687
# NEO4J_USERNAME=neo4j
# NEO4J_PASSWORD=your_password
```

### Security & Isolation
- **Credentials Protection:** Passwords and tokens are never printed or included in error logs. URIs are automatically sanitized.
- **Integration Test Isolation:** Live integration tests use isolated `TEST_` prefixed nodes and links. They never overwrite or mutate the village demo topology (`GW1`, `R1`, `SUB101`, etc.) and automatically clean up after execution.
- **Diagnostic Behavior:**
  - If credentials are not configured, integration tests skip cleanly with a specific explanation.
  - If credentials are configured but connectivity or authentication fails, tests report the actual error clearly.

### Running Tests
1. **Run pure unit tests (zero external dependencies required):**
   ```bash
   python -m pytest tests/engine -m "not integration" -v
   ```
2. **Run complete test suite (includes live Neo4j Aura integration tests):**
   ```bash
   python -m pytest tests/engine -v
   ```


---

## 8. Upstream Failure Scenario

### 8.1 Scenario Description

The `upstream_failure` scenario models a complete loss of the gateway backhaul link (`L1`) — the fiber PoP connection between `GW1` and `R1`. This is the most catastrophic failure mode: it terminates all internet connectivity for every subscriber in the village while interior infrastructure (bridges, access points, wired switches) remains locally powered and link-present.

### 8.2 Constants

```python
from backend.app.engine import GATEWAY_LINK_ID, INTERIOR_LINK_IDS

GATEWAY_LINK_ID = "L1"                          # The single upstream fiber backhaul link
INTERIOR_LINK_IDS = ["L2", "L3", "L4", "L5"]  # All downstream distribution links
```

These constants are centralized in `telemetry.py` and exported via `backend/app/engine/__init__.py`. Tests and diagnostic code import them to avoid magic strings.

### 8.3 Telemetry Fingerprint

When `upstream_failure` is active, each link reports:

| Link | `connectivity_ok` | `packet_loss_pct` | `throughput_mbps` | `latency_ms` | Interpretation |
|------|:-----------------:|:-----------------:|:-----------------:|:------------:|----------------|
| L1 (GW1 → R1) | `False` | 100.0 | 0.0 | `None` | Gateway link is down |
| L2 (R1 → WB1) | `True` | 100.0 | 0.0 | `None` | Locally up, no internet traffic |
| L3 (WB1 → WB2) | `True` | 100.0 | 0.0 | `None` | Locally up, no internet traffic |
| L4 (WB2 → AP1) | `True` | 100.0 | 0.0 | `None` | Locally up, no internet traffic |
| L5 (R1 → AP2) | `True` | 100.0 | 0.0 | `None` | Locally up, no internet traffic |

`latency_ms = None` on interior links because there is no routable internet path to measure round-trip time against. The diagnostic engine treats `None` latency as an unmonitored / unresolvable signal — never as healthy.

All measurements carry `data_source = "simulated"`.

### 8.4 Upstream Failure Detection Algorithm (`_detect_upstream_failure`)

The `DiagnosticEngine` runs this check **before** the standard per-link anomaly scoring. If all three conditions below are met, the engine returns a high-confidence upstream failure incident without falling through to the ambiguity logic:

| # | Condition | Rationale |
|---|-----------|-----------|
| 1 | Gateway link (`L1`) has `connectivity_ok = False` | Confirms the backhaul link is physically or logically down |
| 2 | **All** interior links have `packet_loss_pct >= 98.0%` AND `throughput_mbps == 0.0` | Confirms total saturation downstream — no internet traffic flows through any branch |
| 3 | At least one interior link has `connectivity_ok = True` | Rules out a simultaneous multi-segment hardware cascade; distinguishes upstream failure from a total infrastructure collapse |

If any condition fails the method returns `None`, and the standard scoring path handles the incident.

#### Confidence Assignment

| Situation | `diagnostic_score` | `confidence_score` | Explanation |
|-----------|:------------------:|:------------------:|-------------|
| Conditions 1–3 all met (interior links locally up) | `1.0` | `0.92` | Strong fingerprint; minor uncertainty because simulated measurements cannot capture every real-world edge case |
| Conditions 1–2 met but interior links also down | `1.0` | `0.70` | Evidence still points upstream but ambiguity with total-infrastructure collapse is higher |

The engine **never** fabricates a probability of correctness. The `0.92` / `0.70` figures are documented engineering estimates, not statistical claims.

### 8.5 Uniqueness of the Upstream Fingerprint

An intermediate link fault (e.g., `L3` degraded) shows high anomaly score on `L3` only; `L2` and `L5` remain within healthy baseline. The standard scoring path then correctly identifies `L3`.

An upstream failure shows **all five links simultaneously at 100% loss / zero throughput**. No single intermediate fault can produce this pattern across both independent distribution branches (`L2`→`L3`→`L4` and `L5`). `_detect_upstream_failure` exploits this fact for unambiguous identification.

### 8.6 Downstream Subscriber Impact

Because `L1` is the sole gateway link and the topology uses single-path routing with no redundancy, every subscriber is affected:

```
L1 failure → R1 isolated from internet
           ├── WB1 → WB2 → AP1 → SUB101, SUB102  (affected)
           └── AP2 → SUB201, SUB202, SUB203       (affected)
```

The existing `get_affected_subscribers` graph dependency query (§ 3.3) correctly returns all 5 subscribers when `suspected_component_id = "L1"`, because the query traverses `:LINK*0..` from the link's target device (`R1`) downstream through all access points.

### 8.7 Test Coverage

New tests in `tests/engine/test_upstream_failure.py`:

| Section | Tests |
|---------|-------|
| A — Telemetry correctness | Gateway link down; interior links locally up; measurements deterministic; all 5 links present |
| B — Diagnostic identification | Upstream fault identified; evidence content; uncertainty note present; no false alarm on baseline; direct engine class call |
| C — Ground-truth separation | Diagnostic signature does not accept `target_node_id`; inference without supplying topology |
| D — Subscriber impact | In-memory graph returns all 5 subscribers; full facade pipeline |
| E — Ambiguous / edge cases | Partial gateway degradation not classified as upstream failure; upstream-down with healthy interior falls to standard scoring |


---

## 9. Live Data Semantics, Freshness, & Hop-by-Hop Fault Derivation

### 9.1 Freshness States & Transitions

HopTrace enforces an honest live-data contract (§2.1) to ensure operators distinguish live telemetry from stale or simulated figures:

| Freshness State | Condition | Interpretation |
|---|---|---|
| `live` | `elapsed_sec <= LIVE_TTL_SECONDS` (30s) | Active edge agent telemetry received within TTL |
| `stale` | `LIVE_TTL_SECONDS < elapsed_sec <= 2 * LIVE_TTL_SECONDS` | Agent telemetry delayed; warning state before cutoff |
| `no_data` | `elapsed_sec > 2 * LIVE_TTL_SECONDS` (or never seen) | Telemetry expired; link marked unmonitored |
| `simulated` | `DATA_MODE="demo"` or scenario generator | Synthetic simulation for demonstrations |

```
[Agent Sample] ──(t=0)──> [LIVE] ──(t > 30s)──> [STALE] ──(t > 60s)──> [NO_DATA]
```

### 9.2 Backfill Separation Rules

When delayed or buffered telemetry batches arrive from edge agents (store-and-forward):
1. **Timestamp Inspection:** If `DATA_MODE="live"` and `(now - sample_time) > LIVE_TTL_SECONDS`, the batch is classified as historical backfill.
2. **Storage Route:** Backfilled samples are inserted into the persistent SQLite database and time-series store for historical SLA auditing.
3. **Diagnostic Protection:** Backfilled samples **never** update `received_at` timestamps, never revive stale/no_data freshness status, and never trigger new open incident alerts.

### 9.3 Hop-by-Hop Path Probe Derivation & Topological Subtraction

Rather than requiring telemetry instrumentation on every cable segment, edge monitoring agents probe node addresses in parallel from a designated vantage point (default `GW1`).

HopTrace derives directional link health via BFS tree traversal from the vantage point:

| Reached Node | Inbound Link | Health Inference Rule |
|---|---|---|
| Reachable ($P \to X$) | Link $P \to X$ | Link is UP; latency = $\Delta(\text{lat}_X - \text{lat}_P)$, loss = $\max(0, \text{loss}_X - \text{loss}_P)$ |
| Unreachable ($X$) | Link $P \to X$ | First failed hop! Blamed for outage ($100\%$ loss, connectivity down) |
| Descendants of $X$ | Subtree ($X \to \dots$) | Tagged `behind_failure`; suppressed from false alarm generation |

#### 14-Link Topology Inbound Mapping

| Node | Inbound Link | Source Node | Village Segment |
|---|---|---|---|
| `R1` | `L1` | `GW1` | PoP Core Backhaul |
| `WB1` | `L2` | `R1` | Rampur Wireless Backhaul |
| `WB2` | `L3` | `WB1` | Rampur PtP Link |
| `AP1` | `L4` | `WB2` | Rampur Access Point 1 |
| `AP2` | `L5` | `R1` | Rampur Access Point 2 |
| `WB3` | `L6` | `R1` | Bhatpur Wireless Backhaul |
| `WB4` | `L7` | `WB3` | Bhatpur PtP Link |
| `R2` | `L8` | `WB4` | Bhatpur Sub-Router |
| `AP3` | `L9` | `R2` | Bhatpur Access Point 3 |
| `AP4` | `L10` | `R2` | Bhatpur Access Point 4 |
| `WB5` | `L11` | `R1` | Daulatpur Wireless Backhaul |
| `WB6` | `L12` | `WB5` | Daulatpur PtP Link |
| `AP5` | `L13` | `WB6` | Daulatpur Access Point 5 |
| `AP6` | `L14` | `WB6` | Daulatpur Access Point 6 |

### 9.4 Adaptive EWMA Dynamic Baselines

To adapt to seasonal, diurnal, and atmospheric variations (common in rural wireless deployments) without triggering false positives or suffering anomaly poisoning:

1. **EWMA Formulation:**
   $$\text{Baseline}_{\text{new}} = (1 - \alpha) \cdot \text{Baseline}_{\text{old}} + \alpha \cdot \text{Observed} \quad (\alpha = 0.30)$$
2. **Warm-up Gate:** Static engineering defaults are used until $\ge 60$ healthy samples are observed for a link.
3. **Health Validation:** Updates are strictly gated to healthy samples (`connectivity_ok = True`, `packet_loss < 5.0%`, `anomaly_score < 0.10`).
4. **Drift Clamp:** Learned values are clamped within $\pm 50\%$ of static documented defaults to prevent drift extremes.
