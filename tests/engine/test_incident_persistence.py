"""Unit tests for SQLite incident persistence with cause and hop_trace extras."""

import sqlite3
import pytest

from app.db.connection import get_db_connection
from app.db.init import init_db
from app.db.repository import create_incident, get_incident, get_latest_incident
from app.engine.models import HopResult


def test_incident_extras_round_trip_persistence(tmp_path):
    """Verifies cause, cause_confidence, cause_reasoning, and hop_trace persist and round-trip via extras_json."""
    db_file = str(tmp_path / "test_persist.db")
    init_db(db_path=db_file, seed_demo=False, seed_incidents=False)

    conn = get_db_connection(db_file)
    try:
        hop_trace = [
            HopResult(node_id="GW1", link_id=None, depth=0, reachable=True, latency_ms=0.0, packet_loss_pct=0.0, status="ok"),
            HopResult(node_id="R1", link_id="L1", depth=1, reachable=True, latency_ms=15.0, packet_loss_pct=0.0, status="ok"),
            HopResult(node_id="WB3", link_id="L6", depth=2, reachable=False, latency_ms=None, packet_loss_pct=100.0, status="failed"),
            HopResult(node_id="WB4", link_id="L7", depth=3, reachable=False, latency_ms=None, packet_loss_pct=100.0, status="behind_failure"),
        ]

        incident_data = {
            "id": "inc-roundtrip-001",
            "run_id": "run-test-001",
            "status": "open",
            "suspected_component_id": "L6",
            "suspected_component_type": "link",
            "summary": "[isolated] Degradation localized to link L6",
            "confidence_score": 0.85,
            "evidence": [{"metric": "connectivity_ok", "status": "anomaly"}],
            "uncertainty_note": "Physical link down",
            "data_source": "live",
            "cause": "power_outage",
            "cause_confidence": 0.60,
            "cause_reasoning": ["Co-located power loss detected across site"],
            "hop_trace": hop_trace,
        }

        created = create_incident(conn, incident_data)
        assert created is not None
        assert created["id"] == "inc-roundtrip-001"
        assert created["cause"] == "power_outage"
        assert created["cause_confidence"] == 0.60
        assert created["cause_reasoning"] == ["Co-located power loss detected across site"]
        assert len(created["hop_trace"]) == 4

        # Read back via get_incident
        fetched = get_incident(conn, "inc-roundtrip-001")
        assert fetched is not None
        assert fetched["cause"] == "power_outage"
        assert fetched["cause_confidence"] == 0.60
        assert fetched["cause_reasoning"] == ["Co-located power loss detected across site"]
        assert len(fetched["hop_trace"]) == 4

        trace_nodes = [h["node_id"] for h in fetched["hop_trace"]]
        assert trace_nodes == ["GW1", "R1", "WB3", "WB4"]
        assert fetched["hop_trace"][2]["status"] == "failed"
        assert fetched["hop_trace"][3]["status"] == "behind_failure"

        # Read back via get_latest_incident
        latest = get_latest_incident(conn)
        assert latest is not None
        assert latest["id"] == "inc-roundtrip-001"
        assert latest["cause"] == "power_outage"

    finally:
        conn.close()
