"""
Tests for GET /api/v1/public/villages

Coverage:
  1.  200 response with correct top-level shape (updated_at + villages list of 3)
  2.  Correct village IDs and display names
  3.  status values are within the allowed enum {up, degraded, down, no_data}
  4.  All villages return "no_data" when the time-series store is empty (cold start)
  5.  since is null for all villages when no open incidents exist
  6.  since is set for the affected village when an open incident exists for one of its links
  7.  lang=en (default) returns English-only messages (no Devanagari)
  8.  lang=hi returns Hindi messages (contains Devanagari)
  9.  Unknown lang falls back to English
  10. Endpoint returns 200 with NO Authorization header (truly public)
  11. Response body contains no PII (no subscriber IDs, phone numbers, incident internals)
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.db.connection import get_db, get_db_connection
from app.db.init import init_db
from app.db.repository import create_incident
from app.engine.time_series import TimeSeriesStore
from app.main import app

URL = "/api/v1/public/villages"
VALID_STATUSES = {"up", "degraded", "down", "no_data"}
EXPECTED_VILLAGES = {
    "rampur":    "Rampur",
    "bhatpur":   "Bhatpur",
    "daulatpur": "Daulatpur",
}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def empty_ts_store():
    """Patch public_status module to use a fresh, empty TimeSeriesStore."""
    fresh = TimeSeriesStore()
    with patch("app.api.public_status.get_time_series_store", return_value=fresh):
        yield fresh


@pytest.fixture
def healthy_ts_store():
    """TimeSeriesStore pre-populated with healthy telemetry for all 14 links."""
    from app.engine.models import Measurement

    store = TimeSeriesStore()
    for i in range(1, 15):
        link_id = f"L{i}"
        m = Measurement(
            component_id=link_id,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            latency_ms=10.0,
            packet_loss_pct=0.0,
            throughput_mbps=50.0,
            connectivity_ok=True,
        )
        store.push(link_id, m)

    with patch("app.api.public_status.get_time_series_store", return_value=store):
        yield store


# ── Test 1: 200 shape ─────────────────────────────────────────────────────────

def test_200_shape(client, healthy_ts_store, isolated_db):
    resp = client.get(URL)
    assert resp.status_code == 200
    body = resp.json()
    assert "updated_at" in body, "Missing 'updated_at' in response"
    assert "villages" in body, "Missing 'villages' in response"
    assert isinstance(body["villages"], list)
    assert len(body["villages"]) == 3, f"Expected 3 villages, got {len(body['villages'])}"


# ── Test 2: Village IDs and names ─────────────────────────────────────────────

def test_village_ids_and_names(client, healthy_ts_store, isolated_db):
    resp = client.get(URL)
    assert resp.status_code == 200
    returned = {v["id"]: v["name"] for v in resp.json()["villages"]}
    assert returned == EXPECTED_VILLAGES


# ── Test 3: Status enum values ────────────────────────────────────────────────

def test_status_enum_values(client, healthy_ts_store, isolated_db):
    resp = client.get(URL)
    assert resp.status_code == 200
    for v in resp.json()["villages"]:
        assert v["status"] in VALID_STATUSES, (
            f"Village '{v['id']}' has invalid status '{v['status']}'"
        )


# ── Test 4: no_data when store is empty (cold start) ──────────────────────────

def test_no_data_when_store_empty(client, empty_ts_store, isolated_db):
    """Every village must report 'no_data' when the ts store has no telemetry."""
    resp = client.get(URL)
    assert resp.status_code == 200
    for v in resp.json()["villages"]:
        assert v["status"] == "no_data", (
            f"Expected 'no_data' for '{v['id']}', got '{v['status']}'"
        )


# ── Test 5: since is null when no open incidents ──────────────────────────────

def test_since_null_when_no_incident(client, healthy_ts_store, empty_db):
    """With no open incidents, since must be null for every village."""
    resp = client.get(URL)
    assert resp.status_code == 200
    for v in resp.json()["villages"]:
        assert v["since"] is None, (
            f"Expected since=null for '{v['id']}', got '{v['since']}'"
        )


# ── Test 6: since is populated from the earliest open incident ────────────────

def test_since_set_when_open_incident(client, healthy_ts_store, tmp_path):
    """An open incident on a Rampur link must set since for Rampur only."""
    db_file = str(tmp_path / "since_test.db")
    init_db(db_file, seed_demo=False)

    incident_ts = "2026-11-21T10:00:00+00:00"
    conn = get_db_connection(db_file)
    create_incident(conn, {
        "id": "test-public-inc-001",
        "run_id": "run-001",
        "status": "open",
        "suspected_component_id": "L3",   # Rampur link
        "suspected_component_type": "link",
        "summary": "Test degradation on Rampur L3",
        "confidence_score": 0.9,
        "data_source": "simulated",
        "created_at": incident_ts,
    })
    conn.close()

    def _override():
        c = get_db_connection(db_file)
        try:
            yield c
        finally:
            c.close()

    app.dependency_overrides[get_db] = _override
    try:
        resp = client.get(URL)
        assert resp.status_code == 200
        by_id = {v["id"]: v for v in resp.json()["villages"]}
        assert by_id["rampur"]["since"] == incident_ts, (
            f"Expected since='{incident_ts}' for rampur, got '{by_id['rampur']['since']}'"
        )
        assert by_id["bhatpur"]["since"] is None, (
            f"Bhatpur should have since=null, got '{by_id['bhatpur']['since']}'"
        )
        assert by_id["daulatpur"]["since"] is None, (
            f"Daulatpur should have since=null, got '{by_id['daulatpur']['since']}'"
        )
    finally:
        app.dependency_overrides.pop(get_db, None)


# ── Test 7: lang=en (default) returns English messages ───────────────────────

def test_lang_en_default(client, healthy_ts_store, isolated_db):
    """Default lang (no query param) must return English — no Devanagari."""
    resp = client.get(URL)
    assert resp.status_code == 200
    for v in resp.json()["villages"]:
        assert not re.search(r"[\u0900-\u097F]", v["message"]), (
            f"Expected English message for '{v['id']}', got: '{v['message']}'"
        )


# ── Test 8: lang=hi returns Hindi messages ────────────────────────────────────

def test_lang_hi(client, healthy_ts_store, isolated_db):
    """lang=hi must return Devanagari messages for every village."""
    resp = client.get(URL + "?lang=hi")
    assert resp.status_code == 200
    for v in resp.json()["villages"]:
        assert re.search(r"[\u0900-\u097F]", v["message"]), (
            f"Expected Hindi (Devanagari) message for '{v['id']}', got: '{v['message']}'"
        )


# ── Test 9: Unknown lang falls back to English ────────────────────────────────

def test_lang_unknown_falls_back_to_en(client, healthy_ts_store, isolated_db):
    """Unknown lang value must silently fall back to English (no 400, no Devanagari)."""
    resp = client.get(URL + "?lang=klingon")
    assert resp.status_code == 200
    for v in resp.json()["villages"]:
        assert not re.search(r"[\u0900-\u097F]", v["message"]), (
            f"Expected English fallback for '{v['id']}', got: '{v['message']}'"
        )


# ── Test 10: No authentication required ───────────────────────────────────────

def test_no_auth_required(healthy_ts_store, isolated_db):
    """Public endpoint must return 200 with absolutely no Authorization header."""
    bare_client = TestClient(app, headers={})   # explicit empty headers — no auth
    resp = bare_client.get(URL)
    assert resp.status_code == 200, (
        f"Expected 200 without auth header, got {resp.status_code}: {resp.text}"
    )


# ── Test 11: No PII in response body ─────────────────────────────────────────

def test_no_pii_in_response(client, healthy_ts_store, isolated_db):
    """Response body must be free of subscriber IDs, phone numbers, and incident internals."""
    resp = client.get(URL)
    assert resp.status_code == 200
    body_text = resp.text

    # Subscriber ID pattern (SUB followed by digits)
    assert not re.search(r"\bSUB\d+\b", body_text), "Subscriber ID leaked in response"

    # Phone number pattern (+91 followed by digits)
    assert not re.search(r"\+91\d+", body_text), "Phone number leaked in response"

    # Incident diagnostic fields that must never appear on a public endpoint
    for forbidden_key in (
        "confidence_score",
        "suspected_component_id",
        '"evidence"',
        '"run_id"',
        "uncertainty_note",
    ):
        assert forbidden_key not in body_text, (
            f"Forbidden field '{forbidden_key}' leaked in public response"
        )
