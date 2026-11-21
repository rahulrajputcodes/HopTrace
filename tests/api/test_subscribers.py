"""
Automated tests for Subscriber and Payment Reminder operations (Milestone 2).

Tests:
1. Database initialization and table creation.
2. Subscriber persistence across separate database connections.
3. Subscriber listing with records.
4. Subscriber listing with an empty database.
5. Exact response field names and types according to docs/api-contract.md.
6. Successful payment reminder recording.
7. Persistence of reminder history in SQLite.
8. Unknown subscriber returns 404.
9. Invalid request body and unsupported language validation.
10. Repeated operations idempotency (no duplicate subscribers, multiple reminders succeed).
11. SQLite foreign key enforcement.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any
import pytest
from fastapi.testclient import TestClient

from app.db.connection import get_db_connection
from app.db.init import DEMO_SUBSCRIBERS, init_db
from app.db.repository import get_reminders_for_subscriber


# ── 1. Database Initialization ───────────────────────────────────────────────

def test_database_initialization(tmp_path) -> None:
    """init_db must create both 'subscribers' and 'payment_reminders' tables."""
    db_file = str(tmp_path / "init_check.db")
    init_db(db_file, seed_demo=False)

    conn = get_db_connection(db_file)
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        )
        tables = {row["name"] for row in cursor.fetchall()}
        assert "subscribers" in tables
        assert "payment_reminders" in tables
    finally:
        conn.close()


# ── 2. Persistence Across Connections ────────────────────────────────────────

def test_subscriber_persistence_across_connections(tmp_path) -> None:
    """Records committed on connection 1 must persist and be readable on connection 2."""
    db_file = str(tmp_path / "persist_check.db")
    init_db(db_file, seed_demo=False)

    # Insert on connection 1
    conn1 = get_db_connection(db_file)
    try:
        conn1.execute(
            """
            INSERT INTO subscribers (id, display_name, plan, access_point_id, status, payment_status, due_date)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            ("SUB999", "Persistent User", "Pro", "AP1", "active", "paid", "2026-12-01"),
        )
        conn1.commit()
    finally:
        conn1.close()

    # Read on connection 2
    conn2 = get_db_connection(db_file)
    try:
        cursor = conn2.execute("SELECT * FROM subscribers WHERE id = ?;", ("SUB999",))
        row = cursor.fetchone()
        assert row is not None
        assert row["id"] == "SUB999"
        assert row["display_name"] == "Persistent User"
        assert row["plan"] == "Pro"
        assert row["access_point_id"] == "AP1"
        assert row["status"] == "active"
        assert row["payment_status"] == "paid"
        assert row["due_date"] == "2026-12-01"
    finally:
        conn2.close()


# ── 3. Subscriber Listing with Records ───────────────────────────────────────

def test_get_subscribers_with_records(client: TestClient, isolated_db: str) -> None:
    """GET /api/v1/subscribers returns 200 and list of seeded demo subscribers."""
    response = client.get("/api/v1/subscribers")
    assert response.status_code == 200

    data = response.json()
    assert "subscribers" in data
    assert isinstance(data["subscribers"], list)
    assert len(data["subscribers"]) == len(DEMO_SUBSCRIBERS)

    # Check that SUB101 is present with expected demo values
    sub_map = {s["id"]: s for s in data["subscribers"]}
    assert "SUB101" in sub_map
    sub101 = sub_map["SUB101"]
    demo_sub101 = next(s for s in DEMO_SUBSCRIBERS if s["id"] == "SUB101")
    assert sub101["display_name"] == demo_sub101["display_name"]
    assert sub101["plan"] == demo_sub101["plan"]
    assert sub101["access_point_id"] == demo_sub101["access_point_id"]
    assert sub101["status"] == demo_sub101["status"]
    assert sub101["payment_status"] == demo_sub101["payment_status"]
    assert sub101["due_date"] == demo_sub101["due_date"]


# ── 4. Subscriber Listing with Empty Database ────────────────────────────────

def test_get_subscribers_empty_database(client: TestClient, empty_db: str) -> None:
    """GET /api/v1/subscribers returns 200 and an empty list when no subscribers exist."""
    response = client.get("/api/v1/subscribers")
    assert response.status_code == 200
    assert response.json() == {"subscribers": []}


# ── 5. Exact Response Field Names and Types ──────────────────────────────────

def test_subscriber_field_names_and_types(client: TestClient, isolated_db: str) -> None:
    """Every subscriber record must strictly conform to documented fields and string types."""
    expected_fields = {
        "id": str,
        "display_name": str,
        "plan": str,
        "plan_price": (int, float),
        "access_point_id": str,
        "status": str,
        "payment_status": str,
        "due_date": str,
        "phone": (str, type(None)),
        "preferred_language": (str, type(None)),
    }

    response = client.get("/api/v1/subscribers")
    assert response.status_code == 200
    subscribers = response.json()["subscribers"]
    assert len(subscribers) > 0

    for item in subscribers:
        assert set(item.keys()) == set(expected_fields.keys()), (
            f"Field mismatch in item: {item.keys()} vs expected {expected_fields.keys()}"
        )
        for field, expected_type in expected_fields.items():
            assert isinstance(item[field], expected_type), (
                f"Field '{field}' expected {expected_type}, got {type(item[field])}"
            )


