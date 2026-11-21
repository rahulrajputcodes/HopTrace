"""Tests for WebSocket telemetry streaming in live and demo modes."""

import pytest
from starlette.testclient import TestClient

from app.api.telemetry_ws import build_telemetry_batch
from app.config import settings
from app.engine.facade import get_engine
from app.engine.models import Measurement


@pytest.fixture(autouse=True)
def clean_engine():
    engine = get_engine()
    engine.clear_live_measurements()
    engine.close_open_incidents()
    yield
    engine.clear_live_measurements()
    engine.close_open_incidents()


def test_build_telemetry_batch_demo(monkeypatch):
    """In demo mode, batch includes data_mode='demo', freshness, and last_seen_utc."""
    monkeypatch.setattr(settings, "data_mode", "demo")

    batch = build_telemetry_batch(tick=1)

    assert batch["type"] == "telemetry_batch"
    assert batch["data_mode"] == "demo"
    assert "agents" in batch
    assert isinstance(batch["measurements"], list)
    assert len(batch["measurements"]) >= 14

    for m in batch["measurements"]:
        assert "link_id" in m
        assert "freshness" in m
        assert m["freshness"] in ("live", "stale", "simulated", "no_data")
        assert "last_seen_utc" in m


def test_build_telemetry_batch_live_no_data(monkeypatch):
    """In live mode with no live readings, all links report freshness='no_data' with null metrics."""
    monkeypatch.setattr(settings, "data_mode", "live")

    batch = build_telemetry_batch(tick=1)

    assert batch["type"] == "telemetry_batch"
    assert batch["data_mode"] == "live"
    assert "agents" in batch
    assert len(batch["measurements"]) == 14  # All 14 topology links emitted

    for m in batch["measurements"]:
        assert m["freshness"] == "no_data"
        assert m["latency_ms"] is None
        assert m["packet_loss_pct"] is None
        assert m["throughput_mbps"] is None
        assert m["connectivity_ok"] is None
        assert m["data_source"] == "no_data"


def test_build_telemetry_batch_live_with_reading(monkeypatch):
    """In live mode, only reported links show metrics and freshness='live'."""
    monkeypatch.setattr(settings, "data_mode", "live")
    engine = get_engine()

    m1 = Measurement(
        component_id="L1",
        latency_ms=18.5,
        packet_loss_pct=0.0,
        throughput_mbps=95.0,
        connectivity_ok=True,
    )
    engine.ingest_live_measurements([m1])

    batch = build_telemetry_batch(tick=1)

    assert batch["data_mode"] == "live"
    l1_item = next((m for m in batch["measurements"] if m["link_id"] == "L1"), None)
    assert l1_item is not None
    assert l1_item["freshness"] == "live"
    assert l1_item["latency_ms"] == 18.5
    assert l1_item["data_source"] == "live"

    # Other links must be no_data
    l2_item = next((m for m in batch["measurements"] if m["link_id"] == "L2"), None)
    assert l2_item is not None
    assert l2_item["freshness"] == "no_data"
    assert l2_item["latency_ms"] is None


def test_ws_connection_initial_message(client: TestClient):
    """Connecting to /ws/telemetry delivers the initial connected handshake."""
    with client.websocket_connect("/ws/telemetry") as ws:
        handshake = ws.receive_json()
        assert handshake["type"] == "connected"
        assert "message" in handshake
