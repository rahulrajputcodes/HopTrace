"""Unit tests for deterministic root cause classifier (engine/cause.py).

Adheres to HopTrace Part 1 Contract §3 and TRACK_B_api_frontend.md §B4.
"""

import pytest
from app.engine.cause import classify_cause
from app.engine.models import CauseResult


@pytest.fixture
def sample_topology():
    return {
        "nodes": [
            {"id": "GW1", "type": "gateway", "village": "block_hq", "properties": {"village": "block_hq"}},
            {"id": "R1", "type": "router", "village": "rampur", "properties": {"village": "rampur"}},
            {"id": "WB1", "type": "wireless_bridge", "village": "rampur", "properties": {"village": "rampur"}},
            {"id": "WB2", "type": "wireless_bridge", "village": "rampur", "properties": {"village": "rampur"}},
            {"id": "AP1", "type": "access_point", "village": "rampur", "properties": {"village": "rampur"}},
            {"id": "AP2", "type": "access_point", "village": "rampur", "properties": {"village": "rampur"}},
            {"id": "WB3", "type": "wireless_bridge", "village": "bhatpur", "properties": {"village": "bhatpur"}},
            {"id": "WB4", "type": "wireless_bridge", "village": "bhatpur", "properties": {"village": "bhatpur"}},
        ],
        "links": [
            {"id": "L1", "source": "GW1", "target": "R1", "medium": "fiber", "properties": {"medium": "fiber"}},
            {"id": "L2", "source": "R1", "target": "WB1", "medium": "ethernet", "properties": {"medium": "ethernet"}},
            {"id": "L3", "source": "WB1", "target": "WB2", "medium": "wireless_ptp", "properties": {"medium": "wireless_ptp"}},
            {"id": "L4", "source": "WB2", "target": "AP1", "medium": "ethernet", "properties": {"medium": "ethernet"}},
            {"id": "L5", "source": "R1", "target": "AP2", "medium": "ethernet", "properties": {"medium": "ethernet"}},
            {"id": "L6", "source": "R1", "target": "WB3", "medium": "ethernet", "properties": {"medium": "ethernet"}},
            {"id": "L7", "source": "WB3", "target": "WB4", "medium": "wireless_60ghz", "properties": {"medium": "wireless_60ghz"}},
        ],
    }


def _make_nominal_history(n=10):
    return [
        {
            "tick": i,
            "latency_ms": 15.0,
            "packet_loss_pct": 0.0,
            "connectivity_ok": True,
            "risk_score": 5.0,
        }
        for i in range(n)
    ]


# ── Case 1: Fiber cut ─────────────────────────────────────────────────────────

def test_fiber_cut_abrupt(sample_topology):
    """Case 1: Fiber link hard-down (connectivity_ok False, loss >= 98%), abrupt -> fiber_cut."""
    measurements = [
        {"component_id": "L1", "packet_loss_pct": 100.0, "latency_ms": None, "connectivity_ok": False},
        {"component_id": "L2", "packet_loss_pct": 0.0, "latency_ms": 2.0, "connectivity_ok": True},
    ]
    history = _make_nominal_history(8)
    history.append({"tick": 9, "packet_loss_pct": 100.0, "connectivity_ok": False, "latency_ms": 0.0})

    result = classify_cause(
        measurements=measurements,
        topology=sample_topology,
        suspected_component_id="L1",
        link_history=history,
    )

    assert isinstance(result, CauseResult)
    assert result.cause == "fiber_cut"
    assert result.confidence <= 0.80
    assert result.confidence >= 0.70
    assert any("fiber" in r.lower() for r in result.reasoning)


# ── Case 2: RF degradation ───────────────────────────────────────────────────

def test_rf_degradation_gradual(sample_topology):
    """Case 2: Wireless link, loss/latency rising over history, still connected -> rf_degradation."""
    measurements = [
        {"component_id": "L3", "packet_loss_pct": 35.0, "latency_ms": 120.0, "connectivity_ok": True},
    ]
    # Gradual rise across 7 samples
    history = [
        {"tick": 1, "packet_loss_pct": 1.0, "latency_ms": 25.0, "connectivity_ok": True},
        {"tick": 2, "packet_loss_pct": 3.0, "latency_ms": 32.0, "connectivity_ok": True},
        {"tick": 3, "packet_loss_pct": 8.0, "latency_ms": 48.0, "connectivity_ok": True},
        {"tick": 4, "packet_loss_pct": 14.0, "latency_ms": 65.0, "connectivity_ok": True},
        {"tick": 5, "packet_loss_pct": 22.0, "latency_ms": 88.0, "connectivity_ok": True},
        {"tick": 6, "packet_loss_pct": 28.0, "latency_ms": 105.0, "connectivity_ok": True},
        {"tick": 7, "packet_loss_pct": 35.0, "latency_ms": 120.0, "connectivity_ok": True},
    ]

    result = classify_cause(
        measurements=measurements,
        topology=sample_topology,
        suspected_component_id="L3",
        link_history=history,
    )

    assert result.cause == "rf_degradation"
    assert result.confidence <= 0.75
    assert result.confidence >= 0.60
    assert any("gradual" in r.lower() or "rf" in r.lower() for r in result.reasoning)


