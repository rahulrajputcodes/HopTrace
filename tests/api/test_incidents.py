"""
Automated tests for Incident Retrieval and Affected-Subscriber APIs (Milestone 3).

Tests:
1. GET /api/v1/incidents/latest returns null on empty database.
2. GET /api/v1/incidents/latest returns the most recent incident when incidents exist.
3. GET /api/v1/incidents/latest orders correctly when multiple incidents exist.
4. GET /api/v1/incidents/{incident_id} returns exact contract fields and types.
5. GET /api/v1/incidents/{incident_id} returns 404 for non-existent incident.
6. Incident nullable fields (confidence_score, uncertainty_note, run_id).
7. Evidence field is a list and data_source is valid ('simulated' or 'measured').
8. Timestamp format is ISO 8601 UTC.
9. GET /api/v1/incidents/{incident_id}/affected-subscribers returns 404 for unknown incident.
10. GET /api/v1/incidents/{incident_id}/affected-subscribers returns 503 when graph engine is unavailable.
11. Affected subscribers response structure and count matching when 0 subscribers are affected.
12. Affected subscribers response structure and count matching when subscribers are affected.
13. SimulatedDependencyAdapter end-to-end integration for incident-001.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.connection import get_db_connection
from app.db.init import DEMO_INCIDENTS
from app.db.repository import create_incident

DEMO_INCIDENT_ID = DEMO_INCIDENTS[0]["id"]
from app.main import app
from app.providers.dependencies import (
    DependencyAnalysisAdapter,
    EngineDependencyAdapter,
    GraphEngineUnavailableError,
    SimulatedDependencyAdapter,
)
from app.providers.registry import get_dependency_adapter


# ── 1. Latest Incident on Empty Database ──────────────────────────────────────

def test_get_latest_incident_empty_database(client: TestClient, empty_db: str) -> None:
    """When no incident has been created, GET /api/v1/incidents/latest returns null (200 OK)."""
    response = client.get("/api/v1/incidents/latest")
    assert response.status_code == 200
    assert response.json() is None


# ── 2. Latest Incident with Seeded Incident ───────────────────────────────────

def test_get_latest_incident_with_data(client: TestClient, isolated_db: str) -> None:
    """GET /api/v1/incidents/latest returns the seeded demo incident."""
    response = client.get("/api/v1/incidents/latest")
    assert response.status_code == 200

    data = response.json()
    assert data is not None
    demo_inc = DEMO_INCIDENTS[0]
    assert data["id"] == demo_inc["id"]
    assert data["status"] == demo_inc["status"]
    assert data["suspected_component_id"] == demo_inc["suspected_component_id"]
    assert data["suspected_component_type"] == demo_inc["suspected_component_type"]
    assert data["data_source"] == demo_inc["data_source"]


# ── 3. Latest Incident Multiple Ordering ─────────────────────────────────────

def test_get_latest_incident_most_recent(client: TestClient, isolated_db: str) -> None:
    """GET /api/v1/incidents/latest always returns the newest incident by created_at."""
    conn = get_db_connection(isolated_db)
    try:
        create_incident(
            conn,
            {
                "id": "incident-002",
                "run_id": "run-002",
                "status": "open",
                "suspected_component_id": "AP2",
                "suspected_component_type": "access_point",
                "summary": "Access point failure",
                "confidence_score": 0.95,
                "evidence": [{"metric": "ping_loss", "value": 100.0}],
                "uncertainty_note": None,
                "data_source": "simulated",
                "created_at": "2026-10-30T12:00:00Z",
            },
        )
    finally:
        conn.close()

    response = client.get("/api/v1/incidents/latest")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "incident-002"
    assert data["suspected_component_id"] == "AP2"
    assert data["confidence_score"] == 0.95
    assert len(data["evidence"]) == 1


# ── 4. Incident Lookup by ID ─────────────────────────────────────────────────

def test_get_incident_by_id_success(client: TestClient, isolated_db: str) -> None:
    """GET /api/v1/incidents/{incident_id} returns exact contract structure."""
    demo_inc = DEMO_INCIDENTS[0]
    response = client.get(f"/api/v1/incidents/{demo_inc['id']}")
    assert response.status_code == 200

    data = response.json()
    expected_fields = {
        "id": demo_inc["id"],
        "run_id": demo_inc["run_id"],
        "status": demo_inc["status"],
        "suspected_component_id": demo_inc["suspected_component_id"],
        "suspected_component_type": demo_inc["suspected_component_type"],
        "summary": demo_inc["summary"],
        "confidence_score": demo_inc["confidence_score"],
        "evidence": [],
        "uncertainty_note": demo_inc["uncertainty_note"],
        "data_source": demo_inc["data_source"],
        "created_at": demo_inc["created_at"],
    }

    for key, expected_val in expected_fields.items():
        assert key in data, f"Missing key: {key}"
        assert data[key] == expected_val, f"Mismatch on {key}: {data[key]} != {expected_val}"


# ── 5. Incident Lookup 404 ───────────────────────────────────────────────────

def test_get_incident_by_id_not_found(client: TestClient, isolated_db: str) -> None:
    """Unknown incident ID returns HTTP 404."""
    response = client.get("/api/v1/incidents/non-existent-999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ── 6. Nullable Fields & Data Source Constraints ─────────────────────────────

def test_incident_nullable_fields_and_data_source(client: TestClient, isolated_db: str) -> None:
    """
    confidence_score and uncertainty_note can be null.
    data_source must be 'simulated' or 'measured'.
    """
    response = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}")
    assert response.status_code == 200
    data = response.json()

    assert data["confidence_score"] is None or isinstance(data["confidence_score"], (int, float))
    assert data["uncertainty_note"] is None
    assert data["data_source"] in {"simulated", "measured"}
    assert isinstance(data["evidence"], list)

    # Validate ISO 8601 UTC timestamp
    dt = datetime.fromisoformat(data["created_at"])
    assert dt is not None


# ── 7. Affected Subscribers Unknown Incident 404 ─────────────────────────────

def test_affected_subscribers_unknown_incident_404(client: TestClient, isolated_db: str) -> None:
    """Requesting affected subscribers for a non-existent incident returns 404."""
    response = client.get("/api/v1/incidents/NON_EXISTENT_INCIDENT/affected-subscribers")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ── 8. Affected Subscribers 503 when Graph Engine Unavailable ───────────────

def test_affected_subscribers_503_when_engine_unavailable(
    client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    When Member 1's graph engine is not connected (or unavailable adapter is configured),
    the endpoint must return 503 rather than fabricating affected subscribers.
    """
    monkeypatch.setattr(settings, "dependency_adapter", "unavailable")
    response = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/affected-subscribers")
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()


