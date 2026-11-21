"""
GET /api/v1/public/villages

Public network status endpoint — no authentication required.

Exposes per-village connectivity status suitable for a public-facing status
page (kiosk, website widget, SMS gateway).

Privacy guarantee
-----------------
This module MUST NOT expose:
  - Subscriber names, phone numbers, subscriber IDs, or subscriber counts
  - Incident IDs, run IDs, confidence scores, evidence arrays
  - Diagnostic internals or suspected component identifiers
  - Any PII of any kind

Data freshness
--------------
Status is derived from the in-process TimeSeriesStore ring buffer (live EWMA
telemetry).  `since` timestamps come exclusively from persisted SQLite incident
rows — never invented.  When telemetry is absent, the response honestly reports
"no_data" rather than fabricating an "up" state.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.db.connection import get_db
from app.db.repository import VILLAGE_COMPONENT_MAP
from app.engine.time_series import get_time_series_store
from app.engine.topology import VILLAGE_METADATA

router = APIRouter(tags=["public"])

# ── Link → village mapping (excludes L1 — handled separately as gateway) ──────
# L1 is the shared fibre backhaul.  Its presence in the ts store alone must NOT
# promote a village to "up" when that village has no village-specific telemetry.
VILLAGE_LINKS: Dict[str, List[str]] = {
    "rampur":    ["L2", "L3", "L4", "L5"],
    "bhatpur":   ["L6", "L7", "L8", "L9", "L10"],
    "daulatpur": ["L11", "L12", "L13", "L14"],
}
GATEWAY_LINK = "L1"

# ── Deterministic bilingual message table ─────────────────────────────────────
_MESSAGES: Dict[str, Dict[str, str]] = {
    "up": {
        "en": "Network is operating normally.",
        "hi": "नेटवर्क सामान्य रूप से चल रहा है।",
    },
    "degraded": {
        "en": "Network performance is degraded. Our team is monitoring.",
        "hi": "नेटवर्क प्रदर्शन प्रभावित है। हमारी टीम निगरानी कर रही है।",
    },
    "down": {
        "en": "Network outage detected. Our team is working to restore service.",
        "hi": "नेटवर्क में बाधा है। हमारी टीम सेवा बहाल करने में लगी है।",
    },
    "no_data": {
        "en": "Network status is currently unavailable.",
        "hi": "नेटवर्क की स्थिति अभी उपलब्ध नहीं है।",
    },
}


def _render_message(status: str, lang: str) -> str:
    """Return a localised status message.

    Attempts app.services.templates.render_message(kind, lang, ctx) first.
    Falls back to the built-in _MESSAGES table on ImportError, AttributeError,
    or any runtime exception.  Unknown lang silently falls back to "en".
    """
    resolved_lang = lang if lang in ("en", "hi") else "en"
    try:
        from app.services.templates import render_message  # type: ignore[import]
        return render_message(
            "village_status", resolved_lang, {"status": status}
        )
    except Exception:
        pass
    lang_map = _MESSAGES.get(status, _MESSAGES["no_data"])
    return lang_map.get(resolved_lang, lang_map["en"])


def _village_status(
    village_id: str,
    risk_map: Dict[str, Dict[str, Any]],
    gateway_entry: Optional[Dict[str, Any]],
) -> str:
    """Derive the public status for one village.

    Priority order:
    1. No village-specific links in the ts store → "no_data".
       Gateway L1 alone does NOT promote a village to "up".
    2. Gateway L1 risk ≥ 60 → "down" (backhaul failure affects all villages).
    3. All tracked village links have connectivity_ok=False → "down".
    4. max village risk_score ≥ 60 → "down".
    5. max village risk_score ≥ 30 → "degraded".
    6. Otherwise → "up".
    """
    own_link_ids = VILLAGE_LINKS.get(village_id, [])
    own_entries = [risk_map[lid] for lid in own_link_ids if lid in risk_map]

    # Rule 1 — no telemetry for this village's own links
    if not own_entries:
        return "no_data"

    # Rule 2 — gateway failure cascades
    if gateway_entry is not None and gateway_entry.get("risk_score", 0.0) >= 60.0:
        return "down"

    # Rule 3 — all tracked links report connectivity lost
    if all(not e.get("connectivity_ok", True) for e in own_entries):
        return "down"

    # Rules 4 & 5 — risk score thresholds
    max_risk = max(e.get("risk_score", 0.0) for e in own_entries)
    if max_risk >= 60.0:
        return "down"
    if max_risk >= 30.0:
        return "degraded"
    return "up"


def _get_since(
    village_id: str,
    status: str,
    conn: sqlite3.Connection,
) -> Optional[str]:
    """Return the ISO timestamp when the current status began, or None.

    Queries for the earliest open incident whose suspected_component_id
    belongs to this village's component set.  Never invents a timestamp.

    Returns None when:
      - status is "no_data" (no telemetry, no meaningful start time)
      - status is "up" with no open incidents
      - no open incidents match this village's components
    """
    if status == "no_data":
        return None

    village_components = list(VILLAGE_COMPONENT_MAP.get(village_id, []))
    if not village_components:
        return None

    placeholders = ",".join("?" for _ in village_components)
    cursor = conn.execute(
        f"""
        SELECT created_at
        FROM incidents
        WHERE status = 'open'
          AND suspected_component_id IN ({placeholders})
        ORDER BY created_at ASC
        LIMIT 1;
        """,
        village_components,
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return row[0]  # raw ISO string from SQLite — never modified


# ── Pydantic response models ──────────────────────────────────────────────────

class VillageStatusItem(BaseModel):
    id: str
    name: str
    status: str            # "up" | "degraded" | "down" | "no_data"
    since: Optional[str]   # ISO 8601 UTC or null
    message: str


class PublicVillagesResponse(BaseModel):
    updated_at: str        # ISO 8601 UTC of this response
    villages: List[VillageStatusItem]


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get(
    "/public/villages",
    response_model=PublicVillagesResponse,
    summary="Public village network status",
    description=(
        "Returns the current network connectivity status for each village. "
        "No authentication required. "
        "No subscriber data, incident internals, or diagnostic details are exposed."
    ),
)
def get_public_villages(
    lang: str = Query(
        default="en",
        description=(
            "Response language: 'en' (default) or 'hi'. "
            "Unknown values fall back to 'en' silently."
        ),
    ),
    conn: sqlite3.Connection = Depends(get_db),
) -> PublicVillagesResponse:
    """Public village status — no authentication required."""
    now_utc = datetime.now(timezone.utc).isoformat()

    # Normalise language once; re-used for every village message
    resolved_lang = lang if lang in ("en", "hi") else "en"

    # Pull live risk snapshot once — avoids repeated store lookups
    ts_store = get_time_series_store()
    snapshot = ts_store.get_risk_snapshot()
    risk_map: Dict[str, Dict[str, Any]] = {e["link_id"]: e for e in snapshot}

    # Gateway entry — may be None when the store has no L1 data yet
    gateway_entry: Optional[Dict[str, Any]] = risk_map.get(GATEWAY_LINK)

    items: List[VillageStatusItem] = []
    for village_id, meta in VILLAGE_METADATA.items():
        status = _village_status(village_id, risk_map, gateway_entry)
        since = _get_since(village_id, status, conn)
        message = _render_message(status, resolved_lang)
        items.append(
            VillageStatusItem(
                id=village_id,
                name=meta["name"],
                status=status,
                since=since,
                message=message,
            )
        )

    return PublicVillagesResponse(updated_at=now_utc, villages=items)
