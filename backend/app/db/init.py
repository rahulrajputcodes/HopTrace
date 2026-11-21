"""
Database initialization and demo data seeding — HopTrace v2.

v2: 20 subscribers across 3 villages (AP1–AP6).
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
"""

# ── Demo Data — 20 subscribers, 3 villages ───────────────────────────────────

DEMO_SUBSCRIBERS: list[dict[str, Any]] = [
    # Village 1 — Rampur, AP1
    {"id": "SUB101", "display_name": "Ramesh Patel — Kishan Kirana Store",
     "plan": "Basic", "access_point_id": "AP1", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB102", "display_name": "Gram Panchayat e-Seva Kendra",
     "plan": "Enterprise", "access_point_id": "AP1", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB103", "display_name": "Rampur Co-op Bank Branch",
     "plan": "Enterprise", "access_point_id": "AP1", "status": "active",
     "payment_status": "due", "due_date": "2026-11-01"},
    # Village 1 — Rampur, AP2
    {"id": "SUB201", "display_name": "Primary Health Centre Rampur",
     "plan": "Community", "access_point_id": "AP2", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB202", "display_name": "Govt Secondary School Rampur",
     "plan": "Community", "access_point_id": "AP2", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB203", "display_name": "Manoj CSC Digital Centre",
     "plan": "Basic", "access_point_id": "AP2", "status": "active",
     "payment_status": "due", "due_date": "2026-10-15"},
    {"id": "SUB204", "display_name": "Rampur Ration Shop (PDS)",
     "plan": "Basic", "access_point_id": "AP2", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    # Village 2 — Bhatpur, AP3
    {"id": "SUB301", "display_name": "Bhatpur Vegetable Mandi",
     "plan": "Basic", "access_point_id": "AP3", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB302", "display_name": "Bhatpur Milk Collection Point",
     "plan": "Basic", "access_point_id": "AP3", "status": "active",
     "payment_status": "due", "due_date": "2026-11-01"},
    {"id": "SUB303", "display_name": "Bhatpur Village Sarpanch Office",
     "plan": "Enterprise", "access_point_id": "AP3", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    # Village 2 — Bhatpur, AP4
    {"id": "SUB401", "display_name": "Bhatpur Govt Middle School",
     "plan": "Community", "access_point_id": "AP4", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB402", "display_name": "Bhatpur Anganwadi Centre",
     "plan": "Community", "access_point_id": "AP4", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB403", "display_name": "Bhatpur Youth Digital Library",
     "plan": "Basic", "access_point_id": "AP4", "status": "active",
     "payment_status": "due", "due_date": "2026-10-28"},
    # Village 3 — Daulatpur, AP5
    {"id": "SUB501", "display_name": "Daulatpur Haat Bazaar Committee",
     "plan": "Basic", "access_point_id": "AP5", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB502", "display_name": "Suresh Cold Storage & Agri",
     "plan": "Enterprise", "access_point_id": "AP5", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB503", "display_name": "Daulatpur CSC e-District Point",
     "plan": "Basic", "access_point_id": "AP5", "status": "active",
     "payment_status": "due", "due_date": "2026-11-01"},
    {"id": "SUB504", "display_name": "Daulatpur Police Chowki",
     "plan": "Enterprise", "access_point_id": "AP5", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    # Village 3 — Daulatpur, AP6
    {"id": "SUB601", "display_name": "PHC Daulatpur — Telemedicine",
     "plan": "Community", "access_point_id": "AP6", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB602", "display_name": "Daulatpur Sub-District Hospital",
     "plan": "Community", "access_point_id": "AP6", "status": "active",
     "payment_status": "paid", "due_date": "2026-11-15"},
    {"id": "SUB604", "display_name": "Daulatpur Govt ITI College",
     "plan": "Community", "access_point_id": "AP6", "status": "active",
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

        if seed_demo:
            conn.executemany(
                """
                INSERT INTO subscribers (
                    id, display_name, plan, access_point_id, status, payment_status, due_date
                ) VALUES (
                    :id, :display_name, :plan, :access_point_id, :status, :payment_status, :due_date
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

            conn.commit()
    finally:
        conn.close()
