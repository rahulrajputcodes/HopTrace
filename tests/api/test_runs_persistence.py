"""Automated tests for SQLite persistence of lab runs, telemetry observations, and restart recovery.

Tests:
1. Run and measurements persisted to SQLite: survives clearing in-memory _runs.
2. Restart simulation: brand-new app instance pointing to the same SQLite DB file
   confirms past runs, live ingested runs, and incidents still return HTTP 200.
3. Retention limit: verify oldest runs and measurements are automatically pruned
   when the total run count exceeds RUNS_RETENTION_LIMIT.
4. WebSocket streaming recovery: verify engine restores incident run telemetry
   from SQLite after a restart for WebSocket streaming overlay.
"""
from __future__ import annotations

import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.connection import get_db_connection
from app.db.init import init_db
from app.db.repository import count_runs, get_latest_open_incident, get_run
from app.engine import facade
from app.engine.facade import get_engine, seed_topology
from app.main import app


def test_run_measurements_survive_memory_clear(client: TestClient) -> None:
    """A generated lab run is persisted in SQLite and retrieved even after clearing in-memory _runs."""
    # 1. Generate run via lab endpoint
    lab_resp = client.post(
        "/api/v1/lab/run",
        json={
            "scenario": "degrade_link",
            "target_link_id": "L3",
            "severity": "high",
        },
    )
    assert lab_resp.status_code == 200
    run_id = lab_resp.json()["run_id"]
    assert run_id

    # 2. Clear engine's in-memory runs dictionary
    engine = get_engine()
    assert run_id in engine._runs
    engine._runs.clear()
    assert run_id not in engine._runs

    # 3. GET /runs/{run_id}/measurements must read from SQLite and return 200
    meas_resp = client.get(f"/api/v1/runs/{run_id}/measurements")
    assert meas_resp.status_code == 200
    data = meas_resp.json()

    assert data["run_id"] == run_id
    assert data["data_source"] == "simulated"
    assert len(data["measurements"]) > 0

    # L3 should reflect degraded telemetry
    l3_meas = next(m for m in data["measurements"] if m["component_id"] == "L3")
    assert l3_meas["latency_ms"] is not None and l3_meas["latency_ms"] >= 100.0
    assert l3_meas["packet_loss_pct"] is not None and l3_meas["packet_loss_pct"] >= 15.0

    # Also verify it repopulated memory cache
    assert run_id in engine._runs


