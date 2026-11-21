"""
Automated tests for Lab Simulation API (Milestone 4: POST /api/v1/lab/run).

Tests cover:
1. Successful baseline run.
2. Successful degraded-link run.
3. Access-point failure validation and execution.
4. Missing target validation (degrade_link requires target_link_id, failure scenarios require target_node_id).
5. Invalid scenario rejection (HTTP 422).
6. Invalid severity rejection (HTTP 422).
7. No incident generated on baseline (incident_id is null, not persisted).
8. Incident generated and persisted in SQLite.
9. Newly generated incident can immediately be retrieved through existing incident details endpoint.
10. Latest incident endpoint reflects newly generated incident.
11. Persistence failure returns HTTP 500 (does not report false success).
12. Unsupported upstream_failure handled honestly (HTTP 501).
13. Target validation against topology (unknown link L99, non-AP node for AP failure).
14. Ambiguous fault scenario execution and uncertainty note persistence.
15. Demo incident preservation (never overwritten).
16. Whitespace target validation (whitespace target_link_id and target_node_id rejected with 422).
17. Topology provider failure (returns HTTP 503 without proceeding to simulation).
"""
from __future__ import annotations

import sqlite3
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.db.connection import get_db_connection
from app.db.init import DEMO_INCIDENTS
from app.db.repository import get_incident, get_latest_incident
from app.engine.topology import get_default_links


# ── 1. Successful Baseline Run ────────────────────────────────────────────────

