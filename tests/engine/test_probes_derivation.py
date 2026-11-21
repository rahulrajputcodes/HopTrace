"""Unit tests for hop-by-hop path probe derivation and tree semantics."""

import pytest
from app.engine.models import HopResult, Measurement
from app.engine.probes import derive_link_measurements
from app.engine.topology import get_default_topology


def test_single_mid_tree_node_down_blames_only_first_failure():
    """When a mid-tree node (WB3) fails, only its inbound link is blamed.
    Descendants (WB4, R2, AP3, AP4) are behind_failure and NEVER blamed.
    """
    topo = get_default_topology()

    # WB3 is unreachable (loss 100%, reachable False)
    # Ancestors (GW1, R1) are reachable
    # Descendants report unreachable or no response
    results = [
        {"node_id": "GW1", "reachable": True, "latency_ms": 0.0, "packet_loss_pct": 0.0},
        {"node_id": "R1", "reachable": True, "latency_ms": 15.0, "packet_loss_pct": 0.0},
        {"node_id": "WB1", "reachable": True, "latency_ms": 17.0, "packet_loss_pct": 0.0},
        {"node_id": "WB2", "reachable": True, "latency_ms": 42.0, "packet_loss_pct": 0.5},
        {"node_id": "AP1", "reachable": True, "latency_ms": 45.0, "packet_loss_pct": 0.5},
        {"node_id": "AP2", "reachable": True, "latency_ms": 20.0, "packet_loss_pct": 0.0},
        # FAILING NODE: WB3
        {"node_id": "WB3", "reachable": False, "latency_ms": None, "packet_loss_pct": 100.0},
        # Downstream nodes behind WB3
        {"node_id": "WB4", "reachable": False, "latency_ms": None, "packet_loss_pct": 100.0},
        {"node_id": "R2", "reachable": False, "latency_ms": None, "packet_loss_pct": 100.0},
        {"node_id": "AP3", "reachable": False, "latency_ms": None, "packet_loss_pct": 100.0},
        {"node_id": "AP4", "reachable": False, "latency_ms": None, "packet_loss_pct": 100.0},
        # Independent Daulatpur branch is fine
        {"node_id": "WB5", "reachable": True, "latency_ms": 17.0, "packet_loss_pct": 0.0},
        {"node_id": "WB6", "reachable": True, "latency_ms": 47.0, "packet_loss_pct": 0.8},
        {"node_id": "AP5", "reachable": True, "latency_ms": 50.0, "packet_loss_pct": 0.8},
        {"node_id": "AP6", "reachable": True, "latency_ms": 50.0, "packet_loss_pct": 0.8},
    ]

    measurements, hop_trace = derive_link_measurements(results, topo, vantage_node_id="GW1")

    hop_map = {h.node_id: h for h in hop_trace}

    # WB3 is the first failure boundary
    assert hop_map["WB3"].status == "failed"
    assert hop_map["WB3"].link_id == "L6"  # Inbound link of WB3 is R1 -> WB3 (L6)

    # Descendants must be behind_failure
    for desc_id in ["WB4", "R2", "AP3", "AP4"]:
        assert hop_map[desc_id].status == "behind_failure"

    # Only L6 should be reported down among the Bhatpur branch links
    down_links = [m for m in measurements if not m.connectivity_ok]
    assert len(down_links) == 1
    assert down_links[0].component_id == "L6"
    assert down_links[0].packet_loss_pct == 100.0

    # No measurements should be emitted for links behind WB3 (L7, L8, L9, L10)
    emitted_link_ids = {m.component_id for m in measurements}
    for behind_link in ["L7", "L8", "L9", "L10"]:
        assert behind_link not in emitted_link_ids


def test_root_link_down():
    """When R1 fails, only L1 is blamed. All other nodes become behind_failure."""
    topo = get_default_topology()

    results = [
        {"node_id": "GW1", "reachable": True, "latency_ms": 0.0, "packet_loss_pct": 0.0},
        {"node_id": "R1", "reachable": False, "latency_ms": None, "packet_loss_pct": 100.0},
        {"node_id": "WB1", "reachable": False, "latency_ms": None, "packet_loss_pct": 100.0},
        {"node_id": "WB3", "reachable": False, "latency_ms": None, "packet_loss_pct": 100.0},
        {"node_id": "WB5", "reachable": False, "latency_ms": None, "packet_loss_pct": 100.0},
    ]

    measurements, hop_trace = derive_link_measurements(results, topo, vantage_node_id="GW1")
    hop_map = {h.node_id: h for h in hop_trace}

    assert hop_map["R1"].status == "failed"
    assert hop_map["WB1"].status == "behind_failure"
    assert hop_map["WB3"].status == "behind_failure"
    assert hop_map["WB5"].status == "behind_failure"

    down_links = [m for m in measurements if not m.connectivity_ok]
    assert len(down_links) == 1
    assert down_links[0].component_id == "L1"


def test_hop_by_hop_subtraction_and_degraded_status():
    """Checks latency delta subtraction and degraded status assignment for slow hops."""
    topo = get_default_topology()

    # R1 latency = 15.0ms
    # WB1 latency = 150.0ms (huge spike on L2: 150 - 15 = 135ms delta, baseline is 2ms)
    results = [
        {"node_id": "GW1", "reachable": True, "latency_ms": 0.0, "packet_loss_pct": 0.0},
        {"node_id": "R1", "reachable": True, "latency_ms": 15.0, "packet_loss_pct": 0.0},
        {"node_id": "WB1", "reachable": True, "latency_ms": 150.0, "packet_loss_pct": 0.0},
    ]

    measurements, hop_trace = derive_link_measurements(results, topo, vantage_node_id="GW1")
    hop_map = {h.node_id: h for h in hop_trace}

    # L2 latency should be 150.0 - 15.0 = 135.0 ms
    l2_meas = next((m for m in measurements if m.component_id == "L2"), None)
    assert l2_meas is not None
    assert l2_meas.latency_ms == 135.0

    # WB1 hop status should be degraded due to anomaly threshold crossing
    assert hop_map["WB1"].status == "degraded"
    assert hop_map["R1"].status == "ok"


def test_missing_node_result_marked_no_data():
    """A node omitted from probe results is marked status='no_data'."""
    topo = get_default_topology()

    results = [
        {"node_id": "GW1", "reachable": True, "latency_ms": 0.0, "packet_loss_pct": 0.0},
        {"node_id": "R1", "reachable": True, "latency_ms": 15.0, "packet_loss_pct": 0.0},
        # WB1 is omitted
    ]

    measurements, hop_trace = derive_link_measurements(results, topo, vantage_node_id="GW1")
    hop_map = {h.node_id: h for h in hop_trace}

    assert hop_map["WB1"].status == "no_data"
    # No link measurement emitted for L2
    assert not any(m.component_id == "L2" for m in measurements)