def test_restart_simulation_new_app_same_db(tmp_path) -> None:
    """Restart simulation: fresh app and engine instance on the same SQLite database file."""
    db_file = str(tmp_path / "restart_simulation.db")
    orig_db_path = settings.sqlite_db_path
    orig_limit = settings.runs_retention_limit
    try:
        settings.sqlite_db_path = db_file
        init_db(db_file, seed_demo=True, seed_incidents=True)

        # ── Instance 1: Generate runs and incidents ───────────────────────────
        facade._engine_instance = None
        seed_topology(force_in_memory=True)
        client_1 = TestClient(app)

        # 1. Live telemetry ingest
        ingest_resp = client_1.post(
            "/api/v1/measurements/ingest",
            json=[
                {
                    "component_id": "L1",
                    "latency_ms": 11.2,
                    "packet_loss_pct": 0.0,
                    "throughput_mbps": 98.0,
                    "connectivity_ok": True,
                }
            ],
        )
        assert ingest_resp.status_code == 200

        # Retrieve the live run_id from the database
        conn = get_db_connection(db_file)
        cursor = conn.execute("SELECT run_id FROM runs WHERE data_source = 'live' ORDER BY created_at DESC LIMIT 1;")
        live_run_row = cursor.fetchone()
        assert live_run_row is not None
        run_id_live = live_run_row["run_id"]
        conn.close()

        # 2. Lab run: degrade L2 (creates and leaves an open incident)
        lab_resp = client_1.post(
            "/api/v1/lab/run",
            json={
                "scenario": "degrade_link",
                "target_link_id": "L2",
                "severity": "medium",
            },
        )
        assert lab_resp.status_code == 200
        run_id_lab = lab_resp.json()["run_id"]
        incident_id = lab_resp.json()["incident"]["id"]

        # ── SIMULATE RESTART: Tear down in-memory singletons ───────────────────
        facade._engine_instance = None
        # Instance 2 is now started against the exact same DB file
        client_2 = TestClient(app)
        engine_2 = get_engine()

        # In-memory dictionary is completely empty on fresh startup
        assert run_id_lab not in engine_2._runs
        assert run_id_live not in engine_2._runs

        # 3. Confirm past lab run still returns 200 with full telemetry
        meas_resp = client_2.get(f"/api/v1/runs/{run_id_lab}/measurements")
        assert meas_resp.status_code == 200
        lab_data = meas_resp.json()
        assert lab_data["run_id"] == run_id_lab
        assert lab_data["data_source"] == "simulated"
        assert len(lab_data["measurements"]) > 0

        # 4. Confirm past live ingested run still returns 200
        live_resp = client_2.get(f"/api/v1/runs/{run_id_live}/measurements")
        assert live_resp.status_code == 200
        live_data = live_resp.json()
        assert live_data["run_id"] == run_id_live
        assert live_data["data_source"] == "live"
        l1_meas = next(m for m in live_data["measurements"] if m["component_id"] == "L1")
        assert l1_meas["latency_ms"] == 11.2

        # 5. Confirm demo incident and run return 200
        demo_resp = client_2.get("/api/v1/runs/run-demo-001/measurements")
        assert demo_resp.status_code == 200
        assert demo_resp.json()["run_id"] == "run-demo-001"

        # 6. Confirm incident details retrieved after restart
        inc_resp = client_2.get(f"/api/v1/incidents/{incident_id}")
        assert inc_resp.status_code == 200
        assert inc_resp.json()["id"] == incident_id

        # 7. Confirm open incident and past run measurements are restored for WS stream
        conn = get_db_connection(db_file)
        latest_open = get_latest_open_incident(conn)
        conn.close()
        assert latest_open is not None
        assert latest_open["id"] == incident_id
        incident_run = engine_2.get_run_measurements(latest_open["run_id"])
        assert incident_run is not None
        assert incident_run.run_id == run_id_lab

    finally:
        facade._engine_instance = None
        settings.sqlite_db_path = orig_db_path
        settings.runs_retention_limit = orig_limit


def test_runs_retention_limit(tmp_path) -> None:
    """Runs and measurements are pruned when exceeding RUNS_RETENTION_LIMIT."""
    db_file = str(tmp_path / "retention_test.db")
    orig_db_path = settings.sqlite_db_path
    orig_limit = settings.runs_retention_limit
    try:
        settings.sqlite_db_path = db_file
        # Configure small retention limit of 3
        settings.runs_retention_limit = 3
        init_db(db_file, seed_demo=False, seed_incidents=False)

        facade._engine_instance = None
        seed_topology(force_in_memory=True)
        client = TestClient(app)

        run_ids = []
        for i in range(5):
            resp = client.post(
                "/api/v1/lab/run",
                json={"scenario": "baseline"},
            )
            assert resp.status_code == 200
            run_ids.append(resp.json()["run_id"])

        conn = get_db_connection(db_file)
        try:
            # Only the latest 3 runs should remain in SQLite
            total_runs = count_runs(conn)
            assert total_runs == 3

            # Oldest 2 runs should be purged
            for old_id in run_ids[:2]:
                assert get_run(conn, old_id) is None
                # Clear memory to force SQLite check
                get_engine()._runs.pop(old_id, None)
                resp = client.get(f"/api/v1/runs/{old_id}/measurements")
                assert resp.status_code == 404

            # Newest 3 runs should exist
            for new_id in run_ids[2:]:
                assert get_run(conn, new_id) is not None
                get_engine()._runs.pop(new_id, None)
                resp = client.get(f"/api/v1/runs/{new_id}/measurements")
                assert resp.status_code == 200
        finally:
            conn.close()

    finally:
        facade._engine_instance = None
        settings.sqlite_db_path = orig_db_path
        settings.runs_retention_limit = orig_limit
