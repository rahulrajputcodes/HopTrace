"""Tests for topology-derived branch computation and cascade fault detection."""

import pytest
from app.engine.diagnostics import DiagnosticEngine, derive_topology_branches, diagnose
from app.engine.models import (
    Measurement,
    NetworkTopology,
    TopologyLink,
    TopologyNode,
)
from app.engine.telemetry import SimulatedTelemetryGenerator
from app.engine.topology import get_default_topology


def test_derive_topology_branches_default():
    """Confirms branches derived from the default 14-link topology."""
    topology = get_default_topology()
    branches = derive_topology_branches(topology)

    # 4 distinct interior branches downstream of R1 (child of gateway link L1)
    assert len(branches) == 4

    branch_sets = [set(b) for b in branches]
    assert {"L2", "L3", "L4"} in branch_sets
    assert {"L5"} in branch_sets
    assert {"L6", "L7", "L8", "L9", "L10"} in branch_sets
    assert {"L11", "L12", "L13", "L14"} in branch_sets


def test_fallback_branches_when_no_topology():
    """Confirms fallback to hardcoded branches when topology is None."""
    engine = DiagnosticEngine()

    # Degrade L3 (Rampur) and L7 (Bhatpur) without topology -> fallback branches used
    meas = [
        Measurement(component_id="L3", latency_ms=120.0, packet_loss_pct=15.0),
        Measurement(component_id="L7", latency_ms=95.0, packet_loss_pct=12.0),
    ]
    incident = engine.diagnose(measurements=meas, topology=None)
    assert incident.summary.startswith("[cascade]")

    # Degrade L3 and L4 (both Rampur WB path) without topology -> not a cascade
    meas_same_branch = [
        Measurement(component_id="L3", latency_ms=120.0, packet_loss_pct=15.0),
        Measurement(component_id="L4", latency_ms=90.0, packet_loss_pct=10.0),
    ]
    incident_same = engine.diagnose(measurements=meas_same_branch, topology=None)
    assert not incident_same.summary.startswith("[cascade]")


def test_default_topology_existing_behaviour_unchanged():
    """Confirms cascade detection behaviour is preserved on the default topology."""
    topology = get_default_topology()
    gen = SimulatedTelemetryGenerator()

    # 1. Multi-branch cascade degradation (L3 in Rampur, L7 in Bhatpur)
    meas_cascade = gen.generate_measurements(scenario="cascade_fault", severity="high")
    inc_cascade = diagnose(measurements=meas_cascade, topology=topology)
    assert inc_cascade.summary.startswith("[cascade]")
    assert inc_cascade.status == "open"

    # 2. Single-branch isolated degradation (L3 in Rampur WB path)
    meas_isolated = gen.generate_measurements(scenario="degrade_link", target_link_id="L3", severity="high")
    inc_isolated = diagnose(measurements=meas_isolated, topology=topology)
    assert inc_isolated.summary.startswith("[isolated]")
    assert inc_isolated.suspected_component_id == "L3"
    assert inc_isolated.status == "open"

    # 3. Same-branch degradation (L3 and L4 simultaneously degraded without L7)
    meas_same_branch = gen.generate_measurements(scenario="baseline")
    # Mutate L3 and L4 in the same branch
    for m in meas_same_branch:
        if m.component_id == "L3":
            m.latency_ms = 130.0
            m.packet_loss_pct = 18.0
        elif m.component_id == "L4":
            m.latency_ms = 85.0
            m.packet_loss_pct = 10.0
    inc_same_branch = diagnose(measurements=meas_same_branch, topology=topology)
    assert not inc_same_branch.summary.startswith("[cascade]")
    assert inc_same_branch.suspected_component_id == "L3"

    # 4. Healthy baseline
    meas_baseline = gen.generate_measurements(scenario="baseline")
    inc_baseline = diagnose(measurements=meas_baseline, topology=topology)
    assert inc_baseline.status == "closed"