# ── 6. Successful Payment Reminder Recording ─────────────────────────────────

def test_record_payment_reminder_success(client: TestClient, isolated_db: str) -> None:
    """POST /api/v1/subscribers/{subscriber_id}/remind records reminder and returns exact contract."""
    response = client.post(
        "/api/v1/subscribers/SUB101/remind",
        json={"language": "hi"},
    )
    assert response.status_code == 200
    expected = {
        "subscriber_id": "SUB101",
        "status": "recorded",
        "delivery_status": "not_sent",
    }
    assert response.json() == expected


# ── 7. Persistence of Reminder History ───────────────────────────────────────

def test_reminder_history_persisted_in_db(client: TestClient, isolated_db: str) -> None:
    """Recording a reminder must create an entry in the payment_reminders SQLite table."""
    post_resp = client.post(
        "/api/v1/subscribers/SUB101/remind",
        json={"language": "hi"},
    )
    assert post_resp.status_code == 200

    conn = get_db_connection(isolated_db)
    try:
        reminders = get_reminders_for_subscriber(conn, "SUB101")
        assert len(reminders) >= 1
        rem = reminders[-1]
        assert rem["subscriber_id"] == "SUB101"
        assert rem["language"] == "hi"
        assert rem["status"] == "recorded"
        assert rem["delivery_status"] == "not_sent"
        assert rem["id"].startswith("rem-")

        # Verify timestamp is valid ISO 8601 UTC
        created_at_dt = datetime.fromisoformat(rem["created_at"])
        assert created_at_dt is not None
    finally:
        conn.close()


# ── 8. Unknown Subscriber Returns 404 ────────────────────────────────────────

def test_record_reminder_unknown_subscriber_returns_404(
    client: TestClient, isolated_db: str
) -> None:
    """Unknown subscriber ID must return 404 and record no reminder."""
    response = client.post(
        "/api/v1/subscribers/NON_EXISTENT_SUB/remind",
        json={"language": "hi"},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

    # Verify no orphan reminder was stored
    conn = get_db_connection(isolated_db)
    try:
        cursor = conn.execute(
            "SELECT COUNT(*) as cnt FROM payment_reminders WHERE subscriber_id = ?;",
            ("NON_EXISTENT_SUB",),
        )
        assert cursor.fetchone()["cnt"] == 0
    finally:
        conn.close()


# ── 9. Invalid Request Body and Unsupported Language ─────────────────────────

def test_record_reminder_unsupported_language_returns_422(
    client: TestClient, isolated_db: str
) -> None:
    """Languages outside documented policy ('hi', 'en') must return 422 Unprocessable Entity."""
    response = client.post(
        "/api/v1/subscribers/SUB101/remind",
        json={"language": "french"},
    )
    assert response.status_code == 422


def test_record_reminder_empty_body_returns_422(
    client: TestClient, isolated_db: str
) -> None:
    """Empty JSON body missing required 'language' field must return 422."""
    response = client.post(
        "/api/v1/subscribers/SUB101/remind",
        json={},
    )
    assert response.status_code == 422


def test_record_reminder_invalid_type_returns_422(
    client: TestClient, isolated_db: str
) -> None:
    """Non-string language value must return 422."""
    response = client.post(
        "/api/v1/subscribers/SUB101/remind",
        json={"language": 12345},
    )
    assert response.status_code == 422


# ── 10. Repeated Requests & Idempotency ──────────────────────────────────────

def test_repeated_init_db_does_not_duplicate_subscribers(tmp_path) -> None:
    """Calling init_db multiple times must preserve existing records without duplicates."""
    db_file = str(tmp_path / "idempotent.db")
    init_db(db_file, seed_demo=True)
    init_db(db_file, seed_demo=True)
    init_db(db_file, seed_demo=True)

    conn = get_db_connection(db_file)
    try:
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM subscribers;")
        assert cursor.fetchone()["cnt"] == len(DEMO_SUBSCRIBERS)
    finally:
        conn.close()


def test_multiple_reminders_for_same_subscriber(
    client: TestClient, isolated_db: str
) -> None:
    """Multiple reminders for the same subscriber can be recorded without collision."""
    r1 = client.post("/api/v1/subscribers/SUB101/remind", json={"language": "hi"})
    r2 = client.post("/api/v1/subscribers/SUB101/remind", json={"language": "en"})

    assert r1.status_code == 200
    assert r2.status_code == 200

    conn = get_db_connection(isolated_db)
    try:
        reminders = get_reminders_for_subscriber(conn, "SUB101")
        assert len(reminders) == 2
        assert {rem["language"] for rem in reminders} == {"hi", "en"}
    finally:
        conn.close()


# ── 11. Foreign Key Constraint Enforcement ───────────────────────────────────

def test_foreign_key_constraint_enforced(tmp_path) -> None:
    """Direct insertion of reminder with invalid subscriber ID must fail with IntegrityError."""
    db_file = str(tmp_path / "fk_check.db")
    init_db(db_file, seed_demo=False)

    conn = get_db_connection(db_file)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO payment_reminders (id, subscriber_id, language, created_at, status, delivery_status)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                ("rem-test", "NON_EXISTENT", "hi", "2026-10-30T00:00:00Z", "recorded", "not_sent"),
            )
            conn.commit()
    finally:
        conn.close()