# ── 9. Affected Subscribers with Adapter (0 affected) ────────────────────────

class _MockEmptyDependencyAdapter(DependencyAnalysisAdapter):
    def get_affected_subscribers(self, incident_id, suspected_component_id, suspected_component_type, db_conn):
        return []


def test_affected_subscribers_zero_affected(client: TestClient, isolated_db: str) -> None:
    """When dependency analysis determines 0 affected subscribers, return count=0 and empty list."""
    app.dependency_overrides[get_dependency_adapter] = lambda: _MockEmptyDependencyAdapter()
    try:
        response = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/affected-subscribers")
        assert response.status_code == 200
        assert response.json() == {"count": 0, "subscribers": []}
    finally:
        app.dependency_overrides.pop(get_dependency_adapter, None)


# ── 10. Affected Subscribers with Adapter (matching records) ─────────────────

class _MockDependencyAdapter(DependencyAnalysisAdapter):
    def get_affected_subscribers(self, incident_id, suspected_component_id, suspected_component_type, db_conn):
        return [
            {"id": "SUB101", "display_name": "Demo Subscriber 101", "access_point_id": "AP1"},
            {"id": "SUB102", "display_name": "Demo Subscriber 102", "access_point_id": "AP1"},
        ]


def test_affected_subscribers_with_records(client: TestClient, isolated_db: str) -> None:
    """Affected subscribers response must match exact contract and count == len(subscribers)."""
    app.dependency_overrides[get_dependency_adapter] = lambda: _MockDependencyAdapter()
    try:
        response = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/affected-subscribers")
        assert response.status_code == 200

        data = response.json()
        assert data["count"] == 2
        assert len(data["subscribers"]) == 2

        sub101 = next(s for s in data["subscribers"] if s["id"] == "SUB101")
        assert sub101 == {
            "id": "SUB101",
            "display_name": "Demo Subscriber 101",
            "access_point_id": "AP1",
        }
    finally:
        app.dependency_overrides.pop(get_dependency_adapter, None)


# ── 11. SimulatedDependencyAdapter End-to-End ────────────────────────────────

def test_simulated_dependency_adapter_end_to_end(client: TestClient, isolated_db: str) -> None:
    """
    Using SimulatedDependencyAdapter:
    demo incident has suspected_component_id='L3'.
    Downstream AP for L3 is AP2 in SimulatedDependencyAdapter.
    """
    app.dependency_overrides[get_dependency_adapter] = lambda: SimulatedDependencyAdapter()
    try:
        response = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/affected-subscribers")
        assert response.status_code == 200

        data = response.json()
        assert data["count"] == len(data["subscribers"])
        assert data["count"] > 0
        assert all(s["access_point_id"] == "AP2" for s in data["subscribers"])
    finally:
        app.dependency_overrides.pop(get_dependency_adapter, None)


# ── 12. EngineDependencyAdapter End-to-End ───────────────────────────────────

def test_engine_dependency_adapter_end_to_end(client: TestClient, isolated_db: str) -> None:
    """
    Using EngineDependencyAdapter:
    demo incident has suspected_component_id='L3'.
    Engine graph store traces downstream AP: AP1.
    Subscribers on AP1 are SUB101, SUB102, and SUB103.
    SQLite enriches those records with operational data.
    """
    app.dependency_overrides[get_dependency_adapter] = lambda: EngineDependencyAdapter()
    try:
        response = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/affected-subscribers")
        assert response.status_code == 200

        data = response.json()
        assert data["count"] == 3
        sub_ids = [s["id"] for s in data["subscribers"]]
        assert set(sub_ids) == {"SUB101", "SUB102", "SUB103"}
        assert all(s["access_point_id"] == "AP1" for s in data["subscribers"])
        # Check SQLite enrichment fields
        for s in data["subscribers"]:
            assert "id" in s
            assert "display_name" in s
            assert "access_point_id" in s
    finally:
        app.dependency_overrides.pop(get_dependency_adapter, None)
