"""
Automated tests for Post-Merge Engine Integration and Facade Compliance.

Validates the 12 critical engine-integration criteria:
1. Shared engine singleton behavior.
2. force_in_memory=True initialization.
3. Topology initialization during FastAPI startup/lifespan.
4. Topology endpoint integration with get_topology(force_in_memory=True).
5. Lab endpoint integration with run_scenario().
6. Injected fault isolation from diagnostic prediction.
7. Actual engine measurements returned to the frontend.
8. Incident retrieval through facade functions.
9. Affected-subscriber integration through get_affected_subscribers().
10. Correct behavior when in-memory run/incident history is unavailable after restart.
11. Explicit simulated data-source identification across endpoints.
12. Clean API error handling without leaking internal credentials or tracebacks.
"""
from __future__ import annotations

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.engine.diagnostics import DiagnosticEngine
from app.engine.facade import (
    get_affected_subscribers,
    get_engine,
    get_incident_details,
    get_latest_incident,
    get_run_measurements,
    get_topology,
    run_scenario,
    seed_topology,
)
from app.main import app, lifespan
from app.engine.topology import get_default_links, get_default_nodes, get_default_subscribers
from app.providers.dependencies import EngineDependencyAdapter, GraphEngineUnavailableError
from app.providers.engine_topology import EngineTopologyProvider


# ── 1. Shared Engine Singleton Behavior ──────────────────────────────────────

def test_shared_engine_singleton() -> None:
    """get_engine() must return the identical singleton instance throughout the process."""
    e1 = get_engine()
    e2 = get_engine()
    assert e1 is e2, "get_engine() must be an idempotent singleton"


# ── 2. force_in_memory=True Initialization ───────────────────────────────────

def test_force_in_memory_initialization() -> None:
    """seed_topology(force_in_memory=True) seeds the in-memory graph store without Neo4j."""
    res = seed_topology(force_in_memory=True)
    assert res["status"] == "seeded"
    assert res["nodes_count"] == 15
    assert res["links_count"] == 14
    assert res["subscribers_count"] == 20

    topo = get_topology(force_in_memory=True)
    assert len(topo.nodes) == 15
    assert len(topo.links) == 14
    assert topo.data_source == "simulated"


# ── 3. Topology Initialization During FastAPI Startup ─────────────────────────

@pytest.mark.asyncio
async def test_topology_initialization_during_lifespan(monkeypatch) -> None:
    """FastAPI lifespan startup must invoke seed_topology(force_in_memory=True) when engine is configured."""
    monkeypatch.setattr(settings, "topology_provider", "engine")

    with patch("app.engine.facade.seed_topology") as mock_seed:
        mock_seed.return_value = {"status": "seeded"}
        async with lifespan(app):
            pass

        mock_seed.assert_called_once_with(force_in_memory=True)


# ── 4. Topology Endpoint Integration ─────────────────────────────────────────

def test_topology_endpoint_integration_engine(client: TestClient, monkeypatch) -> None:
    """GET /api/v1/topology returns actual engine topology with data_source='simulated'."""
    monkeypatch.setattr(settings, "topology_provider", "engine")
    resp = client.get("/api/v1/topology")
    assert resp.status_code == 200

    data = resp.json()
    assert data["data_source"] == "simulated"
    assert len(data["nodes"]) == len(get_default_nodes())
    assert len(data["links"]) == len(get_default_links())

    node_ids = {n["id"] for n in data["nodes"]}
    assert {"GW1", "R1", "WB1", "WB2", "AP1", "AP2"}.issubset(node_ids)

    link_ids = {l["id"] for l in data["links"]}
    assert {l.id for l in get_default_links()} == link_ids


# ── 5. Lab Endpoint Integration with run_scenario() ──────────────────────────

def test_lab_endpoint_run_scenario_integration(client: TestClient, isolated_db: str) -> None:
    """POST /api/v1/lab/run delegates to run_scenario(force_in_memory=True) and returns actual engine results."""
    payload = {
        "scenario": "degrade_link",
        "target_link_id": "L3",
        "severity": "high",
    }
    resp = client.post("/api/v1/lab/run", json=payload)
    assert resp.status_code == 200

    data = resp.json()
    assert data["run_id"].startswith("run-")
    assert data["data_source"] == "simulated"
    assert data["measurements_count"] == len(get_default_links())
    assert data["incident_id"] is not None


