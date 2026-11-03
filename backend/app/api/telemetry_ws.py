"""WebSocket /api/v1/ws/telemetry

Streams simulated telemetry to connected clients every TICK_INTERVAL_SECONDS.
Each tick:
  1. Checks the engine's ramp state; if a gradual_degradation ramp is active,
     generates a ramped measurement for the target link and baseline measurements
     for all others.  Without a ramp, generates pure baseline measurements.
  2. Pushes all measurements into the shared TimeSeriesStore.
  3. Runs the DiagnosticEngine on the current measurements (no scenario/target
     label is passed — the engine infers from observations only).
  4. If the engine opens a new incident for a component that has no open
     incident yet, persists it to SQLite (same path as api/lab.py).
  5. Builds the risk snapshot (latest metrics + Theil-Sen predictions) and
     broadcasts it as a flat JSON message to the client.

CRITICAL: The diagnostic engine never receives the scenario name or target
link ID.  All predictions come from observed sample trends only.

Message format (flat JSON):
{
  "tick": <int>,
  "links": [
    {
      "link_id": "L3",
      "connectivity_ok": true,
      "packet_loss_pct": 8.2,
      "latency_ms": 87.4,
      "throughput_mbps": 18.1,
      "data_source": "simulated",
      "predicted_eta_minutes": 14.0,   // null when absent
      "prediction_confidence": "medium", // null when absent
      "prediction_r2": 0.71             // null when absent
    },
    ...
  ]
}
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.db.connection import get_db_connection
from app.db.repository import create_incident, get_incident
from app.engine.diagnostics import DiagnosticEngine
from app.engine.facade import get_engine
from app.engine.telemetry import BASELINE_TELEMETRY, SimulatedTelemetryGenerator
from app.engine.time_series import get_time_series_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["telemetry"])

# Tick interval for the streaming loop (seconds)
TICK_INTERVAL_SECONDS: float = 3.0

_diag_engine = DiagnosticEngine()
_telemetry_gen = SimulatedTelemetryGenerator()

# Track which suspected components already have an open incident to avoid
# persisting duplicates across ticks.
_open_incidents_by_component: dict[str, str] = {}  # component_id -> incident_id


@router.websocket("/ws/telemetry")
async def telemetry_ws(websocket: WebSocket) -> None:
    """Stream simulated telemetry and predictions over WebSocket."""
    await websocket.accept()
    logger.info("WebSocket /ws/telemetry: client connected")

    try:
        tick = 0
        while True:
            engine = get_engine()
            ramp = engine.get_ramp_state()

            # 1. Generate measurements for this tick
            if ramp is not None:
                progress = engine.advance_ramp_tick()
                measurements = _telemetry_gen.generate_measurements(
                    scenario="gradual_degradation",
                    target_link_id=ramp["target_link_id"],
                    severity=ramp["severity"],
                    ramp_progress=progress,
                )
            else:
                engine.advance_ramp_tick()  # keep tick counter monotonic
                measurements = _telemetry_gen.generate_measurements(scenario="baseline")

            # 2. Push into time-series store
            store = get_time_series_store()
            store.push_batch(measurements)

            # 3. Run diagnostic engine (no scenario/target label injected)
            topology = engine.get_topology(force_in_memory=True)
            incident = _diag_engine.diagnose(
                measurements=measurements,
                topology=topology,
                run_id=f"ws-tick-{tick}",
            )

            # 4. Persist new incidents to SQLite (at most one per suspected component)
            if (
                incident.suspected_component_id is not None
                and incident.status == "open"
                and incident.suspected_component_id not in _open_incidents_by_component
            ):
                _persist_incident(incident)
                _open_incidents_by_component[incident.suspected_component_id] = incident.id
                engine._incidents[incident.id] = incident
                engine._incident_order.append(incident.id)

            # Clear stale open-incident tracker when baseline measurements come in
            # (diagnostic engine returns closed + no component)
            if incident.suspected_component_id is None and incident.status == "closed":
                _open_incidents_by_component.clear()

            # 5. Build risk snapshot and broadcast
            snapshot = store.get_risk_snapshot()
            message = {"tick": tick, "links": snapshot}
            await websocket.send_text(json.dumps(message))

            tick += 1
            await asyncio.sleep(TICK_INTERVAL_SECONDS)

    except WebSocketDisconnect:
        logger.info("WebSocket /ws/telemetry: client disconnected")
    except Exception as exc:
        logger.error("WebSocket /ws/telemetry error: %s", exc)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass


def _persist_incident(incident) -> None:  # type: ignore[no-untyped-def]
    """Persist a streaming-loop incident to SQLite (guarded, best-effort)."""
    try:
        db = get_db_connection(settings.sqlite_db_path)
        existing = get_incident(db, incident.id)
        if existing is None:
            evidence_list = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in (incident.evidence or [])
            ]
            record = {
                "id": incident.id,
                "run_id": incident.run_id,
                "status": incident.status,
                "suspected_component_id": incident.suspected_component_id,
                "suspected_component_type": incident.suspected_component_type,
                "summary": incident.summary,
                "confidence_score": incident.confidence_score,
                "evidence": evidence_list,
                "uncertainty_note": incident.uncertainty_note,
                "data_source": incident.data_source,
                "created_at": incident.created_at,
            }
            create_incident(db, record)
    except Exception as exc:
        logger.warning("WebSocket: failed to persist incident %s: %s", incident.id, exc)
