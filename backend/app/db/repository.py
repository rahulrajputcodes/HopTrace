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
    extras_raw = data.get("extras_json")
    if extras_raw:
        try:
            extras = json.loads(extras_raw)
            data["cause"] = extras.get("cause")
            data["cause_confidence"] = extras.get("cause_confidence")
            data["cause_reasoning"] = extras.get("cause_reasoning", [])
            data["hop_trace"] = extras.get("hop_trace", [])
        except (json.JSONDecodeError, TypeError):
            data["cause"] = None
            data["cause_confidence"] = None
            data["cause_reasoning"] = []
            data["hop_trace"] = []
    else:
        data.setdefault("cause", None)
        data.setdefault("cause_confidence", None)
        data.setdefault("cause_reasoning", [])
        data.setdefault("hop_trace", [])
    data.setdefault("resolved_at", data.get("resolved_at"))
    data.setdefault("duration_seconds", data.get("duration_seconds"))
    return data


def get_latest_incident(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """Fetch the most recent diagnostic incident, or None if no incident exists."""
    cursor = conn.execute(
        """
        SELECT id, run_id, status, suspected_component_id, suspected_component_type,
               summary, confidence_score, evidence, uncertainty_note, data_source, created_at, extras_json,
               resolved_at, duration_seconds
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
               summary, confidence_score, evidence, uncertainty_note, data_source, created_at, extras_json,
               resolved_at, duration_seconds
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
               summary, confidence_score, evidence, uncertainty_note, data_source, created_at, extras_json,
               resolved_at, duration_seconds
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

    extras = incident_data.get("extras_json")
    if extras is None:
        hop_trace_val = incident_data.get("hop_trace", [])
        hop_trace_serializable = [
            h.model_dump() if hasattr(h, "model_dump") else (h.dict() if hasattr(h, "dict") else h)
            for h in (hop_trace_val or [])
        ]
        extras = {
            "cause": incident_data.get("cause"),
            "cause_confidence": incident_data.get("cause_confidence"),
            "cause_reasoning": incident_data.get("cause_reasoning", []),
            "hop_trace": hop_trace_serializable,
        }
    extras_json = json.dumps(extras) if not isinstance(extras, str) else extras

    conn.execute(
        """
        INSERT INTO incidents (
            id, run_id, status, suspected_component_id, suspected_component_type,
            summary, confidence_score, evidence, uncertainty_note, data_source, created_at, extras_json,
            resolved_at, duration_seconds
        ) VALUES (
            :id, :run_id, :status, :suspected_component_id, :suspected_component_type,
            :summary, :confidence_score, :evidence, :uncertainty_note, :data_source, :created_at, :extras_json,
            :resolved_at, :duration_seconds
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
            "extras_json": extras_json,
            "resolved_at": incident_data.get("resolved_at"),
            "duration_seconds": incident_data.get("duration_seconds"),
        },
    )
    conn.commit()
    return get_incident(conn, incident_data["id"])  # type: ignore[return-value]


def close_open_incidents(conn: sqlite3.Connection) -> None:
    """Mark all open incidents in SQLite as closed, recording resolved_at and duration_seconds."""
    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat()
    cursor = conn.execute("SELECT id, created_at FROM incidents WHERE status = 'open';")
    open_rows = cursor.fetchall()
    for row in open_rows:
        inc_id = row[0]
        created_str = row[1]
        duration = None
        if created_str:
            try:
                c_clean = str(created_str).replace("Z", "+00:00")
                c_dt = datetime.fromisoformat(c_clean)
                if c_dt.tzinfo is None:
                    c_dt = c_dt.replace(tzinfo=timezone.utc)
                duration = max(0, int((now_utc - c_dt).total_seconds()))
            except Exception:
                duration = None

        conn.execute(
            """
            UPDATE incidents
            SET status = 'closed',
                resolved_at = ?,
                duration_seconds = ?
            WHERE id = ?;
            """,
            (now_iso, duration, inc_id),
        )
    conn.commit()


VILLAGE_COMPONENT_MAP = {
    "rampur": ["L1", "L2", "L3", "L4", "L5", "R1", "WB1", "WB2", "AP1", "AP2"],
    "bhatpur": ["L6", "L7", "L8", "L9", "L10", "WB3", "WB4", "R2", "AP3", "AP4"],
    "daulatpur": ["L11", "L12", "L13", "L14", "WB5", "WB6", "AP5", "AP6"],
}

VILLAGE_META_INFO = {
    "rampur": {"name": "Rampur", "subscribers": 10},
    "bhatpur": {"name": "Bhatpur", "subscribers": 6},
    "daulatpur": {"name": "Daulatpur", "subscribers": 4},
}


def get_village_sla_stats(conn: sqlite3.Connection, window_hours: int = 24) -> dict[str, Any]:
    """Computes SLA availability percentages and outage duration per village over the window."""
    now_utc = datetime.now(timezone.utc)
    total_window_sec = max(1, window_hours * 3600)

    cursor = conn.execute(
        """
        SELECT id, suspected_component_id, status, created_at, resolved_at, duration_seconds
        FROM incidents;
        """
    )
    rows = cursor.fetchall()

    village_downtime: dict[str, float] = {"rampur": 0.0, "bhatpur": 0.0, "daulatpur": 0.0}
    village_incident_count: dict[str, int] = {"rampur": 0, "bhatpur": 0, "daulatpur": 0}
    village_active_count: dict[str, int] = {"rampur": 0, "bhatpur": 0, "daulatpur": 0}

    for row in rows:
        comp_id = row[1]
        status = row[2]
        created_str = row[3]
        duration = row[5]

        # Calculate outage duration
        if status == "open" and created_str:
            try:
                c_clean = str(created_str).replace("Z", "+00:00")
                c_dt = datetime.fromisoformat(c_clean)
                if c_dt.tzinfo is None:
                    c_dt = c_dt.replace(tzinfo=timezone.utc)
                dur_sec = max(0.0, (now_utc - c_dt).total_seconds())
            except Exception:
                dur_sec = 0.0
        else:
            dur_sec = float(duration or 0.0)

        # Cap at total window
        dur_sec = min(float(total_window_sec), dur_sec)

        # Map to affected villages (L1 backhaul affects all 3 villages)
        affected_villages = []
        if comp_id == "L1" or comp_id == "GW1":
            affected_villages = ["rampur", "bhatpur", "daulatpur"]
        else:
            for vid, components in VILLAGE_COMPONENT_MAP.items():
                if comp_id in components:
                    affected_villages.append(vid)

        for vid in affected_villages:
            village_downtime[vid] = min(float(total_window_sec), village_downtime[vid] + dur_sec)
            village_incident_count[vid] += 1
            if status == "open":
                village_active_count[vid] += 1

    villages_res = {}
    for vid, meta in VILLAGE_META_INFO.items():
        down_sec = village_downtime[vid]
        uptime_pct = round(100.0 * (total_window_sec - down_sec) / total_window_sec, 2)
        down_min = round(down_sec / 60.0, 1)
        active = village_active_count[vid]
        vstatus = "critical" if active > 0 else ("degraded" if uptime_pct < 99.0 else "healthy")
        villages_res[vid] = {
            "village_id": vid,
            "village_name": meta["name"],
            "uptime_pct": uptime_pct,
            "downtime_minutes": down_min,
            "total_incidents": village_incident_count[vid],
            "active_incidents": active,
            "status": vstatus,
        }

    return {
        "window_hours": window_hours,
        "timestamp_utc": now_utc.isoformat(),
        "villages": villages_res,
    }


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


# ── M3: Notification Persistence ─────────────────────────────────────────────

def get_notification_batch_by_idempotency(
    conn: sqlite3.Connection,
    incident_id: str,
    idempotency_key: str,
) -> dict[str, Any] | None:
    """Fetch an existing notification batch by incident ID and idempotency key."""
    cursor = conn.execute(
        """
        SELECT id, incident_id, kind, channel, provider, idempotency_key, created_by, created_at
        FROM notification_batches
        WHERE incident_id = ? AND idempotency_key = ?;
        """,
        (incident_id, idempotency_key),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    batch = dict(row)
    batch["deliveries"] = get_notification_deliveries(conn, batch["id"])
    return batch


def get_notification_deliveries(
    conn: sqlite3.Connection,
    batch_id: str,
) -> list[dict[str, Any]]:
    """Fetch all deliveries for a given batch."""
    cursor = conn.execute(
        """
        SELECT d.id, d.batch_id, d.subscriber_id, d.language, d.message, d.message_source,
               d.status, d.message_id, d.error, d.updated_at,
               b.channel, b.provider,
               s.display_name as subscriber_name, COALESCE(s.phone, '') as recipient
        FROM notification_deliveries d
        JOIN notification_batches b ON d.batch_id = b.id
        LEFT JOIN subscribers s ON d.subscriber_id = s.id
        WHERE d.batch_id = ?
        ORDER BY d.rowid ASC;
        """,
        (batch_id,),
    )
    rows = cursor.fetchall()
    return [dict(r) for r in rows]


def list_notification_batches_by_incident(
    conn: sqlite3.Connection,
    incident_id: str,
) -> list[dict[str, Any]]:
    """Fetch all batches for an incident, newest first, with deliveries."""
    cursor = conn.execute(
        """
        SELECT id, incident_id, kind, channel, provider, idempotency_key, created_by, created_at
        FROM notification_batches
        WHERE incident_id = ?
        ORDER BY created_at DESC, rowid DESC;
        """,
        (incident_id,),
    )
    rows = cursor.fetchall()
    batches = []
    for r in rows:
        batch = dict(r)
        batch["deliveries"] = get_notification_deliveries(conn, batch["id"])
        batches.append(batch)
    return batches


def create_notification_batch(
    conn: sqlite3.Connection,
    batch_data: dict[str, Any],
) -> None:
    """Insert a new notification batch."""
    conn.execute(
        """
        INSERT INTO notification_batches (
            id, incident_id, kind, channel, provider, idempotency_key, created_by, created_at
        ) VALUES (
            :id, :incident_id, :kind, :channel, :provider, :idempotency_key, :created_by, :created_at
        );
        """,
        batch_data,
    )


def create_notification_deliveries(
    conn: sqlite3.Connection,
    deliveries: list[dict[str, Any]],
) -> None:
    """Insert multiple notification delivery records."""
    if not deliveries:
        return
    conn.executemany(
        """
        INSERT INTO notification_deliveries (
            id, batch_id, subscriber_id, language, message, message_source, status, message_id, error, updated_at
        ) VALUES (
            :id, :batch_id, :subscriber_id, :language, :message, :message_source, :status, :message_id, :error, :updated_at
        );
        """,
        deliveries,
    )


def update_notification_delivery(
    conn: sqlite3.Connection,
    delivery_id: str,
    status: str,
    message_id: str | None,
    error: str | None,
    updated_at: str,
) -> None:
    """Update delivery status and attempt tracking."""
    conn.execute(
        """
        UPDATE notification_deliveries
        SET status = ?, message_id = ?, error = ?, updated_at = ?
        WHERE id = ?;
        """,
        (status, message_id, error, updated_at, delivery_id),
    )
