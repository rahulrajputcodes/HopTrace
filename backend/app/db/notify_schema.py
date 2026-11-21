"""
SQLite schema definitions and initialization for notifications (M3).

Tables:
- notification_batches: Tracks notification dispatch batches per incident.
- notification_deliveries: Tracks per-subscriber notification attempts and statuses.

Ensures idempotent creation and proper indexes.
"""
from __future__ import annotations

import sqlite3

NOTIFY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS notification_batches (
    id TEXT PRIMARY KEY,
    incident_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    channel TEXT NOT NULL,
    provider TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    created_by TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (incident_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS notification_deliveries (
    id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES notification_batches(id) ON DELETE CASCADE,
    subscriber_id TEXT NOT NULL,
    language TEXT NOT NULL,
    message TEXT NOT NULL,
    message_source TEXT NOT NULL,
    status TEXT NOT NULL,
    message_id TEXT,
    error TEXT,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_notif_batches_incident ON notification_batches (incident_id);
CREATE INDEX IF NOT EXISTS idx_notif_batches_idempotency ON notification_batches (incident_id, idempotency_key);
CREATE INDEX IF NOT EXISTS idx_notif_deliveries_batch ON notification_deliveries (batch_id);
CREATE INDEX IF NOT EXISTS idx_notif_deliveries_subscriber ON notification_deliveries (subscriber_id);
"""


def ensure_notify_tables(conn: sqlite3.Connection) -> None:
    """
    Ensure notification tables exist in SQLite idempotently.
    Safe to call repeatedly across restarts and tests.
    """
    conn.executescript(NOTIFY_SCHEMA_SQL)
    conn.commit()