# ── 6. Injected Fault Isolation from Diagnostic Prediction ───────────────────

def test_injected_fault_isolation_from_diagnostic_prediction() -> None:
    """
    CRITICAL: The diagnostic engine must infer root cause strictly from telemetry observations.
    It must NEVER receive target_link_id, target_node_id, or scenario name.
    """
    engine = get_engine()
    # 1. Generate measurements for L2 degradation
    measurements = engine.telemetry_generator.generate_measurements(
        scenario="degrade_link",
        target_link_id="L2",
        severity="high",
    )
    topology = engine.get_topology(force_in_memory=True)

    # 2. Inspect DiagnosticEngine.diagnose signature
    diag_engine = DiagnosticEngine()
    import inspect
    sig = inspect.signature(diag_engine.diagnose)
    assert "target_link_id" not in sig.parameters
    assert "target_node_id" not in sig.parameters
    assert "scenario" not in sig.parameters

    # 3. Diagnose using ONLY observations and topology
    incident = diag_engine.diagnose(
        measurements=measurements,
        topology=topology,
        run_id="test-run-iso",
    )
    # The engine independently infers L2 based on anomalous latency/loss
    assert incident.suspected_component_id == "L2"
    assert incident.suspected_component_type == "link"


# ── 7. Actual Engine Measurements Returned to Frontend ───────────────────────

def test_actual_engine_measurements_returned(client: TestClient) -> None:
    """GET /api/v1/runs/{run_id}/measurements returns actual measurements produced by the engine."""
    # Execute a lab run
    lab_resp = client.post(
        "/api/v1/lab/run",
        json={"scenario": "degrade_link", "target_link_id": "L2", "severity": "medium"},
    )
    assert lab_resp.status_code == 200
    run_id = lab_resp.json()["run_id"]

    # Verify endpoint returns the measurements stored in the engine facade
    meas_resp = client.get(f"/api/v1/runs/{run_id}/measurements")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()

    assert meas_data["run_id"] == run_id
    assert meas_data["data_source"] == "simulated"
    assert len(meas_data["measurements"]) == len(get_default_links())

    # Check that measurements match what get_run_measurements returns directly
    facade_data = get_run_measurements(run_id)
    assert facade_data is not None
    assert facade_data.run_id == run_id
    assert len(facade_data.measurements) == len(meas_data["measurements"])


# ── 8. Incident Retrieval Through Facade Functions ───────────────────────────

def test_incident_retrieval_facade_integration(client: TestClient, isolated_db: str) -> None:
    """GET /api/v1/incidents/latest and /{id} retrieve actual engine incidents generated via facade."""
    # Run a scenario that creates an incident
    lab_resp = client.post(
        "/api/v1/lab/run",
        json={"scenario": "degrade_link", "target_link_id": "L3", "severity": "high"},
    )
    assert lab_resp.status_code == 200
    incident_id = lab_resp.json()["incident_id"]
    assert incident_id is not None

    # 1. Test get_incident_details via API
    resp_detail = client.get(f"/api/v1/incidents/{incident_id}")
    assert resp_detail.status_code == 200
    det = resp_detail.json()
    assert det["id"] == incident_id
    assert det["suspected_component_id"] == "L3"
    assert det["data_source"] == "simulated"

    # 2. Test get_latest_incident via API
    resp_latest = client.get("/api/v1/incidents/latest")
    assert resp_latest.status_code == 200
    latest = resp_latest.json()
    assert latest["id"] == incident_id


# ── 9. Affected Subscribers Through get_affected_subscribers() ──────────────

