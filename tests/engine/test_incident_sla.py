"""Unit and integration tests for incident resolution tracking and village SLA metrics."""

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
import pytest

from app.db.init import SCHEMA_SQL
from app.db.repository import (
    close_open_incidents,
    create_incident,
    get_incident,
    get_village_sla_stats,
)
from app.main import app


@pytest.fixture
def test_db():
    """In-memory SQLite connection initialized with HopTrace schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    yield conn
    conn.close()


def test_incident_resolved_and_duration_on_close(test_db):
    """When open incidents are closed, resolved_at and duration_seconds are accurately populated."""
    t0 = datetime.now(timezone.utc) - timedelta(minutes=15)
    inc_data = {
        "id": f"incident-{uuid.uuid4().hex[:8]}",
        "summary": "High packet loss on L6",
        "suspected_component_id": "L6",
        "status": "open",
        "created_at": t0.isoformat(),
    }
    create_incident(test_db, inc_data)

    before = get_incident(test_db, inc_data["id"])
    assert before["status"] == "open"
    assert before["resolved_at"] is None
    assert before["duration_seconds"] is None

    # Close incidents
    close_open_incidents(test_db)

    after = get_incident(test_db, inc_data["id"])
    assert after["status"] == "closed"
    assert after["resolved_at"] is not None
    # 15 minutes is approx 900 seconds (+/- 10s)
    assert after["duration_seconds"] is not None
    assert 890 <= after["duration_seconds"] <= 920


def test_sla_calculation_healthy_network(test_db):
    """Network with zero incidents reports 100% SLA uptime for all villages."""
    stats = get_village_sla_stats(test_db, window_hours=24)

    assert stats["window_hours"] == 24
    villages = stats["villages"]
    for vid in ("rampur", "bhatpur", "daulatpur"):
        assert villages[vid]["uptime_pct"] == 100.0
        assert villages[vid]["downtime_minutes"] == 0.0
        assert villages[vid]["active_incidents"] == 0
        assert villages[vid]["status"] == "healthy"


def test_sla_calculation_village_isolated_outage(test_db):
    """Outage on WB3 (Bhatpur) affects Bhatpur SLA only; Rampur and Daulatpur stay 100%."""
    # 1 hour outage in Bhatpur (WB3)
    inc_data = {
        "id": "inc-bhatpur-outage",
        "summary": "WB3 link down",
        "suspected_component_id": "WB3",
        "status": "closed",
        "created_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "resolved_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "duration_seconds": 3600,  # 60 mins
    }
    create_incident(test_db, inc_data)

    stats = get_village_sla_stats(test_db, window_hours=24)
    villages = stats["villages"]

    # In a 24-hr window (1440 mins), 60 mins down is (1440 - 60)/1440 = 95.83%
    assert villages["bhatpur"]["downtime_minutes"] == 60.0
    assert 95.8 <= villages["bhatpur"]["uptime_pct"] <= 95.9
    assert villages["bhatpur"]["status"] == "degraded"

    # Other villages are unaffected
    assert villages["rampur"]["uptime_pct"] == 100.0
    assert villages["daulatpur"]["uptime_pct"] == 100.0


def test_sla_calculation_gateway_outage_impacts_all_villages(test_db):
    """Gateway outage on L1 impacts all villages equally."""
    inc_data = {
        "id": "inc-gateway-outage",
        "summary": "L1 PoP Gateway blackout",
        "suspected_component_id": "L1",
        "status": "closed",
        "created_at": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(),
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": 1800,  # 30 mins
    }
    create_incident(test_db, inc_data)

    stats = get_village_sla_stats(test_db, window_hours=24)
    villages = stats["villages"]

    for vid in ("rampur", "bhatpur", "daulatpur"):
        assert villages[vid]["downtime_minutes"] == 30.0
        # (1440 - 30)/1440 = 97.92%
        assert 97.8 <= villages[vid]["uptime_pct"] <= 98.0


def test_api_topology_sla_endpoint():
    """GET /api/v1/topology/sla returns valid SLA response model."""
    client = TestClient(app)
    res = client.get("/api/v1/topology/sla?window_hours=12")
    assert res.status_code == 200
    data = res.json()
    assert data["window_hours"] == 12
    assert "villages" in data
    assert "rampur" in data["villages"]
    assert "bhatpur" in data["villages"]
    assert "daulatpur" in data["villages"]
