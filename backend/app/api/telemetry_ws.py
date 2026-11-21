"""WebSocket endpoint for real-time telemetry streaming — HopTrace v2.

Endpoint: WS /ws/telemetry and WS /api/v1/ws/telemetry

Pushes a telemetry batch every TICK_INTERVAL_SECONDS seconds to all
connected clients. Batch includes:
  - Per-link measurements with risk scores, EWMA stats, and Theil-Sen ETA predictions
  - Active incident (if any) from the engine
  - Cascade/flapping detection flags
  - Tick counter
  - Data source flag ("live" or "simulated")
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.engine.facade import get_engine
from app.engine.telemetry import RAMP_TICKS
from app.engine.time_series import get_time_series_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["telemetry"])

TICK_INTERVAL_SECONDS: float = 3.0

# Connected WebSocket clients
_connected_clients: Set[WebSocket] = set()

# Background streaming task handle
_streaming_task: Optional[asyncio.Task] = None


async def _broadcast(message: Dict[str, Any]) -> None:
    """Send a JSON message to all connected WebSocket clients."""
    if not _connected_clients:
        return
    payload = json.dumps(message, default=str)
    dead_clients: Set[WebSocket] = set()
    for ws in list(_connected_clients):
        try:
            await ws.send_text(payload)
        except Exception:
            dead_clients.add(ws)
    _connected_clients.difference_update(dead_clients)


async def _streaming_loop() -> None:
    """Background coroutine: generates and broadcasts telemetry every TICK_INTERVAL_SECONDS."""
    engine = get_engine()
    ts_store = get_time_series_store()
    tick = 0

    while True:
        try:
            await asyncio.sleep(TICK_INTERVAL_SECONDS)

            if not _connected_clients:
                continue

            tick += 1
            now = datetime.now(timezone.utc).isoformat()

            # If there is an active ramp, advance it
            ramp = engine.get_ramp_state()
            if ramp is not None:
                progress = engine.advance_ramp_tick()
                baseline_measurements = engine.telemetry_generator.generate_baseline_with_noise()
                ramp_measurement = engine.telemetry_generator.generate_ramp_measurement(
                    link_id=ramp["target_link_id"],
                    severity=ramp["severity"],
                    progress=progress,
                    timestamp=now,
                )
                active_measurements = [
                    ramp_measurement if m.component_id == ramp["target_link_id"] else m
                    for m in baseline_measurements
                ]
            else:
                # Generate noisy baseline measurements for streaming
                measurements = engine.telemetry_generator.generate_baseline_with_noise()

                # If there is an active injected incident, overlay its measurements
                latest = engine.get_latest_open_incident()
                injected_measurements = None
                if latest and latest.status == "open" and latest.suspected_component_id:
                    run = None
                    if latest.run_id:
                        run = engine.get_run_measurements(latest.run_id)
                    if run:
                        injected_measurements = run.measurements

                active_measurements = list(injected_measurements or measurements)

                # Overlay live ingested measurements (if any), replacing simulated values for those links
                live_meas = engine.get_live_measurements()
                if live_meas:
                    active_map = {m.component_id: m for m in active_measurements}
                    for comp_id, lm in live_meas.items():
                        active_map[comp_id] = lm
                    active_measurements = list(active_map.values())

            # Push into time-series store
            ts_store.push_measurements_batch(active_measurements, tick=tick)

            # Build risk snapshot
            risk_map = {r["link_id"]: r for r in ts_store.get_risk_snapshot()}

            # Compose per-link payload
            link_payloads = []
            for m in active_measurements:
                risk_info = risk_map.get(m.component_id, {})
                link_payloads.append({
                    "link_id": m.component_id,
                    "latency_ms": m.latency_ms,
                    "packet_loss_pct": m.packet_loss_pct,
                    "throughput_mbps": m.throughput_mbps,
                    "connectivity_ok": m.connectivity_ok,
                    "data_source": getattr(m, "data_source", "simulated"),
                    "risk_score": risk_info.get("risk_score", 0.0),
                    "trend": risk_info.get("trend", "stable"),
                    "alert_level": risk_info.get("alert_level", "normal"),
                    "ewma_latency_ms": risk_info.get("ewma_latency_ms"),
                    "ewma_loss_pct": risk_info.get("ewma_loss_pct"),
                    "ewma_throughput_mbps": risk_info.get("ewma_throughput_mbps"),
                    "predicted_eta_minutes": risk_info.get("predicted_eta_minutes"),
                    "prediction_confidence": risk_info.get("prediction_confidence"),
                    "prediction_r2": risk_info.get("prediction_r2"),
                    "predicted_eta_min_minutes": risk_info.get("predicted_eta_min_minutes"),
                    "predicted_eta_max_minutes": risk_info.get("predicted_eta_max_minutes"),
                })

            # Cascade + flapping detection
            cascade_detected = ts_store.detect_cascade(threshold_risk=60.0)
            flapping_links = ts_store.detect_flapping_links()

            # Network-level status
            max_risk = max((r.get("risk_score", 0.0) for r in link_payloads), default=0.0)
            if max_risk >= 75.0 or not all(m.connectivity_ok for m in active_measurements):
                network_status = "critical"
            elif max_risk >= 40.0 or cascade_detected:
                network_status = "degraded"
            else:
                network_status = "healthy"

            # Active incident payload
            latest = engine.get_latest_open_incident()
            incident_payload = None
            if latest and latest.status == "open":
                incident_payload = {
                    "id": latest.id,
                    "run_id": latest.run_id,
                    "status": latest.status,
                    "suspected_component_id": latest.suspected_component_id,
                    "suspected_component_type": latest.suspected_component_type,
                    "summary": latest.summary,
                    "confidence_score": latest.confidence_score,
                    "diagnostic_score": getattr(latest, "diagnostic_score", 0.0),
                    "evidence": [
                        e.model_dump() if hasattr(e, "model_dump") else e
                        for e in (latest.evidence or [])
                    ],
                    "uncertainty_note": latest.uncertainty_note,
                    "created_at": latest.created_at,
                }

            has_live = any(getattr(m, "data_source", "simulated") == "live" for m in active_measurements)

            batch = {
                "type": "telemetry_batch",
                "tick": tick,
                "timestamp_utc": now,
                "data_source": "live" if has_live else "simulated",
                "measurements": link_payloads,
                "links": link_payloads,
                "active_incident": incident_payload,
                "cascade_detected": cascade_detected,
                "flapping_links": flapping_links,
                "network_status": network_status,
            }

            await _broadcast(batch)

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.debug("Streaming loop tick exception: %s", exc)
            await asyncio.sleep(1.0)


def start_streaming_loop() -> None:
    """Start the background streaming task (called from app lifespan)."""
    global _streaming_task
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return
    if _streaming_task is None or _streaming_task.done():
        _streaming_task = loop.create_task(_streaming_loop())


def stop_streaming_loop() -> None:
    """Stop the background streaming task (called from app lifespan)."""
    global _streaming_task
    if _streaming_task and not _streaming_task.done():
        _streaming_task.cancel()
        _streaming_task = None


@router.websocket("/ws/telemetry")
async def telemetry_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint — clients connect here to receive live telemetry pushes."""
    await websocket.accept()
    _connected_clients.add(websocket)

    engine = get_engine()
    ts_store = get_time_series_store()
    try:
        risk_snapshot = ts_store.get_risk_snapshot()
        latest = engine.get_latest_open_incident()
        incident_payload = None
        if latest and latest.status == "open":
            incident_payload = {
                "id": latest.id,
                "suspected_component_id": latest.suspected_component_id,
                "summary": latest.summary,
                "confidence_score": latest.confidence_score,
                "created_at": latest.created_at,
            }
        has_live = any(getattr(m, "data_source", "simulated") == "live" for m in engine.get_live_measurements().values())
        await websocket.send_text(
            json.dumps(
                {
                    "type": "connected",
                    "message": "HopTrace v2 live telemetry stream connected.",
                    "data_source": "live" if has_live else "simulated",
                    "risk_snapshot": risk_snapshot,
                    "active_incident": incident_payload,
                },
                default=str,
            )
        )
    except Exception:
        pass

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text(json.dumps({"type": "keepalive"}))
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        _connected_clients.discard(websocket)