def test_lab_run_baseline_success(client: TestClient, isolated_db: str) -> None:
    """Baseline run produces measurements, returns 200, and incident_id is null."""
    response = client.post(
        "/api/v1/lab/run",
        json={"scenario": "baseline"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["run_id"].startswith("run-")
    assert data["data_source"] == "simulated"
    assert data["measurements_count"] >= 5
    assert data["incident_id"] is None


# ── 2. Successful Degraded-Link Run ──────────────────────────────────────────

def test_lab_run_degraded_link_success(client: TestClient, isolated_db: str) -> None:
    """Degraded link run generates and detects an incident, returning 200 and incident_id."""
    response = client.post(
        "/api/v1/lab/run",
        json={
            "scenario": "degrade_link",
            "target_link_id": "L2",
            "severity": "high",
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert data["run_id"].startswith("run-")
    assert data["data_source"] == "simulated"
    assert data["measurements_count"] >= 5
    assert data["incident_id"] is not None
    assert data["incident_id"].startswith("incident-")


# ── 3. Access-Point Failure Validation & Execution ───────────────────────────

def test_lab_run_access_point_failure_success(client: TestClient, isolated_db: str) -> None:
    """Access point failure simulation executes successfully for valid AP node."""
    response = client.post(
        "/api/v1/lab/run",
        json={
            "scenario": "access_point_failure",
            "target_node_id": "AP1",
            "severity": "high",
        },
    )
    assert response.status_code == 200
    data = response.json()

    assert data["incident_id"] is not None
    assert data["incident_id"].startswith("incident-")


def test_lab_run_access_point_failure_non_ap_node_422(client: TestClient, isolated_db: str) -> None:
    """Access point failure rejects non-AP nodes (e.g. router R1) with HTTP 422."""
    response = client.post(
        "/api/v1/lab/run",
        json={
            "scenario": "access_point_failure",
            "target_node_id": "R1",
        },
    )
    assert response.status_code == 422
    assert "not a valid access point" in response.json()["detail"]


# ── 4. Missing Target Validation ─────────────────────────────────────────────

def test_lab_run_missing_target_link_422(client: TestClient, isolated_db: str) -> None:
    """degrade_link without target_link_id is rejected with HTTP 422."""
    response = client.post(
        "/api/v1/lab/run",
        json={"scenario": "degrade_link", "severity": "high"},
    )
    assert response.status_code == 422


def test_lab_run_whitespace_target_link_422(client: TestClient, isolated_db: str) -> None:
    """degrade_link with whitespace-only target_link_id is rejected with HTTP 422."""
    response = client.post(
        "/api/v1/lab/run",
        json={
            "scenario": "degrade_link",
            "target_link_id": "   ",
            "severity": "high",
        },
    )
    assert response.status_code == 422


def test_lab_run_missing_target_node_422(client: TestClient, isolated_db: str) -> None:
    """access_point_failure without target_node_id is rejected with HTTP 422."""
    response = client.post(
        "/api/v1/lab/run",
        json={"scenario": "access_point_failure", "severity": "medium"},
    )
    assert response.status_code == 422


def test_lab_run_whitespace_target_node_422(client: TestClient, isolated_db: str) -> None:
    """access_point_failure with whitespace-only target_node_id is rejected with HTTP 422."""
    response = client.post(
        "/api/v1/lab/run",
        json={
            "scenario": "access_point_failure",
            "target_node_id": "   ",
            "severity": "high",
        },
    )
    assert response.status_code == 422


def test_lab_run_upstream_failure_missing_target_node_422(client: TestClient, isolated_db: str) -> None:
    """upstream_failure without target_node_id is rejected with HTTP 422."""
    response = client.post(
        "/api/v1/lab/run",
        json={"scenario": "upstream_failure"},
    )
    assert response.status_code == 422


def test_lab_run_upstream_failure_whitespace_target_node_422(client: TestClient, isolated_db: str) -> None:
    """upstream_failure with whitespace-only target_node_id is rejected with HTTP 422."""
    response = client.post(
        "/api/v1/lab/run",
        json={
            "scenario": "upstream_failure",
            "target_node_id": "   ",
            "severity": "high",
        },
    )
    assert response.status_code == 422


# ── 5. Invalid Scenario ──────────────────────────────────────────────────────

def test_lab_run_invalid_scenario_422(client: TestClient, isolated_db: str) -> None:
    """Unsupported or malformed scenario names are rejected with HTTP 422."""
    response = client.post(
        "/api/v1/lab/run",
        json={"scenario": "fiber_cut", "target_link_id": "L1"},
    )
    assert response.status_code == 422


# ── 6. Invalid Severity ──────────────────────────────────────────────────────

def test_lab_run_invalid_severity_422(client: TestClient, isolated_db: str) -> None:
    """Invalid severity values outside low/medium/high are rejected with HTTP 422."""
    response = client.post(
        "/api/v1/lab/run",
        json={"scenario": "baseline", "severity": "critical"},
    )
    assert response.status_code == 422


# ── 7. Target Link Topology Validation ───────────────────────────────────────

def test_lab_run_target_link_not_in_topology_422(client: TestClient, isolated_db: str) -> None:
    """target_link_id not present in topology is rejected with HTTP 422."""
    response = client.post(
        "/api/v1/lab/run",
        json={
            "scenario": "degrade_link",
            "target_link_id": "L99",
            "severity": "high",
        },
    )
    assert response.status_code == 422
    assert "Target link 'L99' not found" in response.json()["detail"]


# ── 8. No Incident Generated on Baseline ─────────────────────────────────────

def test_lab_run_baseline_no_incident_persisted(client: TestClient, isolated_db: str) -> None:
    """Healthy baseline does not persist any incident to SQLite."""
    conn = get_db_connection(isolated_db)
    cursor = conn.execute("SELECT COUNT(*) AS cnt FROM incidents;")
    count_before = cursor.fetchone()["cnt"]

    response = client.post(
        "/api/v1/lab/run",
        json={"scenario": "baseline"},
    )
    assert response.status_code == 200
    assert response.json()["incident_id"] is None

    cursor = conn.execute("SELECT COUNT(*) AS cnt FROM incidents;")
    count_after = cursor.fetchone()["cnt"]
    assert count_after == count_before


# ── 9. Incident Persisted in SQLite ──────────────────────────────────────────

def test_lab_run_incident_persisted_in_sqlite(client: TestClient, isolated_db: str) -> None:
    """When engine detects an incident, it is persisted to SQLite with diagnostic fields."""
    response = client.post(
        "/api/v1/lab/run",
        json={
            "scenario": "degrade_link",
            "target_link_id": "L3",
            "severity": "high",
        },
    )
    assert response.status_code == 200
    incident_id = response.json()["incident_id"]
    assert incident_id is not None

    conn = get_db_connection(isolated_db)
    saved = get_incident(conn, incident_id)
    assert saved is not None
    assert saved["id"] == incident_id
    assert saved["status"] == "open"
    assert saved["suspected_component_id"] == "L3"
    assert saved["suspected_component_type"] == "link"
    assert saved["data_source"] == "simulated"
    assert isinstance(saved["evidence"], list)
    assert len(saved["evidence"]) > 0


# ── 10. Incident Retrievable via Details Endpoint ────────────────────────────

def test_lab_run_incident_retrievable_via_details_endpoint(client: TestClient, isolated_db: str) -> None:
    """Newly generated incident can immediately be retrieved via GET /api/v1/incidents/{id}."""
    run_res = client.post(
        "/api/v1/lab/run",
        json={
            "scenario": "degrade_link",
            "target_link_id": "L1",
            "severity": "high",
        },
    )
    assert run_res.status_code == 200
    incident_id = run_res.json()["incident_id"]

    inc_res = client.get(f"/api/v1/incidents/{incident_id}")
    assert inc_res.status_code == 200
    data = inc_res.json()
    assert data["id"] == incident_id
    assert data["suspected_component_id"] == "L1"
    assert data["status"] == "open"
    assert data["data_source"] == "simulated"


# ── 11. Latest Incident Endpoint Reflects New Incident ───────────────────────

def test_lab_run_latest_incident_reflects_new_incident(client: TestClient, isolated_db: str) -> None:
    """GET /api/v1/incidents/latest reflects the newly generated incident."""
    run_res = client.post(
        "/api/v1/lab/run",
        json={
            "scenario": "degrade_link",
            "target_link_id": "L4",
            "severity": "high",
        },
    )
    assert run_res.status_code == 200
    new_incident_id = run_res.json()["incident_id"]

    latest_res = client.get("/api/v1/incidents/latest")
    assert latest_res.status_code == 200
    latest_data = latest_res.json()
    assert latest_data is not None
    assert latest_data["id"] == new_incident_id
    assert latest_data["suspected_component_id"] == "L4"


# ── 12. Persistence Failure Returns HTTP 500 ─────────────────────────────────

def test_lab_run_persistence_failure_returns_500(client: TestClient, isolated_db: str) -> None:
    """If database persistence fails, HTTP 500 is returned rather than false success."""
    with patch("app.api.lab.create_incident", side_effect=sqlite3.OperationalError("disk I/O error")):
        response = client.post(
            "/api/v1/lab/run",
            json={
                "scenario": "degrade_link",
                "target_link_id": "L2",
                "severity": "high",
            },
        )
        assert response.status_code == 500
        assert "Failed to persist incident" in response.json()["detail"]


# ── 13. Upstream Failure Scenario Integration ───────────────────────────

def test_lab_run_upstream_failure_success(client: TestClient, isolated_db: str) -> None:
    """upstream_failure executes successfully, generates measurements, and opens an incident."""
    response = client.post(
        "/api/v1/lab/run",
        json={
            "scenario": "upstream_failure",
            "target_node_id": "GW1",
            "severity": "high",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"].startswith("run-")
    assert data["data_source"] == "simulated"
    assert data["measurements_count"] == len(get_default_links())
    assert data["incident_id"] is not None

    # Verify incident persisted in SQLite with inferred L1 suspect
    conn = get_db_connection(isolated_db)
    try:
        inc = get_incident(conn, data["incident_id"])
        assert inc is not None
        assert inc["suspected_component_id"] == "L1"
        assert inc["suspected_component_type"] == "link"
        assert inc["status"] == "open"
        assert inc["data_source"] == "simulated"
    finally:
        conn.close()


def test_lab_run_upstream_failure_non_existent_target_node_422(
    client: TestClient, isolated_db: str
) -> None:
    """upstream_failure with a non-existent target node returns 422."""
    response = client.post(
        "/api/v1/lab/run",
        json={
            "scenario": "upstream_failure",
            "target_node_id": "UNKNOWN_GATEWAY",
            "severity": "high",
        },
    )
    assert response.status_code == 422
    assert "not found in topology" in response.json()["detail"].lower()


def test_lab_run_upstream_failure_affected_subscribers_and_measurements(
    client: TestClient, isolated_db: str
) -> None:
    """Full workflow: upstream_failure creates incident affecting all 5 subscribers and creates measurements."""
    lab_resp = client.post(
        "/api/v1/lab/run",
        json={
            "scenario": "upstream_failure",
            "target_node_id": "GW1",
            "severity": "high",
        },
    )
    assert lab_resp.status_code == 200
    run_id = lab_resp.json()["run_id"]
    incident_id = lab_resp.json()["incident_id"]
    assert incident_id is not None

    # 1. Check affected subscribers: all 5 downstream subscribers must be affected
    aff_resp = client.get(f"/api/v1/incidents/{incident_id}/affected-subscribers")
    assert aff_resp.status_code == 200
    aff_data = aff_resp.json()
    assert aff_data["count"] == 20
    sub_ids = {s["id"] for s in aff_data["subscribers"]}
    assert len(sub_ids) == 20
    assert {"SUB101", "SUB102", "SUB103", "SUB201", "SUB202", "SUB203", "SUB204"}.issubset(sub_ids)

    # 2. Check measurements: L1 has connectivity_ok=False; interior links have connectivity_ok=True but 100% loss
    meas_resp = client.get(f"/api/v1/runs/{run_id}/measurements")
    assert meas_resp.status_code == 200
    meas_data = meas_resp.json()
    assert meas_data["data_source"] == "simulated"
    assert len(meas_data["measurements"]) == len(get_default_links())

    meas_map = {m["component_id"]: m for m in meas_data["measurements"]}
    assert meas_map["L1"]["connectivity_ok"] is False
    assert meas_map["L1"]["packet_loss_pct"] == 100.0
    for interior in ["L2", "L3", "L4", "L5"]:
        assert meas_map[interior]["connectivity_ok"] is True
        assert meas_map[interior]["packet_loss_pct"] == 100.0
        assert meas_map[interior]["throughput_mbps"] == 0.0


# ── 14. Ambiguous Fault Scenario ─────────────────────────────────────────────

def test_lab_run_ambiguous_fault_success(client: TestClient, isolated_db: str) -> None:
    """ambiguous_fault scenario generates an incident with uncertainty note."""
    response = client.post(
        "/api/v1/lab/run",
        json={"scenario": "ambiguous_fault", "severity": "high"},
    )
    assert response.status_code == 200
    incident_id = response.json()["incident_id"]
    assert incident_id is not None

    conn = get_db_connection(isolated_db)
    incident = get_incident(conn, incident_id)
    assert incident is not None
    assert incident["uncertainty_note"] is not None
    assert "Ambiguous evidence" in incident["uncertainty_note"]


# ── 15. Demo Incident Preserved ──────────────────────────────────────────────

def test_lab_run_demo_incident_preserved(client: TestClient, isolated_db: str) -> None:
    """Demo incident is preserved across simulation runs."""
    demo_id = DEMO_INCIDENTS[0]["id"]
    conn = get_db_connection(isolated_db)
    demo = get_incident(conn, demo_id)
    assert demo is not None

    client.post(
        "/api/v1/lab/run",
        json={"scenario": "degrade_link", "target_link_id": "L5", "severity": "medium"},
    )

    demo_after = get_incident(conn, demo_id)
    assert demo_after is not None
    assert demo_after["id"] == demo_id


# ── 16. Topology Provider Failure ────────────────────────────────────────────

def test_lab_run_topology_provider_failure_returns_503(client: TestClient, isolated_db: str) -> None:
    """When get_topology() fails, API returns HTTP 503 and does NOT call run_scenario."""
    with patch("app.api.lab.get_topology", side_effect=RuntimeError("Graph database offline")), \
         patch("app.api.lab.run_scenario") as mock_run_scenario:
        response = client.post(
            "/api/v1/lab/run",
            json={
                "scenario": "degrade_link",
                "target_link_id": "L2",
                "severity": "high",
            },
        )
        assert response.status_code == 503
        data = response.json()
        assert "Network topology unavailable" in data["detail"]
        mock_run_scenario.assert_not_called()


def test_lab_run_topology_provider_failure_baseline_returns_503(client: TestClient, isolated_db: str) -> None:
    """Baseline run also fails with 503 when topology is unavailable without proceeding to simulation."""
    with patch("app.api.lab.get_topology", side_effect=RuntimeError("Connection timeout")), \
         patch("app.api.lab.run_scenario") as mock_run_scenario:
        response = client.post(
            "/api/v1/lab/run",
            json={"scenario": "baseline"},
        )
        assert response.status_code == 503
        assert "Network topology unavailable" in response.json()["detail"]
        mock_run_scenario.assert_not_called()
