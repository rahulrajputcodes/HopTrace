"""
Tests for Agent Heartbeat and Status Monitoring (Blind-Spot Detection).

Adheres to HopTrace Part 1 Contract §2.4 and TRACK_B_api_frontend.md §B2.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from app.config import settings
from app.services.agent_monitor import agent_monitor, reset_agent_monitor


def setup_function() -> None:
    """Reset agent monitor before each test."""
    reset_agent_monitor()


def test_agent_heartbeat_and_status_contract_shape(client: TestClient) -> None:
    """Agent heartbeat registers successfully and status response matches contract §2.4."""
    payload = {
        "agent_id": "agent-rampur-1",
        "site_id": "rampur",
        "timestamp": "2026-11-15T10:42:11Z",
        "buffered_count": 0,
        "version": "2.1",
    }
    resp = client.post("/api/v1/agent/heartbeat", json=payload)
    assert resp.status_code == 200
    hb_data = resp.json()
    assert hb_data["status"] == "ok"
    assert hb_data["agent_id"] == "agent-rampur-1"

    # Status response check
    status_resp = client.get("/api/v1/agent/status")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert "agents" in data
    assert len(data["agents"]) == 1

    agent = data["agents"][0]
    assert agent["agent_id"] == "agent-rampur-1"
    assert agent["site_id"] == "rampur"
    assert agent["status"] == "online"
    assert agent["buffered_count"] == 0
    assert isinstance(agent["silent_for_seconds"], int)
    assert agent["silent_for_seconds"] == 0
    assert "last_seen_utc" in agent


def test_agent_online_to_silent_transition_with_injected_clock() -> None:
    """Direct service test: agent transitions from online to silent after settings.agent_silent_seconds."""
    t0 = datetime(2026, 11, 15, 12, 0, 0, tzinfo=timezone.utc)
    agent_monitor.record_heartbeat(
        agent_id="agent-rampur-1",
        site_id="rampur",
        timestamp=t0.isoformat(),
        buffered_count=5,
        version="2.1",
        now=t0,
    )

    # Within silence threshold (default 20s, test at 15s)
    t1 = t0 + timedelta(seconds=15)
    snap1 = agent_monitor.get_status_snapshot(now=t1)
    assert len(snap1) == 1
    assert snap1[0]["status"] == "online"
    assert snap1[0]["silent_for_seconds"] == 15
    assert snap1[0]["buffered_count"] == 5

    # Exceeded silence threshold (at 25s)
    t2 = t0 + timedelta(seconds=25)
    snap2 = agent_monitor.get_status_snapshot(now=t2)
    assert len(snap2) == 1
    assert snap2[0]["status"] == "silent"
    assert snap2[0]["silent_for_seconds"] == 25


def test_agent_auto_register(client: TestClient) -> None:
    """Unknown agents auto-register on heartbeat."""
    for i in (1, 2):
        client.post(
            "/api/v1/agent/heartbeat",
            json={
                "agent_id": f"agent-node-{i}",
                "site_id": f"site-{i}",
                "timestamp": "2026-11-15T10:42:11Z",
                "buffered_count": i * 10,
                "version": "2.1",
            },
        )

    resp = client.get("/api/v1/agent/status")
    assert resp.status_code == 200
    agents = resp.json()["agents"]
    assert len(agents) == 2
    agent_ids = {a["agent_id"] for a in agents}
    assert agent_ids == {"agent-node-1", "agent-node-2"}


def test_agent_heartbeat_api_key_auth(client: TestClient, monkeypatch) -> None:
    """Header X-API-Key is enforced when INGEST_API_KEY is configured."""
    monkeypatch.setattr(settings, "ingest_api_key", "secret-test-key")

    payload = {
        "agent_id": "agent-rampur-1",
        "site_id": "rampur",
        "timestamp": "2026-11-15T10:42:11Z",
    }

    # 1. Missing key -> 401
    resp_no_key = client.post("/api/v1/agent/heartbeat", json=payload)
    assert resp_no_key.status_code == 401
    assert "invalid or missing" in resp_no_key.json()["detail"].lower()

    # 2. Bad key -> 401
    resp_bad_key = client.post(
        "/api/v1/agent/heartbeat",
        json=payload,
        headers={"X-API-Key": "wrong-key"},
    )
    assert resp_bad_key.status_code == 401

    # 3. Correct key -> 200
    resp_good_key = client.post(
        "/api/v1/agent/heartbeat",
        json=payload,
        headers={"X-API-Key": "secret-test-key"},
    )
    assert resp_good_key.status_code == 200
    assert resp_good_key.json()["status"] == "ok"
