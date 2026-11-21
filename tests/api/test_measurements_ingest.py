"""Automated tests for Live Telemetry Ingestion endpoint (POST /api/v1/measurements/ingest).

Tests:
1. Ingest success: valid components ingested with status 200 and data_source="live".
2. Unknown component rejection: returns HTTP 422.
3. API Key auth:
   - When INGEST_API_KEY is configured, requests without key or with bad key return 401.
   - Requests with matching X-API-Key succeed with 200.
4. Live data source propagation into engine and overlay.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.engine.facade import clear_live_measurements, get_live_measurements


@pytest.fixture(autouse=True)
def cleanup_live_measurements():
    """Ensure live measurements and api key settings are clean before and after each test."""
    clear_live_measurements()
    orig_key = settings.ingest_api_key
    yield
    clear_live_measurements()
    settings.ingest_api_key = orig_key


def test_ingest_measurements_success(client: TestClient) -> None:
    """POST /api/v1/measurements/ingest accepts valid telemetry and returns 200 with data_source='live'."""
    settings.ingest_api_key = ""

    payload = [
        {
            "component_id": "L1",
            "latency_ms": 12.4,
            "packet_loss_pct": 0.0,
            "throughput_mbps": 95.0,
            "connectivity_ok": True,
            "timestamp": "2026-11-04T12:00:00Z",
        },
        {
            "component_id": "L2",
            "latency_ms": 25.1,
            "packet_loss_pct": 1.2,
            "throughput_mbps": 48.0,
            "connectivity_ok": True,
        },
    ]

    resp = client.post("/api/v1/measurements/ingest", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "ok"
    assert data["ingested_count"] == 2
    assert data["data_source"] == "live"

    # Verify live measurements stored in engine
    live = get_live_measurements()
    assert "L1" in live
    assert "L2" in live
    assert live["L1"].data_source == "live"
    assert live["L1"].latency_ms == 12.4
    assert live["L2"].packet_loss_pct == 1.2


def test_ingest_measurements_bad_component(client: TestClient) -> None:
    """POST /api/v1/measurements/ingest rejects unknown component IDs with HTTP 422."""
    settings.ingest_api_key = ""

    payload = [
        {
            "component_id": "UNKNOWN_LINK_999",
            "latency_ms": 50.0,
            "packet_loss_pct": 0.0,
            "connectivity_ok": True,
        }
    ]

    resp = client.post("/api/v1/measurements/ingest", json=payload)
    assert resp.status_code == 422
    assert "Unknown component_id" in resp.json()["detail"]


def test_ingest_measurements_api_key_auth(client: TestClient) -> None:
    """When INGEST_API_KEY is configured, require valid X-API-Key header."""
    settings.ingest_api_key = "test-secret-key-42"

    payload = [
        {
            "component_id": "L1",
            "latency_ms": 15.0,
            "packet_loss_pct": 0.0,
            "connectivity_ok": True,
        }
    ]

    # 1. Missing header -> 401
    resp_no_key = client.post("/api/v1/measurements/ingest", json=payload)
    assert resp_no_key.status_code == 401
    assert "Invalid or missing X-API-Key" in resp_no_key.json()["detail"]

    # 2. Bad header -> 401
    resp_bad_key = client.post(
        "/api/v1/measurements/ingest",
        json=payload,
        headers={"X-API-Key": "wrong-secret"},
    )
    assert resp_bad_key.status_code == 401

    # 3. Correct header -> 200
    resp_valid = client.post(
        "/api/v1/measurements/ingest",
        json=payload,
        headers={"X-API-Key": "test-secret-key-42"},
    )
    assert resp_valid.status_code == 200
    assert resp_valid.json()["data_source"] == "live"


def test_ingest_measurements_triggers_diagnosis_and_live_flag(client: TestClient) -> None:
    """Severe packet loss in ingested live measurement triggers open incident tagged live."""
    settings.ingest_api_key = ""

    # Ingest a severe outage on L1
    payload = [
        {
            "component_id": "L1",
            "latency_ms": 999.0,
            "packet_loss_pct": 100.0,
            "throughput_mbps": 0.0,
            "connectivity_ok": False,
        }
    ]

    resp = client.post("/api/v1/measurements/ingest", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["data_source"] == "live"
    # An incident should be triggered for L1 failure
    assert data["incident_id"] is not None

    # Verify incident endpoint returns the incident
    inc_resp = client.get(f"/api/v1/incidents/{data['incident_id']}")
    assert inc_resp.status_code == 200
    inc_data = inc_resp.json()
    assert inc_data["suspected_component_id"] == "L1"
    assert inc_data["status"] == "open"
