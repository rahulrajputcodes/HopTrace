"""
Test that running a baseline scenario clears any active fault state.

Validates Task E:
- After POST /lab/run with baseline:
  (a) streaming loop stops overlaying old measurements
  (b) active_incident is null in telemetry_batch and connected payloads
  (c) previous open incidents are marked closed in the engine store
- assert latest open incident is None and the next batch has active_incident null.
"""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from app.engine.facade import get_engine, get_latest_open_incident, get_incident_details


def test_baseline_clears_live_fault(client: TestClient, isolated_db: str) -> None:
    engine = get_engine()

    with client:
        # 1. Trigger a fault via degrade_link on L3
        degrade_resp = client.post(
            "/api/v1/lab/run",
            json={"scenario": "degrade_link", "target_link_id": "L3", "severity": "high"},
        )
        assert degrade_resp.status_code == 200
        degrade_data = degrade_resp.json()
        incident_id = degrade_data["incident_id"]
        assert incident_id is not None
        assert incident_id.startswith("incident-")

        # Verify that an open incident exists
        open_inc = get_latest_open_incident()
        assert open_inc is not None
        assert open_inc.id == incident_id
        assert open_inc.status == "open"

        # 2. Run baseline scenario
        base_resp = client.post(
            "/api/v1/lab/run",
            json={"scenario": "baseline"},
        )
        assert base_resp.status_code == 200
        base_data = base_resp.json()
        assert base_data["incident_id"] is None

        # (c) Assert latest open incident is None and previous incident is marked closed in engine store
        latest_open = get_latest_open_incident()
        assert latest_open is None, f"Expected latest open incident to be None, got {latest_open}"
        assert engine.get_latest_open_incident() is None

        prev_incident = engine.get_incident_details(incident_id)
        assert prev_incident is not None
        assert prev_incident.status == "closed", f"Expected previous incident to be closed, got {prev_incident.status}"

        # Assert GET /incidents/latest returns null when latest incident is closed
        latest_resp = client.get("/api/v1/incidents/latest")
        assert latest_resp.status_code == 200
        assert latest_resp.json() is None, f"Expected /incidents/latest to be null, got {latest_resp.json()}"

        # Historical incident lookup by ID still works
        hist_resp = client.get(f"/api/v1/incidents/{incident_id}")
        assert hist_resp.status_code == 200
        assert hist_resp.json()["id"] == incident_id
        assert hist_resp.json()["status"] == "closed"

        # (b) Read connected and one telemetry_batch, assert active_incident null and L3 latency within tolerance
        with client.websocket_connect("/ws/telemetry") as ws:
            # 1. Immediate greeting
            conn_msg = ws.receive_json()
            assert conn_msg["type"] == "connected"
            assert conn_msg["active_incident"] is None, (
                f"Expected connected active_incident to be null, got {conn_msg['active_incident']}"
            )

            # 2. Next message: telemetry_batch (~3s tick)
            batch_msg = ws.receive_json()
            assert batch_msg["type"] == "telemetry_batch"
            assert batch_msg["active_incident"] is None, (
                f"Expected telemetry_batch active_incident to be null, got {batch_msg['active_incident']}"
            )

            # Assert L3 latency is within baseline tolerance: abs(l3 - 25.0) < 10.0
            measurements = batch_msg.get("measurements", [])
            l3_meas = next((m for m in measurements if m.get("link_id") == "L3"), None)
            assert l3_meas is not None, "L3 measurement not found in telemetry_batch"
            l3_latency = l3_meas["latency_ms"]
            assert abs(l3_latency - 25.0) < 10.0, (
                f"Expected L3 latency within baseline tolerance abs(lat - 25.0) < 10.0, got {l3_latency}"
            )
