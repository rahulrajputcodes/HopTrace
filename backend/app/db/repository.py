"""
Data access repository for subscribers, payment reminders, incidents, and test runs.
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
        SELECT id, display_name, plan, plan_price, access_point_id, status, payment_status, due_date, phone, preferred_language
        FROM subscribers
        ORDER BY id ASC;
        """
    )
    return [dict(row) for row in cursor.fetchall()]


def get_subscriber(conn: sqlite3.Connection, subscriber_id: str) -> dict[str, Any] | None:
    """Fetch a single subscriber by ID, or None if not found."""
    cursor = conn.execute(
        """
        SELECT id, display_name, plan, plan_price, access_point_id, status, payment_status, due_date, phone, preferred_language
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
        SELECT id, display_name, plan, plan_price, access_point_id, status, payment_status, due_date, phone, preferred_language
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
        SELECT id, display_name, plan, plan_price, access_point_id, status, payment_status, due_date, phone, preferred_language
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


# ── Run and Measurement Queries ──────────────────────────────────────────────

def save_run(
    conn: sqlite3.Connection,
    run_id: str,
    data_source: str,
    measurements: list[Any],
    created_at: str | None = None,
    retention_limit: int | None = None,
) -> None:
    """
    Persist a test run and its component measurements into SQLite.
    Prunes older runs beyond `retention_limit` if configured.
    """
    now_iso = created_at or datetime.now(timezone.utc).isoformat()

    conn.execute(
        """
        INSERT INTO runs (run_id, data_source, created_at)
        VALUES (?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
            data_source = excluded.data_source,
            created_at = excluded.created_at;
        """,
        (run_id, data_source, now_iso),
    )

    # Replace existing measurements for idempotency
    conn.execute("DELETE FROM measurements WHERE run_id = ?;", (run_id,))

    rows = []
    for m in measurements:
        if hasattr(m, "component_id"):
            comp_id = m.component_id
            ts = getattr(m, "timestamp_utc", None) or getattr(m, "timestamp", None) or now_iso
            lat = m.latency_ms
            loss = m.packet_loss_pct
            tp = m.throughput_mbps
            conn_ok = 1 if m.connectivity_ok else 0
            ds = getattr(m, "data_source", data_source)
        elif isinstance(m, dict):
            comp_id = m["component_id"]
            ts = m.get("timestamp_utc") or m.get("timestamp") or now_iso
            lat = m.get("latency_ms")
            loss = m.get("packet_loss_pct")
            tp = m.get("throughput_mbps")
            conn_ok = 1 if m.get("connectivity_ok", True) else 0
            ds = m.get("data_source", data_source)
        else:
            continue
        rows.append((run_id, comp_id, ts, lat, loss, tp, conn_ok, ds))

    if rows:
        conn.executemany(
            """
            INSERT INTO measurements (
                run_id, component_id, timestamp_utc, latency_ms, packet_loss_pct,
                throughput_mbps, connectivity_ok, data_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            rows,
        )

    if retention_limit is not None and retention_limit > 0:
        prune_runs(conn, retention_limit)

    conn.commit()


def get_run(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    """Fetch run metadata and measurements list by run_id, or None if not found."""
    cursor = conn.execute(
        """
        SELECT run_id, data_source, created_at
        FROM runs
        WHERE run_id = ?;
        """,
        (run_id,),
    )
    row = cursor.fetchone()
    if row is None:
        return None

    meas_cursor = conn.execute(
        """
        SELECT component_id, timestamp_utc, latency_ms, packet_loss_pct,
               throughput_mbps, connectivity_ok, data_source
        FROM measurements
        WHERE run_id = ?
        ORDER BY id ASC;
        """,
        (run_id,),
    )
    measurements = [
        {
            "component_id": r["component_id"],
            "timestamp_utc": r["timestamp_utc"],
            "latency_ms": r["latency_ms"],
            "packet_loss_pct": r["packet_loss_pct"],
            "throughput_mbps": r["throughput_mbps"],
            "connectivity_ok": bool(r["connectivity_ok"]),
            "data_source": r["data_source"],
        }
        for r in meas_cursor.fetchall()
    ]

    return {
        "run_id": row["run_id"],
        "data_source": row["data_source"],
        "created_at": row["created_at"],
        "measurements": measurements,
    }


def prune_runs(conn: sqlite3.Connection, retention_limit: int) -> int:
    """Retains the most recent `retention_limit` runs, deleting older runs and measurements."""
    if retention_limit <= 0:
        return 0

    cursor = conn.execute(
        """
        DELETE FROM runs
        WHERE run_id NOT IN (
            SELECT run_id FROM runs
            ORDER BY created_at DESC, rowid DESC
            LIMIT ?
        );
        """,
        (retention_limit,),
    )
    deleted = cursor.rowcount
    conn.execute(
        """
        DELETE FROM measurements
        WHERE run_id NOT IN (SELECT run_id FROM runs);
        """
    )
    conn.commit()
    return deleted


def count_runs(conn: sqlite3.Connection) -> int:
    """Returns the total number of persisted runs in SQLite."""
    cursor = conn.execute("SELECT COUNT(*) FROM runs;")
    return cursor.fetchone()[0]


def list_runs(conn: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    """Fetch recent runs without measurements, ordered by newest first."""
    cursor = conn.execute(
        """
        SELECT run_id, data_source, created_at
        FROM runs
        ORDER BY created_at DESC, rowid DESC
        LIMIT ?;
        """,
        (limit,),
    )
    return [dict(row) for row in cursor.fetchall()]
