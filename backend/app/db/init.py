"""
Database initialization and demo data seeding — HopTrace v2.

v2: 20 subscribers across 3 villages (AP1–AP6), demo incident and persisted runs/measurements.
"""
from __future__ import annotations

import sqlite3
from typing import Any

from app.db.connection import get_db_connection

# ── DDL ──────────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS subscribers (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    plan TEXT NOT NULL,
    plan_price REAL NOT NULL DEFAULT 399.0,
    phone TEXT NOT NULL DEFAULT '+919876543200',
    preferred_language TEXT NOT NULL DEFAULT 'hi',
    access_point_id TEXT NOT NULL,
    status TEXT NOT NULL,
    payment_status TEXT NOT NULL,
    due_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payment_reminders (
    id TEXT PRIMARY KEY,
    subscriber_id TEXT NOT NULL,
    language TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    delivery_status TEXT NOT NULL,
    FOREIGN KEY (subscriber_id) REFERENCES subscribers (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS incidents (
    id TEXT PRIMARY KEY,
    run_id TEXT,
    status TEXT NOT NULL,
    suspected_component_id TEXT,
    suspected_component_type TEXT,
    summary TEXT NOT NULL,
    confidence_score REAL,
    evidence TEXT NOT NULL DEFAULT '[]',
    uncertainty_note TEXT,
    data_source TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    data_source TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    component_id TEXT NOT NULL,
    timestamp_utc TEXT NOT NULL,
    latency_ms REAL,
    packet_loss_pct REAL,
    throughput_mbps REAL,
    connectivity_ok INTEGER NOT NULL,
    data_source TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_measurements_run_id ON measurements (run_id);
CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs (created_at);
"""

# ── Demo Data — 20 subscribers, 3 villages ───────────────────────────────────

DEMO_SUBSCRIBERS: list[dict[str, Any]] = [
    # Village 1 — Rampur, AP1
    {"id": "SUB101", "phone": "+91987654SUB101", "preferred_language": "hi", "display_name": "Ramesh Patel — Kishan Kirana Store",
     "plan": "Basic", "plan_price": 399.0, "access_point_id": "AP1", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB102", "phone": "+91987654SUB102", "preferred_language": "hi", "display_name": "Gram Panchayat e-Seva Kendra",
     "plan": "Enterprise", "plan_price": 999.0, "access_point_id": "AP1", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB103", "phone": "+91987654SUB103", "preferred_language": "en", "display_name": "Rampur Co-op Bank Branch",
     "plan": "Enterprise", "plan_price": 999.0, "access_point_id": "AP1", "status": "active",
     "payment_status": "due", "due_date": "2026-11-01"},
    # Village 1 — Rampur, AP2
    {"id": "SUB201", "phone": "+91987654SUB201", "preferred_language": "hi", "display_name": "Primary Health Centre Rampur",
     "plan": "Community", "plan_price": 0.0, "access_point_id": "AP2", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB202", "phone": "+91987654SUB202", "preferred_language": "hi", "display_name": "Govt Secondary School Rampur",
     "plan": "Community", "plan_price": 0.0, "access_point_id": "AP2", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB203", "phone": "+91987654SUB203", "preferred_language": "hi", "display_name": "Manoj CSC Digital Centre",
     "plan": "Basic", "plan_price": 399.0, "access_point_id": "AP2", "status": "active",
     "payment_status": "due", "due_date": "2026-10-15"},
    {"id": "SUB204", "phone": "+91987654SUB204", "preferred_language": "hi", "display_name": "Rampur Ration Shop (PDS)",
     "plan": "Basic", "plan_price": 399.0, "access_point_id": "AP2", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    # Village 2 — Bhatpur, AP3
    {"id": "SUB301", "phone": "+91987654SUB301", "preferred_language": "hi", "display_name": "Bhatpur Vegetable Mandi",
     "plan": "Basic", "plan_price": 399.0, "access_point_id": "AP3", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB302", "phone": "+91987654SUB302", "preferred_language": "hi", "display_name": "Bhatpur Milk Collection Point",
     "plan": "Basic", "plan_price": 399.0, "access_point_id": "AP3", "status": "active",
     "payment_status": "due", "due_date": "2026-11-01"},
    {"id": "SUB303", "phone": "+91987654SUB303", "preferred_language": "hi", "display_name": "Bhatpur Village Sarpanch Office",
     "plan": "Enterprise", "plan_price": 999.0, "access_point_id": "AP3", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    # Village 2 — Bhatpur, AP4
    {"id": "SUB401", "phone": "+91987654SUB401", "preferred_language": "hi", "display_name": "Bhatpur Govt Middle School",
     "plan": "Community", "plan_price": 0.0, "access_point_id": "AP4", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB402", "phone": "+91987654SUB402", "preferred_language": "hi", "display_name": "Bhatpur Anganwadi Centre",
     "plan": "Community", "plan_price": 0.0, "access_point_id": "AP4", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB403", "phone": "+91987654SUB403", "preferred_language": "hi", "display_name": "Bhatpur Youth Digital Library",
     "plan": "Basic", "plan_price": 399.0, "access_point_id": "AP4", "status": "active",
     "payment_status": "due", "due_date": "2026-10-28"},
    # Village 3 — Daulatpur, AP5
    {"id": "SUB501", "phone": "+91987654SUB501", "preferred_language": "hi", "display_name": "Daulatpur Haat Bazaar Committee",
     "plan": "Basic", "plan_price": 399.0, "access_point_id": "AP5", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB502", "phone": "+91987654SUB502", "preferred_language": "en", "display_name": "Suresh Cold Storage & Agri",
     "plan": "Enterprise", "plan_price": 999.0, "access_point_id": "AP5", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB503", "phone": "+91987654SUB503", "preferred_language": "hi", "display_name": "Daulatpur CSC e-District Point",
     "plan": "Basic", "plan_price": 399.0, "access_point_id": "AP5", "status": "active",
     "payment_status": "due", "due_date": "2026-11-01"},
    {"id": "SUB504", "phone": "+91987654SUB504", "preferred_language": "en", "display_name": "Daulatpur Police Chowki",
     "plan": "Enterprise", "plan_price": 999.0, "access_point_id": "AP5", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    # Village 3 — Daulatpur, AP6
    {"id": "SUB601", "phone": "+91987654SUB601", "preferred_language": "hi", "display_name": "PHC Daulatpur — Telemedicine",
     "plan": "Community", "plan_price": 0.0, "access_point_id": "AP6", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB602", "phone": "+91987654SUB602", "preferred_language": "hi", "display_name": "Daulatpur Sub-District Hospital",
     "plan": "Community", "plan_price": 0.0, "access_point_id": "AP6", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB604", "phone": "+91987654SUB604", "preferred_language": "hi", "display_name": "Daulatpur Govt ITI College",
     "plan": "Community", "plan_price": 0.0, "access_point_id": "AP6", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
]

DEMO_INCIDENTS: list[dict[str, Any]] = [
    {
        "id": "incident-demo-001",
        "run_id": "run-demo-001",
        "status": "open",
        "suspected_component_id": "L3",
        "suspected_component_type": "link",
        "summary": "[isolated] Degradation localized to link L3 — 5GHz PtP Wireless Bridge (Rampur→North Hamlet)",
        "confidence_score": 0.87,
        "evidence": "[]",
        "uncertainty_note": None,
        "data_source": "simulated",
        "created_at": "2026-10-29T10:00:00Z",
    }
]

DEMO_RUNS: list[dict[str, Any]] = [
    {
        "run_id": "run-demo-001",
        "data_source": "simulated",
        "created_at": "2026-10-29T10:00:00Z",
    }
]

DEMO_MEASUREMENTS: list[dict[str, Any]] = [
    {"run_id": "run-demo-001", "component_id": "L1", "timestamp_utc": "2026-10-29T10:00:00Z", "latency_ms": 2.1, "packet_loss_pct": 0.0, "throughput_mbps": 95.0, "connectivity_ok": 1, "data_source": "simulated"},
    {"run_id": "run-demo-001", "component_id": "L2", "timestamp_utc": "2026-10-29T10:00:00Z", "latency_ms": 5.4, "packet_loss_pct": 0.0, "throughput_mbps": 50.0, "connectivity_ok": 1, "data_source": "simulated"},
    {"run_id": "run-demo-001", "component_id": "L3", "timestamp_utc": "2026-10-29T10:00:00Z", "latency_ms": 180.0, "packet_loss_pct": 25.0, "throughput_mbps": 12.0, "connectivity_ok": 1, "data_source": "simulated"},
    {"run_id": "run-demo-001", "component_id": "L4", "timestamp_utc": "2026-10-29T10:00:00Z", "latency_ms": 3.8, "packet_loss_pct": 0.0, "throughput_mbps": 48.0, "connectivity_ok": 1, "data_source": "simulated"},
    {"run_id": "run-demo-001", "component_id": "L5", "timestamp_utc": "2026-10-29T10:00:00Z", "latency_ms": 4.1, "packet_loss_pct": 0.0, "throughput_mbps": 45.0, "connectivity_ok": 1, "data_source": "simulated"},
    {"run_id": "run-demo-001", "component_id": "L6", "timestamp_utc": "2026-10-29T10:00:00Z", "latency_ms": 6.2, "packet_loss_pct": 0.0, "throughput_mbps": 50.0, "connectivity_ok": 1, "data_source": "simulated"},
    {"run_id": "run-demo-001", "component_id": "L7", "timestamp_utc": "2026-10-29T10:00:00Z", "latency_ms": 7.0, "packet_loss_pct": 0.0, "throughput_mbps": 45.0, "connectivity_ok": 1, "data_source": "simulated"},
    {"run_id": "run-demo-001", "component_id": "L8", "timestamp_utc": "2026-10-29T10:00:00Z", "latency_ms": 3.5, "packet_loss_pct": 0.0, "throughput_mbps": 48.0, "connectivity_ok": 1, "data_source": "simulated"},
    {"run_id": "run-demo-001", "component_id": "L9", "timestamp_utc": "2026-10-29T10:00:00Z", "latency_ms": 4.0, "packet_loss_pct": 0.0, "throughput_mbps": 46.0, "connectivity_ok": 1, "data_source": "simulated"},
    {"run_id": "run-demo-001", "component_id": "L10", "timestamp_utc": "2026-10-29T10:00:00Z", "latency_ms": 4.2, "packet_loss_pct": 0.0, "throughput_mbps": 45.0, "connectivity_ok": 1, "data_source": "simulated"},
    {"run_id": "run-demo-001", "component_id": "L11", "timestamp_utc": "2026-10-29T10:00:00Z", "latency_ms": 5.8, "packet_loss_pct": 0.0, "throughput_mbps": 50.0, "connectivity_ok": 1, "data_source": "simulated"},
    {"run_id": "run-demo-001", "component_id": "L12", "timestamp_utc": "2026-10-29T10:00:00Z", "latency_ms": 6.5, "packet_loss_pct": 0.0, "throughput_mbps": 45.0, "connectivity_ok": 1, "data_source": "simulated"},
    {"run_id": "run-demo-001", "component_id": "L13", "timestamp_utc": "2026-10-29T10:00:00Z", "latency_ms": 3.9, "packet_loss_pct": 0.0, "throughput_mbps": 48.0, "connectivity_ok": 1, "data_source": "simulated"},
    {"run_id": "run-demo-001", "component_id": "L14", "timestamp_utc": "2026-10-29T10:00:00Z", "latency_ms": 4.3, "packet_loss_pct": 0.0, "throughput_mbps": 46.0, "connectivity_ok": 1, "data_source": "simulated"},
]


def init_db(
    db_path: str | None = None,
    seed_demo: bool = True,
    seed_incidents: bool = True,
) -> None:
    """
    Initialize SQLite schema safely.

    - Creates tables if they do not exist.
    - Inserts demo data using ON CONFLICT DO NOTHING (zero duplicates on repeated runs).
    """
    conn = get_db_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        try:
            conn.execute("ALTER TABLE subscribers ADD COLUMN plan_price REAL DEFAULT 399.0;")
        except sqlite3.OperationalError:
            pass
        conn.execute("UPDATE subscribers SET plan_price = 399.0 WHERE plan = 'Basic' AND (plan_price IS NULL OR plan_price = 0.0);")
        conn.execute("UPDATE subscribers SET plan_price = 999.0 WHERE plan = 'Enterprise' AND (plan_price IS NULL OR plan_price = 399.0);")
        conn.execute("UPDATE subscribers SET plan_price = 0.0 WHERE plan = 'Community' AND (plan_price IS NULL OR plan_price = 399.0);")
        try:
            conn.execute("ALTER TABLE subscribers ADD COLUMN phone TEXT DEFAULT '+919876543200';")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE subscribers ADD COLUMN preferred_language TEXT DEFAULT 'hi';")
        except sqlite3.OperationalError:
            pass

        if seed_demo:
            conn.executemany(
                """
                INSERT INTO subscribers (
                    id, display_name, plan, plan_price, phone, preferred_language, access_point_id, status, payment_status, due_date
                ) VALUES (
                    :id, :display_name, :plan, :plan_price, :phone, :preferred_language, :access_point_id, :status, :payment_status, :due_date
                )
                ON CONFLICT(id) DO NOTHING;
                """,
                DEMO_SUBSCRIBERS,
            )

            if seed_incidents:
                conn.executemany(
                    """
                    INSERT INTO incidents (
                        id, run_id, status, suspected_component_id, suspected_component_type,
                        summary, confidence_score, evidence, uncertainty_note, data_source, created_at
                    ) VALUES (
                        :id, :run_id, :status, :suspected_component_id, :suspected_component_type,
                        :summary, :confidence_score, :evidence, :uncertainty_note, :data_source, :created_at
                    )
                    ON CONFLICT(id) DO NOTHING;
                    """,
                    DEMO_INCIDENTS,
                )

                conn.executemany(
                    """
                    INSERT INTO runs (run_id, data_source, created_at)
                    VALUES (:run_id, :data_source, :created_at)
                    ON CONFLICT(run_id) DO NOTHING;
                    """,
                    DEMO_RUNS,
                )

                # Seed measurements if not present for run-demo-001
                cur = conn.execute("SELECT COUNT(*) FROM measurements WHERE run_id = 'run-demo-001';")
                if cur.fetchone()[0] == 0:
                    conn.executemany(
                        """
                        INSERT INTO measurements (
                            run_id, component_id, timestamp_utc, latency_ms, packet_loss_pct,
                            throughput_mbps, connectivity_ok, data_source
                        ) VALUES (
                            :run_id, :component_id, :timestamp_utc, :latency_ms, :packet_loss_pct,
                            :throughput_mbps, :connectivity_ok, :data_source
                        );
                        """,
                        DEMO_MEASUREMENTS,
                    )

            conn.commit()
    finally:
        conn.close()
