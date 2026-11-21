"""Automated tests for the upstream_failure scenario.

Verifies:
1. Upstream failure telemetry generation (correct measurements).
2. Diagnostic engine infers upstream fault from observations alone.
3. The diagnostic function signature rejects ground-truth inputs.
4. Affected subscriber count for an upstream failure (all 5 subscribers).
5. Ambiguous upstream vs. intermediate failure is handled with uncertainty.
6. Baseline scenario still produces no false upstream alarms.
"""

from __future__ import annotations

import inspect
import pytest
from backend.app.engine import (
    GATEWAY_LINK_ID,
    INTERIOR_LINK_IDS,
    DiagnosticEngine,
    InMemoryTopologyGraph,
    Measurement,
    SimulatedTelemetryGenerator,
    diagnose,
    get_affected_subscribers,
    get_default_topology,
    get_incident_details,
    run_scenario,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_upstream_failure_measurements(timestamp: str = "2026-10-31T00:00:00+00:00"):
    """Returns a canonical upstream_failure measurement list."""
    generator = SimulatedTelemetryGenerator()
    return generator.generate_measurements(
        scenario="upstream_failure",
        timestamp=timestamp,
    )


# ---------------------------------------------------------------------------
# A. Telemetry correctness
# ---------------------------------------------------------------------------

def test_upstream_failure_telemetry_gateway_link_down():
    """L1 (gateway link) must be down in an upstream failure."""
    measurements = make_upstream_failure_measurements()
    meas_map = {m.component_id: m for m in measurements}

    gw = meas_map[GATEWAY_LINK_ID]
    assert gw.connectivity_ok is False
    assert gw.packet_loss_pct == 100.0
    assert gw.throughput_mbps == 0.0
    assert gw.latency_ms is None
    assert gw.data_source == "simulated"


def test_upstream_failure_telemetry_interior_links_locally_up():
    """Interior links must stay locally link-present (connectivity_ok=True)
    but report zero throughput and 100% packet loss — they have no internet traffic."""
    measurements = make_upstream_failure_measurements()
    meas_map = {m.component_id: m for m in measurements}

    for lid in INTERIOR_LINK_IDS:
        m = meas_map[lid]
        assert m.connectivity_ok is True, f"{lid} should be locally link-present"
        assert m.packet_loss_pct == 100.0, f"{lid} should have 100% packet loss"
        assert m.throughput_mbps == 0.0, f"{lid} should have zero throughput"
        assert m.latency_ms is None, f"{lid} latency should be null (internet unreachable)"
        assert m.data_source == "simulated"


def test_upstream_failure_telemetry_deterministic():
    """Same inputs must produce identical outputs (deterministic)."""
    ts = "2026-10-31T00:00:00+00:00"
    gen = SimulatedTelemetryGenerator()
    m1 = gen.generate_measurements(scenario="upstream_failure", timestamp=ts)
    m2 = gen.generate_measurements(scenario="upstream_failure", timestamp=ts)

    ids1 = [m.component_id for m in m1]
    ids2 = [m.component_id for m in m2]
    assert ids1 == ids2

    for a, b in zip(m1, m2):
        assert a.packet_loss_pct == b.packet_loss_pct
        assert a.throughput_mbps == b.throughput_mbps
        assert a.connectivity_ok == b.connectivity_ok


def test_upstream_failure_all_links_have_measurements():
    """Every monitored link must appear in the measurements list."""
    measurements = make_upstream_failure_measurements()
    observed_ids = {m.component_id for m in measurements}
    expected_ids = {GATEWAY_LINK_ID} | set(INTERIOR_LINK_IDS)
    assert expected_ids.issubset(observed_ids)


# ---------------------------------------------------------------------------
# B. Diagnostic engine — upstream failure identification
# ---------------------------------------------------------------------------

def test_diagnostic_identifies_upstream_failure():
    """Engine must infer L1/gateway as root cause without receiving ground truth."""
    measurements = make_upstream_failure_measurements()
    topology = get_default_topology()

    # Ground truth: GW1 is the upstream node, L1 is the gateway link.
    # The engine must NOT receive this — only measurements and topology.
    incident = diagnose(measurements=measurements, topology=topology)

    assert incident.status == "open"
    assert incident.suspected_component_id == GATEWAY_LINK_ID
    assert incident.suspected_component_type == "link"
    assert incident.diagnostic_score == 1.0
    assert incident.confidence_score is not None and incident.confidence_score >= 0.85
    assert len(incident.evidence) >= 2
    assert "upstream" in incident.summary.lower() or "gateway" in incident.summary.lower()


def test_diagnostic_upstream_evidence_content():
    """Evidence must explain the gateway-down and network-wide loss observations."""
    measurements = make_upstream_failure_measurements()
    topology = get_default_topology()
    incident = diagnose(measurements=measurements, topology=topology)

    metrics = {ev.metric for ev in incident.evidence}
    assert "connectivity_ok" in metrics
    assert "packet_loss_pct" in metrics

    conn_ev = next(ev for ev in incident.evidence if ev.metric == "connectivity_ok")
    assert conn_ev.observed_value is False
    assert conn_ev.severity == "critical"

    loss_ev = next(ev for ev in incident.evidence if ev.metric == "packet_loss_pct")
    assert loss_ev.severity == "critical"


def test_diagnostic_upstream_uncertainty_note_present():
    """A non-null uncertainty_note must explain the confidence level."""
    measurements = make_upstream_failure_measurements()
    topology = get_default_topology()
    incident = diagnose(measurements=measurements, topology=topology)

    assert incident.uncertainty_note is not None
    assert len(incident.uncertainty_note) > 10


def test_diagnostic_no_false_upstream_alarm_on_baseline():
    """Baseline scenario must NOT trigger upstream failure detection."""
    gen = SimulatedTelemetryGenerator()
    measurements = gen.generate_measurements(scenario="baseline")
    topology = get_default_topology()

    incident = diagnose(measurements=measurements, topology=topology)

    assert incident.suspected_component_id is None
    assert incident.status == "closed"


def test_diagnostic_upstream_via_engine_class():
    """DiagnosticEngine.diagnose() must produce the same upstream result."""
    measurements = make_upstream_failure_measurements()
    topology = get_default_topology()

    engine = DiagnosticEngine()
    incident = engine.diagnose(measurements=measurements, topology=topology)

    assert incident.suspected_component_id == GATEWAY_LINK_ID
    assert incident.suspected_component_type == "link"


# ---------------------------------------------------------------------------
# C. Ground-truth separation
# ---------------------------------------------------------------------------

def test_diagnostic_signature_rejects_ground_truth():
    """Verify that neither diagnose() nor DiagnosticEngine.diagnose() accept
    target_node_id, scenario, or expected_fault parameters."""
    forbidden = {
        "expected_fault",
        "target_link",
        "target_link_id",
        "target_node",
        "target_node_id",
        "fault_id",
        "scenario",
        "ground_truth",
    }

    for sig in [inspect.signature(diagnose), inspect.signature(DiagnosticEngine.diagnose)]:
        for p in forbidden:
            assert p not in sig.parameters, (
                f"Forbidden ground-truth parameter '{p}' found in diagnostic function"
            )


def test_upstream_failure_inferred_without_node_id():
    """The engine must correctly identify the upstream failure even when called
    with only measurements — no topology, no target_node_id hint."""
    measurements = make_upstream_failure_measurements()

    # No topology passed — engine uses baseline keys only
    incident = diagnose(measurements=measurements, topology=None)

    assert incident.suspected_component_id == GATEWAY_LINK_ID
    assert incident.status == "open"


# ---------------------------------------------------------------------------
# D. Affected subscriber identification
# ---------------------------------------------------------------------------

def test_upstream_failure_affects_all_subscribers():
    """Upstream failure on L1 must surface all 20 subscribers as affected."""
    graph = InMemoryTopologyGraph()
    affected = graph.get_affected_subscribers(
        suspected_component_id=GATEWAY_LINK_ID,
        component_type="link",
    )
    assert len(affected) == 20
    ids = {s.id for s in affected}
    assert len(ids) == 20
    assert {"SUB101", "SUB102", "SUB103", "SUB201", "SUB202", "SUB203", "SUB204"}.issubset(ids)


def test_upstream_failure_affected_subscribers_via_facade():
    """Full pipeline: run upstream_failure scenario -> incident -> affected subscribers."""
    res = run_scenario(
        scenario="upstream_failure",
        force_in_memory=True,
    )
    assert res.incident_id is not None
    assert res.measurements_count >= 5

    incident = get_incident_details(res.incident_id)
    assert incident is not None
    assert incident.suspected_component_id == GATEWAY_LINK_ID

    subs = get_affected_subscribers(res.incident_id, force_in_memory=True)
    assert subs.count == 20
    assert subs.count == len(subs.subscribers)
    sub_ids = {s.id for s in subs.subscribers}
    assert len(sub_ids) == 20
    assert {"SUB101", "SUB102", "SUB103", "SUB201", "SUB202", "SUB203", "SUB204"}.issubset(sub_ids)


# ---------------------------------------------------------------------------
# E. Ambiguous upstream vs. intermediate — partial loss only on L1
# ---------------------------------------------------------------------------

def test_partial_gateway_degradation_not_classified_as_upstream_failure():
    """If L1 is degraded (not fully down) and interior links are still healthy,
    the engine must NOT trigger the upstream failure pattern — it should fall
    through to per-link scoring."""
    gen = SimulatedTelemetryGenerator()
    # Degrade L1 only — interior links remain healthy
    measurements = gen.generate_measurements(
        scenario="degrade_link",
        target_link_id="L1",
        severity="high",
    )
    topology = get_default_topology()

    incident = diagnose(measurements=measurements, topology=topology)

    # Should be identified as intermediate link fault on L1, not upstream_failure pattern
    assert incident.suspected_component_id == "L1"
    # Upstream failure detection requires connectivity_ok=False on L1
    # A degraded (but still passing) link scores via the standard path
    assert incident.diagnostic_score < 1.0  # never hits the upstream sentinel score


def test_upstream_failure_without_interior_saturation_falls_to_standard_scoring():
    """If L1 is down but interior links do NOT show 100% loss (unexpected partial failure),
    the engine cannot confirm the upstream pattern and falls through to standard scoring."""
    # Craft an anomalous scenario: L1 down, but L2 still shows some healthy metrics
    measurements = [
        Measurement(
            component_id="L1",
            latency_ms=None,
            packet_loss_pct=100.0,
            throughput_mbps=0.0,
            connectivity_ok=False,
            data_source="simulated",
        ),
        Measurement(
            component_id="L2",
            latency_ms=2.0,    # healthy!
            packet_loss_pct=0.0,
            throughput_mbps=80.0,
            connectivity_ok=True,
            data_source="simulated",
        ),
        Measurement(
            component_id="L3",
            latency_ms=25.0,
            packet_loss_pct=0.5,
            throughput_mbps=35.0,
            connectivity_ok=True,
            data_source="simulated",
        ),
        Measurement(
            component_id="L4",
            latency_ms=3.0,
            packet_loss_pct=0.0,
            throughput_mbps=50.0,
            connectivity_ok=True,
            data_source="simulated",
        ),
        Measurement(
            component_id="L5",
            latency_ms=5.0,
            packet_loss_pct=0.0,
            throughput_mbps=60.0,
            connectivity_ok=True,
            data_source="simulated",
        ),
    ]
    topology = get_default_topology()
    incident = diagnose(measurements=measurements, topology=topology)

    # Should find L1 as top anomaly (connectivity_ok=False), but via standard scoring
    assert incident.suspected_component_id == "L1"
    # Standard scoring, not the sentinel upstream score
    assert incident.diagnostic_score < 1.0
