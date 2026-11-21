"""Tests for POST /api/v1/probes/path endpoint."""

import pytest
from starlette.testclient import TestClient

from app.config import settings
from app.engine.facade import get_engine, get_incident_details


@pytest.fixture(autouse=True)
def clean_engine():
    engine = get_engine()
    engine.clear_live_measurements()
    engine.close_open_incidents()
    yield
    engine.clear_live_measurements()
    engine.close_open_incidents()


def test_path_probes_all_healthy(client: TestClient):
    """POST /api/v1/probes/path returns 200 with derived links and empty first_failed_nodes."""
    payload = {
        "agent_id": "agent-rampur-1",
        "vantage_node_id": "GW1",
        "results": [
            {"node_id": "GW1", "reachable": True, "latency_ms": 0.0, "packet_loss_pct": 0.0},
            {"node_id": "R1", "reachable": True, "latency_ms": 15.0, "packet_loss_pct": 0.0},
            {"node_id": "WB1", "reachable": True, "latency_ms": 17.0, "packet_loss_pct": 0.0},
            {"node_id": "AP2", "reachable": True, "latency_ms": 18.0, "packet_loss_pct": 0.0},
        ],
    }

    res = client.post("/api/v1/probes/path", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "ok"
    assert data["derived_links"] == 3
    assert data["first_failed_nodes"] == []
    assert data["incident_id"] is None


def test_path_probes_midtree_failure_localised(client: TestClient):
    """POST /api/v1/probes/path with failing WB3 localises incident to L6 with hop_trace attached."""
    payload = {
        "agent_id": "agent-rampur-1",
        "vantage_node_id": "GW1",
        "results": [
            {"node_id": "GW1", "reachable": True, "latency_ms": 0.0, "packet_loss_pct": 0.0},
            {"node_id": "R1", "reachable": True, "latency_ms": 15.0, "packet_loss_pct": 0.0},
            {"node_id": "WB3", "reachable": False, "latency_ms": None, "packet_loss_pct": 100.0},
            {"node_id": "WB4", "reachable": False, "latency_ms": None, "packet_loss_pct": 100.0},
            {"node_id": "R2", "reachable": False, "latency_ms": None, "packet_loss_pct": 100.0},
        ],
    }

    res = client.post("/api/v1/probes/path", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "ok"
    assert "WB3" in data["first_failed_nodes"]
    assert "WB4" not in data["first_failed_nodes"]
    assert "R2" not in data["first_failed_nodes"]
    assert data["incident_id"] is not None

    # Verify incident details in engine
    inc = get_incident_details(data["incident_id"])
    assert inc is not None
    assert inc.suspected_component_id == "L6"
    assert len(inc.hop_trace) > 0

    trace_map = {h.node_id: h.status for h in inc.hop_trace}
    assert trace_map["WB3"] == "failed"
    assert trace_map["WB4"] == "behind_failure"
    assert trace_map["R2"] == "behind_failure"


def test_path_probes_unknown_node_422(client: TestClient):
    """Unknown node_id raises HTTP 422 Unprocessable Entity."""
    payload = {
        "agent_id": "agent-rampur-1",
        "vantage_node_id": "GW1",
        "results": [
            {"node_id": "NON_EXISTENT_NODE_99", "reachable": True, "latency_ms": 10.0, "packet_loss_pct": 0.0},
        ],
    }

    res = client.post("/api/v1/probes/path", json=payload)
    assert res.status_code == 422
    assert "NON_EXISTENT_NODE_99" in res.text


def test_path_probes_api_key_auth(client: TestClient, monkeypatch):
    """When ingest_api_key is configured, missing or invalid X-API-Key is rejected with 401."""
    monkeypatch.setattr(settings, "ingest_api_key", "secret-test-key-123")

    payload = {
        "agent_id": "agent-rampur-1",
        "vantage_node_id": "GW1",
        "results": [
            {"node_id": "GW1", "reachable": True, "latency_ms": 0.0, "packet_loss_pct": 0.0},
        ],
    }

    # Missing header -> 401
    res1 = client.post("/api/v1/probes/path", json=payload)
    assert res1.status_code == 401

    # Wrong header -> 401
    res2 = client.post("/api/v1/probes/path", json=payload, headers={"X-API-Key": "wrong-key"})
    assert res2.status_code == 401

    # Correct header -> 200
    res3 = client.post("/api/v1/probes/path", json=payload, headers={"X-API-Key": "secret-test-key-123"})
    assert res3.status_code == 200