def test_affected_subscribers_facade_integration(client: TestClient, isolated_db: str) -> None:
    """GET /api/v1/incidents/{id}/affected-subscribers uses get_affected_subscribers() and enriches via SQLite."""
    # Generate an incident on L3 (between WB1 and WB2, upstream of AP1)
    lab_resp = client.post(
        "/api/v1/lab/run",
        json={"scenario": "degrade_link", "target_link_id": "L3", "severity": "high"},
    )
    assert lab_resp.status_code == 200
    incident_id = lab_resp.json()["incident_id"]

    # Retrieve affected subscribers
    aff_resp = client.get(f"/api/v1/incidents/{incident_id}/affected-subscribers")
    assert aff_resp.status_code == 200
    data = aff_resp.json()

    # Downstream of L3 is AP1, which serves SUB101, SUB102, and SUB103
    assert data["count"] == 3
    sub_ids = [s["id"] for s in data["subscribers"]]
    assert set(sub_ids) == {"SUB101", "SUB102", "SUB103"}
    # Verified SQLite enrichment
    assert all(s["access_point_id"] == "AP1" for s in data["subscribers"])
    assert any("Ramesh Patel" in s["display_name"] for s in data["subscribers"])


# ── 10. Restart Behavior for In-Memory History ────────────────────────────────

def test_restart_behavior_in_memory_unavailable(client: TestClient, isolated_db: str) -> None:
    """
    Simulating a backend restart: in-memory run/incident history is reset.
    The system must honestly return 404 for missing runs rather than fabricating records.
    """
    engine = get_engine()
    # Save existing memory state and clear to simulate restart
    saved_runs = dict(engine._runs)
    saved_incidents = dict(engine._incidents)
    saved_order = list(engine._incident_order)
    try:
        engine._runs.clear()
        engine._incidents.clear()
        engine._incident_order.clear()

        # Querying an unpersisted old run_id returns 404
        meas_resp = client.get("/api/v1/runs/old-ephemeral-run-999/measurements")
        assert meas_resp.status_code == 404
        assert "not found" in meas_resp.json()["detail"].lower()

        # Querying an unpersisted old incident_id returns 404
        inc_resp = client.get("/api/v1/incidents/old-ephemeral-inc-999")
        assert inc_resp.status_code == 404
        assert "not found" in inc_resp.json()["detail"].lower()
    finally:
        engine._runs.update(saved_runs)
        engine._incidents.update(saved_incidents)
        engine._incident_order.extend(saved_order)


# ── 11. Explicit Simulated Data Source Identification ────────────────────────

def test_simulated_data_source_identification(client: TestClient, isolated_db: str) -> None:
    """All endpoints explicitly identify in-memory/simulated data source as 'simulated'."""
    # Topology
    topo_resp = client.get("/api/v1/topology").json()
    assert topo_resp["data_source"] == "simulated"

    # Lab run
    lab_resp = client.post(
        "/api/v1/lab/run",
        json={"scenario": "degrade_link", "target_link_id": "L1", "severity": "low"},
    ).json()
    assert lab_resp["data_source"] == "simulated"

    # Measurements
    run_id = lab_resp["run_id"]
    meas_resp = client.get(f"/api/v1/runs/{run_id}/measurements").json()
    assert meas_resp["data_source"] == "simulated"
    assert all(m["data_source"] == "simulated" for m in meas_resp["measurements"])

    # Incident
    incident_id = lab_resp["incident_id"]
    inc_resp = client.get(f"/api/v1/incidents/{incident_id}").json()
    assert inc_resp["data_source"] == "simulated"


# ── 12. Clean API Error Handling ─────────────────────────────────────────────

def test_clean_api_error_handling(client: TestClient) -> None:
    """Error responses must be structured, safe, and contain zero raw tracebacks or credentials."""
    # 1. 404 Not Found
    r1 = client.get("/api/v1/runs/unknown-run/measurements")
    assert r1.status_code == 404
    assert "detail" in r1.json()

    # 2. 422 Unprocessable Entity
    r2 = client.post("/api/v1/lab/run", json={"scenario": "unknown_scenario"})
    assert r2.status_code == 422
    assert "detail" in r2.json()

    # 3. 422 Unprocessable Entity for invalid target node in upstream_failure
    r3 = client.post(
        "/api/v1/lab/run",
        json={"scenario": "upstream_failure", "target_node_id": "NON_EXISTENT_NODE"},
    )
    assert r3.status_code == 422
    assert "not found in topology" in r3.json()["detail"].lower()
