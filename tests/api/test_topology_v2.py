"""Tests for GET /api/v1/topology/risk endpoint.

Covers:
1. Empty store returns 200 with empty list.
2. After pushing baseline data: fields present, predictions null.
3. After pushing a ramp: ETA fields present and non-null.
4. gradual_degradation lab run at tick 0 returns incident_id=null.
5. LinkRiskItem schema: all optional prediction fields present in JSON.
6. data_source is always "simulated".
7. gradual_degradation requires target_link_id.
8. gradual_degradation rejects unknown link.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app.engine.models import Measurement
from backend.app.engine.telemetry import BASELINE_TELEMETRY, SimulatedTelemetryGenerator
from backend.app.engine.time_series import TimeSeriesStore


# ── Helpers ───────────────────────────────────────────────────────────────────


def _baseline_sample(link_id: str) -> Measurement:
    b = BASELINE_TELEMETRY[link_id]
    return Measurement(
        component_id=link_id,
        latency_ms=float(b["latency_ms"]),
        packet_loss_pct=float(b["packet_loss_pct"]),
        throughput_mbps=float(b["throughput_mbps"]),
        connectivity_ok=True,
    )


def _ramp_samples(link_id: str, n: int, start: float = 0.15) -> list[Measurement]:
    gen = SimulatedTelemetryGenerator()
    return [
        gen.generate_ramp_measurement(link_id, "high", start + i * 0.025)
        for i in range(n)
    ]


# ── Test 1: Empty store returns [] ────────────────────────────────────────────


def test_topology_risk_empty(client: TestClient) -> None:
    """GET /topology/risk returns 200 empty list when store has no data."""
    store = TimeSeriesStore()
    with patch("app.api.topology_v2.get_time_series_store", return_value=store):
        resp = client.get("/api/v1/topology/risk")
    assert resp.status_code == 200
    assert resp.json() == []


# ── Test 2: Baseline data, predictions null ───────────────────────────────────


def test_topology_risk_baseline_no_prediction(client: TestClient) -> None:
    """Baseline samples produce link entries with null prediction fields."""
    store = TimeSeriesStore()
    for lid in ["L1", "L3"]:
        for _ in range(6):
            store.push(lid, _baseline_sample(lid))

    with patch("app.api.topology_v2.get_time_series_store", return_value=store):
        resp = client.get("/api/v1/topology/risk")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    for entry in data:
        assert entry["data_source"] == "simulated"
        assert entry["predicted_eta_minutes"] is None
        assert entry["prediction_confidence"] is None
        assert entry["prediction_r2"] is None


# ── Test 3: Ramp data -> ETA present ─────────────────────────────────────────


def test_topology_risk_ramp_has_eta(client: TestClient) -> None:
    """After pushing ramp samples GET /topology/risk returns ETA for L3."""
    store = TimeSeriesStore()
    for m in _ramp_samples("L3", n=12):
        store.push("L3", m)

    with patch("app.api.topology_v2.get_time_series_store", return_value=store):
        resp = client.get("/api/v1/topology/risk")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    entry = data[0]
    assert entry["link_id"] == "L3"
    assert entry["predicted_eta_minutes"] is not None
    assert entry["predicted_eta_minutes"] > 0
    assert entry["prediction_confidence"] in ("high", "medium", "low")
    assert entry["prediction_r2"] is not None


# ── Test 4: Full schema present ───────────────────────────────────────────────


def test_topology_risk_schema_fields(client: TestClient) -> None:
    """Every LinkRiskItem must contain all documented fields."""
    store = TimeSeriesStore()
    store.push("L2", _baseline_sample("L2"))

    with patch("app.api.topology_v2.get_time_series_store", return_value=store):
        resp = client.get("/api/v1/topology/risk")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    entry = data[0]

    required_fields = [
        "link_id",
        "connectivity_ok",
        "packet_loss_pct",
        "latency_ms",
        "throughput_mbps",
        "data_source",
        "predicted_eta_minutes",
        "prediction_confidence",
        "prediction_r2",
        "predicted_eta_min_minutes",
        "predicted_eta_max_minutes",
    ]
    for field in required_fields:
        assert field in entry, f"Missing field '{field}' in LinkRiskItem"


# ── Test 5: data_source always simulated ─────────────────────────────────────


def test_topology_risk_data_source_simulated(client: TestClient) -> None:
    """data_source must always be 'simulated'."""
    store = TimeSeriesStore()
    for lid in ["L1", "L2", "L3", "L4", "L5"]:
        store.push(lid, _baseline_sample(lid))

    with patch("app.api.topology_v2.get_time_series_store", return_value=store):
        resp = client.get("/api/v1/topology/risk")
    assert resp.status_code == 200
    for entry in resp.json():
        assert entry["data_source"] == "simulated"


# ── Test 6: gradual_degradation lab run returns null incident at tick 0 ───────


def test_gradual_degradation_lab_run_returns_null_incident(
    client: TestClient, isolated_db: str
) -> None:
    """POST lab/run gradual_degradation at progress=0 must return incident_id=null."""
    resp = client.post(
        "/api/v1/lab/run",
        json={
            "scenario": "gradual_degradation",
            "target_link_id": "L3",
            "severity": "high",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"].startswith("run-")
    assert data["incident_id"] is None, (
        "gradual_degradation at tick 0 (progress=0) should produce no incident"
    )
    assert data["measurements_count"] >= 5


# ── Test 7: gradual_degradation requires target_link_id ──────────────────────


def test_gradual_degradation_requires_target_link(client: TestClient) -> None:
    """gradual_degradation without target_link_id must return 422."""
    resp = client.post(
        "/api/v1/lab/run",
        json={"scenario": "gradual_degradation", "severity": "high"},
    )
    assert resp.status_code == 422


# ── Test 8: gradual_degradation rejects unknown link ─────────────────────────


def test_gradual_degradation_invalid_link(client: TestClient) -> None:
    """gradual_degradation with an unknown link_id must return 422."""
    resp = client.post(
        "/api/v1/lab/run",
        json={
            "scenario": "gradual_degradation",
            "target_link_id": "L99",
            "severity": "high",
        },
    )
    assert resp.status_code == 422