# ── Case 3: Power outage ──────────────────────────────────────────────────────

def test_power_outage_colocated_failure(sample_topology):
    """Case 3: Wireless/node hard-down abruptly + independent co-located failure -> power_outage."""
    # Suspected is L3 in village Rampur (WB1->WB2). AP2 / L5 is also in Rampur but NOT downstream of L3.
    measurements = [
        {"component_id": "L3", "packet_loss_pct": 100.0, "connectivity_ok": False},
        {"component_id": "L5", "packet_loss_pct": 100.0, "connectivity_ok": False},  # Independent co-located in Rampur
        {"component_id": "L7", "packet_loss_pct": 0.0, "connectivity_ok": True},     # Bhatpur is fine
    ]
    history = _make_nominal_history(8)
    history.append({"tick": 9, "packet_loss_pct": 100.0, "connectivity_ok": False})

    result = classify_cause(
        measurements=measurements,
        topology=sample_topology,
        suspected_component_id="L3",
        link_history=history,
    )

    assert result.cause == "power_outage"
    assert result.confidence <= 0.60
    assert any("verify power/ups on site" in r.lower() for r in result.reasoning)


# ── Case 4: Wireless abrupt unknown ──────────────────────────────────────────

def test_wireless_abrupt_unknown_cause(sample_topology):
    """Case 4: Wireless hard-down abruptly, no co-located independent failure -> unknown."""
    # L3 is down, but L5 (also in Rampur) is healthy!
    measurements = [
        {"component_id": "L3", "packet_loss_pct": 100.0, "connectivity_ok": False},
        {"component_id": "L5", "packet_loss_pct": 0.0, "connectivity_ok": True},
    ]
    history = _make_nominal_history(8)
    history.append({"tick": 9, "packet_loss_pct": 100.0, "connectivity_ok": False})

    result = classify_cause(
        measurements=measurements,
        topology=sample_topology,
        suspected_component_id="L3",
        link_history=history,
    )

    assert result.cause == "unknown"
    assert result.confidence <= 0.40
    assert any("abrupt loss; cannot tell power from radio failure remotely" in r.lower() for r in result.reasoning)


# ── Case 5: Upstream failure ──────────────────────────────────────────────────

def test_upstream_failure_interior_blackout(sample_topology):
    """Case 5: All interior links report >= 98% loss -> upstream_failure."""
    measurements = [
        {"component_id": "L1", "packet_loss_pct": 100.0, "connectivity_ok": False},
        {"component_id": "L2", "packet_loss_pct": 100.0, "connectivity_ok": False},
        {"component_id": "L3", "packet_loss_pct": 99.0, "connectivity_ok": False},
        {"component_id": "L5", "packet_loss_pct": 100.0, "connectivity_ok": False},
    ]

    result = classify_cause(
        measurements=measurements,
        topology=sample_topology,
        suspected_component_id="L1",
        link_history=_make_nominal_history(8),
    )

    assert result.cause == "upstream_failure"
    assert result.confidence <= 0.85
    assert result.confidence >= 0.80
    assert any("upstream" in r.lower() for r in result.reasoning)


# ── Case 6: Healthy or Missing Component ─────────────────────────────────────

def test_healthy_or_missing_component(sample_topology):
    """Case 6: No suspected component or healthy or missing history -> unknown with 0.0 confidence."""
    # No suspected component
    res_none = classify_cause(
        measurements=[],
        topology=sample_topology,
        suspected_component_id=None,
    )
    assert res_none.cause == "unknown"
    assert res_none.confidence == 0.0

    # Healthy component
    res_healthy = classify_cause(
        measurements=[{"component_id": "L1", "packet_loss_pct": 0.0, "connectivity_ok": True, "latency_ms": 12.0}],
        topology=sample_topology,
        suspected_component_id="L1",
        link_history=_make_nominal_history(8),
    )
    assert res_healthy.cause == "unknown"
    assert res_healthy.confidence == 0.0

    # Missing history
    res_no_hist = classify_cause(
        measurements=[{"component_id": "L3", "packet_loss_pct": 100.0, "connectivity_ok": False}],
        topology=sample_topology,
        suspected_component_id="L3",
        link_history=None,
    )
    assert res_no_hist.cause == "unknown"
    assert res_no_hist.confidence == 0.0
    assert any("history" in r.lower() for r in res_no_hist.reasoning)


# ── Case 7: Garbage Inputs Safety ─────────────────────────────────────────────

def test_garbage_inputs_safety():
    """Verify classify_cause never raises on arbitrary broken / corrupt inputs."""
    garbage_cases = [
        (None, None, None, None),
        ([], {}, "", []),
        ([{"broken": 123}], "not_a_topology", 42, [{"bad": None}]),
        ("string_measurements", None, "L999", "string_history"),
        ([None, None], None, None, [None, None]),
        ([{"component_id": None}], None, "L1", [{"tick": "bad"}]),
    ]

    for m, t, s, h in garbage_cases:
        res = classify_cause(measurements=m, topology=t, suspected_component_id=s, link_history=h)
        assert isinstance(res, CauseResult)
        assert res.cause == "unknown"
        assert res.confidence <= 0.85
        assert isinstance(res.reasoning, list)