def test_custom_topology_cascade_detection():
    """Builds a small custom topology with arbitrary link IDs and verifies branch derivation and cascade."""
    # Custom topology structure:
    # GW_NODE -> R_CORE (via LINK_BACKHAUL)
    # R_CORE -> N_WEST_1 (via LINK_W1) -> N_WEST_2 (via LINK_W2)
    # R_CORE -> N_EAST_1 (via LINK_E1) -> N_EAST_2 (via LINK_E2)
    nodes = [
        TopologyNode(id="GW_NODE", type="gateway", label="Custom Gateway"),
        TopologyNode(id="R_CORE", type="router", label="Custom Core Router"),
        TopologyNode(id="N_WEST_1", type="wireless_bridge", label="West Bridge 1"),
        TopologyNode(id="N_WEST_2", type="access_point", label="West AP"),
        TopologyNode(id="N_EAST_1", type="wireless_bridge", label="East Bridge 1"),
        TopologyNode(id="N_EAST_2", type="access_point", label="East AP"),
    ]
    links = [
        TopologyLink(id="LINK_BACKHAUL", source="GW_NODE", target="R_CORE"),
        TopologyLink(id="LINK_W1", source="R_CORE", target="N_WEST_1"),
        TopologyLink(id="LINK_W2", source="N_WEST_1", target="N_WEST_2"),
        TopologyLink(id="LINK_E1", source="R_CORE", target="N_EAST_1"),
        TopologyLink(id="LINK_E2", source="N_EAST_1", target="N_EAST_2"),
    ]
    custom_topo = NetworkTopology(nodes=nodes, links=links)

    branches = derive_topology_branches(custom_topo)
    assert len(branches) == 2
    branch_sets = [set(b) for b in branches]
    assert {"LINK_W1", "LINK_W2"} in branch_sets
    assert {"LINK_E1", "LINK_E2"} in branch_sets

    custom_baselines = {
        "LINK_BACKHAUL": {"latency_ms": 10.0, "packet_loss_pct": 0.0, "throughput_mbps": 100.0, "connectivity_ok": True},
        "LINK_W1": {"latency_ms": 15.0, "packet_loss_pct": 0.0, "throughput_mbps": 50.0, "connectivity_ok": True},
        "LINK_W2": {"latency_ms": 15.0, "packet_loss_pct": 0.0, "throughput_mbps": 50.0, "connectivity_ok": True},
        "LINK_E1": {"latency_ms": 15.0, "packet_loss_pct": 0.0, "throughput_mbps": 50.0, "connectivity_ok": True},
        "LINK_E2": {"latency_ms": 15.0, "packet_loss_pct": 0.0, "throughput_mbps": 50.0, "connectivity_ok": True},
    }

    engine = DiagnosticEngine(baselines=custom_baselines)

    # 1. Degrade across independent branches (LINK_W2 and LINK_E2) -> Cascade
    meas_cascade = [
        Measurement(component_id="LINK_BACKHAUL", latency_ms=10.0, packet_loss_pct=0.0),
        Measurement(component_id="LINK_W1", latency_ms=15.0, packet_loss_pct=0.0),
        Measurement(component_id="LINK_W2", latency_ms=140.0, packet_loss_pct=20.0),
        Measurement(component_id="LINK_E1", latency_ms=15.0, packet_loss_pct=0.0),
        Measurement(component_id="LINK_E2", latency_ms=130.0, packet_loss_pct=18.0),
    ]
    inc_cascade = engine.diagnose(measurements=meas_cascade, topology=custom_topo)
    assert inc_cascade.summary.startswith("[cascade]")
    assert inc_cascade.status == "open"

    # 2. Degrade within same branch (LINK_W1 and LINK_W2) -> NOT Cascade
    meas_same = [
        Measurement(component_id="LINK_BACKHAUL", latency_ms=10.0, packet_loss_pct=0.0),
        Measurement(component_id="LINK_W1", latency_ms=140.0, packet_loss_pct=20.0),
        Measurement(component_id="LINK_W2", latency_ms=90.0, packet_loss_pct=10.0),
        Measurement(component_id="LINK_E1", latency_ms=15.0, packet_loss_pct=0.0),
        Measurement(component_id="LINK_E2", latency_ms=15.0, packet_loss_pct=0.0),
    ]
    inc_same = engine.diagnose(measurements=meas_same, topology=custom_topo)
    assert not inc_same.summary.startswith("[cascade]")
    assert inc_same.suspected_component_id == "LINK_W1"
