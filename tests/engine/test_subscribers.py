"""Automated tests for downstream subscriber impact analysis."""

import pytest
from backend.app.engine import (
    InMemoryTopologyGraph,
    get_affected_subscribers,
    get_incident_details,
    run_scenario,
)


def test_subscribers_impact_wireless_bridge_link_l3():
    """Validates that degradation of L3 (wireless bridge) affects ONLY AP1 subscribers.

    Expected in v2:
    Only AP1 subscribers (SUB101, SUB102, SUB103) are downstream of L3.
    """
    graph = InMemoryTopologyGraph()
    affected = graph.get_affected_subscribers(suspected_component_id="L3", component_type="link")

    affected_ids = {s.id for s in affected}
    assert affected_ids == {"SUB101", "SUB102", "SUB103"}
    assert len(affected) == 3
    for s in affected:
        assert s.access_point_id == "AP1"


def test_subscribers_impact_core_backhaul_link_l1():
    """Validates that degradation of L1 (core backhaul) affects ALL 20 subscribers."""
    graph = InMemoryTopologyGraph()
    affected = graph.get_affected_subscribers(suspected_component_id="L1", component_type="link")

    affected_ids = {s.id for s in affected}
    assert len(affected) == 20
    assert len(affected_ids) == 20
    assert {"SUB101", "SUB102", "SUB103", "SUB201", "SUB202", "SUB203", "SUB204"}.issubset(affected_ids)


def test_subscribers_impact_south_distribution_link_l5():
    """Validates that degradation of L5 affects ONLY AP2 subscribers (SUB201-SUB204)."""
    graph = InMemoryTopologyGraph()
    affected = graph.get_affected_subscribers(suspected_component_id="L5", component_type="link")

    affected_ids = {s.id for s in affected}
    assert affected_ids == {"SUB201", "SUB202", "SUB203", "SUB204"}
    assert len(affected) == 4
    for s in affected:
        assert s.access_point_id == "AP2"


def test_subscribers_impact_access_point_node():
    """Validates direct node impact on access point AP1."""
    graph = InMemoryTopologyGraph()
    affected = graph.get_affected_subscribers(suspected_component_id="AP1", component_type="node")

    affected_ids = {s.id for s in affected}
    assert affected_ids == {"SUB101", "SUB102", "SUB103"}
    assert len(affected) == 3


def test_affected_subscribers_facade_end_to_end():
    """Validates full pipeline: scenario -> diagnosis -> affected subscribers response."""
    # Run degradation on L3
    res = run_scenario(
        scenario="degrade_link",
        target_link_id="L3",
        severity="medium",
        force_in_memory=True,
    )
    assert res.incident_id is not None

    # Retrieve affected subscribers via incident ID
    subs_resp = get_affected_subscribers(res.incident_id, force_in_memory=True)

    # API contract requirement: count must equal length of subscribers list
    assert subs_resp.count == len(subs_resp.subscribers)
    assert subs_resp.count == 3
    sub_ids = {s.id for s in subs_resp.subscribers}
    assert sub_ids == {"SUB101", "SUB102", "SUB103"}
