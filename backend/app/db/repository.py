"""
Data access repository for subscribers, payment reminders, and incidents.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any


# ── Subscriber Queries ───────────────────────────────────────────────────────

def list_subscribers(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Fetch all subscribers ordered by ID."""
    cursor = conn.execute(
        """
        SELECT id, display_name, plan, access_point_id, status, payment_status, due_date
        FROM subscribers
        ORDER BY id ASC;
        """
    )
    return [dict(row) for row in cursor.fetchall()]


def get_subscriber(conn: sqlite3.Connection, subscriber_id: str) -> dict[str, Any] | None:
    """Fetch a single subscriber by ID, or None if not found."""
    cursor = conn.execute(
        """
        SELECT id, display_name, plan, access_point_id, status, payment_status, due_date
        FROM subscribers
        WHERE id = ?;
        """,
        (subscriber_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row is not None else None


def get_subscribers_by_access_points(
    conn: sqlite3.Connection,
    access_point_ids: list[str],
) -> list[dict[str, Any]]:
    """Fetch subscribers connected to specific access points (for affected subscriber analysis)."""
    if not access_point_ids:
        return []
    placeholders = ",".join("?" for _ in access_point_ids)
    cursor = conn.execute(
        f"""
        SELECT id, display_name, access_point_id
        FROM subscribers
        WHERE access_point_id IN ({placeholders})
        ORDER BY id ASC;
        """,
        access_point_ids,
    )
    return [dict(row) for row in cursor.fetchall()]


def get_subscribers_by_ids(
    conn: sqlite3.Connection,
    subscriber_ids: list[str],
) -> list[dict[str, Any]]:
    """Fetch operational subscriber details for specific subscriber IDs."""
    if not subscriber_ids:
        return []
    placeholders = ",".join("?" for _ in subscriber_ids)
    cursor = conn.execute(
        f"""
        SELECT id, display_name, access_point_id
        FROM subscribers
        WHERE id IN ({placeholders})
        ORDER BY id ASC;
        """,
        subscriber_ids,
    )
    return [dict(row) for row in cursor.fetchall()]


# ── Payment Reminder Queries ─────────────────────────────────────────────────

def record_payment_reminder(
    conn: sqlite3.Connection,
    subscriber_id: str,
    language: str,
) -> dict[str, str]:
    """
    Insert a payment reminder history record and commit transaction.

    Returns the documented reminder response payload.
    Raises sqlite3.Error on failure to ensure false success is never reported.
    """
    reminder_id = f"rem-{uuid.uuid4().hex[:12]}"
    now_utc = datetime.now(timezone.utc).isoformat()
    status = "recorded"
    delivery_status = "not_sent"

    conn.execute(
        """
        INSERT INTO payment_reminders (
            id, subscriber_id, language, created_at, status, delivery_status
        ) VALUES (?, ?, ?, ?, ?, ?);
        """,
        (reminder_id, subscriber_id, language, now_utc, status, delivery_status),
    )
    conn.commit()

    return {
        "subscriber_id": subscriber_id,
        "status": status,
        "delivery_status": delivery_status,
    }


def get_reminders_for_subscriber(
    conn: sqlite3.Connection,
    subscriber_id: str,
) -> list[dict[str, Any]]:
    """Internal helper to retrieve reminder history for verification."""
    cursor = conn.execute(
        """
        SELECT id, subscriber_id, language, created_at, status, delivery_status
        FROM payment_reminders
        WHERE subscriber_id = ?
        ORDER BY created_at ASC;
        """,
        (subscriber_id,),
    )
    return [dict(row) for row in cursor.fetchall()]


# ── Incident Queries ─────────────────────────────────────────────────────────

def _row_to_incident(row: sqlite3.Row) -> dict[str, Any]:
    """Convert SQLite row to Incident dictionary with parsed JSON evidence."""
    data = dict(row)
    evidence_raw = data.get("evidence")
    if evidence_raw:
        try:
            data["evidence"] = json.loads(evidence_raw)
        except (json.JSONDecodeError, TypeError):
            data["evidence"] = []
    else:
        data["evidence"] = []
    return data


def get_latest_incident(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Fetch the most recent diagnostic incident, or None if no incident exists."""
    cursor = conn.execute(
        """
        SELECT id, run_id, status, suspected_component_id, suspected_component_type,
               summary, confidence_score, evidence, uncertainty_note, data_source, created_at
        FROM incidents
        ORDER BY created_at DESC, id DESC
        LIMIT 1;
        """
    )
    row = cursor.fetchone()
    return _row_to_incident(row) if row is not None else None


def get_latest_open_incident(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Fetch the most recent open diagnostic incident (status != 'closed'), or None."""
    cursor = conn.execute(
        """
        SELECT id, run_id, status, suspected_component_id, suspected_component_type,
               summary, confidence_score, evidence, uncertainty_note, data_source, created_at
        FROM incidents
        WHERE status != 'closed'
        ORDER BY created_at DESC, id DESC
        LIMIT 1;
        """
    )
    row = cursor.fetchone()
    return _row_to_incident(row) if row is not None else None


def get_incident(conn: sqlite3.Connection, incident_id: str) -> dict[str, Any] | None:
    """Fetch a single incident by ID, or None if not found."""
    cursor = conn.execute(
        """
        SELECT id, run_id, status, suspected_component_id, suspected_component_type,
               summary, confidence_score, evidence, uncertainty_note, data_source, created_at
        FROM incidents
        WHERE id = ?;
        """,
        (incident_id,),
    )
    row = cursor.fetchone()
    return _row_to_incident(row) if row is not None else None


def create_incident(conn: sqlite3.Connection, incident_data: dict[str, Any]) -> dict[str, Any]:
    """
    Insert a new diagnostic incident into SQLite and commit transaction.

    Used by test fixtures and future lab runners.
    """
    evidence = incident_data.get("evidence", [])
    evidence_json = json.dumps(evidence) if not isinstance(evidence, str) else evidence

    conn.execute(
        """
        INSERT INTO incidents (
            id, run_id, status, suspected_component_id, suspected_component_type,
            summary, confidence_score, evidence, uncertainty_note, data_source, created_at
        ) VALUES (
            :id, :run_id, :status, :suspected_component_id, :suspected_component_type,
            :summary, :confidence_score, :evidence, :uncertainty_note, :data_source, :created_at
        );
        """,
        {
            "id": incident_data["id"],
            "run_id": incident_data.get("run_id"),
            "status": incident_data.get("status", "open"),
            "suspected_component_id": incident_data.get("suspected_component_id"),
            "suspected_component_type": incident_data.get("suspected_component_type"),
            "summary": incident_data["summary"],
            "confidence_score": incident_data.get("confidence_score"),
            "evidence": evidence_json,
            "uncertainty_note": incident_data.get("uncertainty_note"),
            "data_source": incident_data.get("data_source", "simulated"),
            "created_at": incident_data.get("created_at") or datetime.now(timezone.utc).isoformat(),
        },
    )
    conn.commit()
    return get_incident(conn, incident_data["id"])  # type: ignore[return-value]


def close_open_incidents(conn: sqlite3.Connection) -> None:
    """Mark all open incidents in SQLite as closed."""
    conn.execute(
        """
        UPDATE incidents
        SET status = 'closed'
        WHERE status = 'open';
        """
    )
    conn.commit()
