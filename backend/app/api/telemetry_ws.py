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

from app.config import settings
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


def build_telemetry_batch(tick: int = 1) -> Dict[str, Any]:
    """Composes a single telemetry batch for broadcast or testing."""
    engine = get_engine()
    ts_store = get_time_series_store()
    now = datetime.now(timezone.utc).isoformat()
    data_mode = getattr(settings, "data_mode", "demo")

    topo = engine.get_topology(force_in_memory=True)
    all_links = topo.links if topo and topo.links else []

    # Safe integration with Track B agent monitor (I-2)
    agents_snapshot = []
    try:
        from app.services.agent_monitor import get_status_snapshot
        agents_snapshot = get_status_snapshot()
    except Exception:
        agents_snapshot = []

    if data_mode == "live":
        # In live mode: DO NOT generate noisy baselines.
        # Emit one entry for EVERY topology link; links without real data have null metrics and freshness "no_data".
        live_meas = engine.get_live_measurements()
        valid_live_measurements = []
        for link in all_links:
            freshness, _ = engine.get_freshness(link.id)
            if freshness in ("live", "stale") and link.id in live_meas:
                valid_live_measurements.append(live_meas[link.id])

        if valid_live_measurements:
            ts_store.push_measurements_batch(valid_live_measurements, tick=tick)

        risk_map = {r["link_id"]: r for r in ts_store.get_risk_snapshot()}
        link_payloads = []

        for link in all_links:
            link_id = link.id
            freshness, last_seen_utc = engine.get_freshness(link_id)
            m = live_meas.get(link_id) if freshness in ("live", "stale") else None

            if m is not None:
                risk_info = risk_map.get(link_id, {})
                r_score = risk_info.get("risk_score", 0.0)
                predicted_eta = round(max(3.0, (100.0 - r_score) * 0.8), 1) if (r_score >= 35.0 and m.connectivity_ok) else None
                link_payloads.append({
                    "link_id": link_id,
                    "latency_ms": m.latency_ms,
                    "packet_loss_pct": m.packet_loss_pct,
                    "throughput_mbps": m.throughput_mbps,
                    "connectivity_ok": m.connectivity_ok,
                    "data_source": "live",
                    "risk_score": r_score,
                    "trend": risk_info.get("trend", "stable"),
                    "alert_level": risk_info.get("alert_level", "normal"),
                    "ewma_latency_ms": risk_info.get("ewma_latency_ms"),
                    "ewma_loss_pct": risk_info.get("ewma_loss_pct"),
                    "ewma_throughput_mbps": risk_info.get("ewma_throughput_mbps"),
                    "freshness": freshness,
                    "last_seen_utc": last_seen_utc,
                    "predicted_eta_minutes": predicted_eta,
                })
            else:
                link_payloads.append({
                    "link_id": link_id,
                    "latency_ms": None,
                    "packet_loss_pct": None,
                    "throughput_mbps": None,
                    "connectivity_ok": None,
                    "data_source": "no_data",
                    "risk_score": 0.0,
                    "trend": "stable",
                    "alert_level": "normal",
                    "ewma_latency_ms": None,
                    "ewma_loss_pct": None,
                    "ewma_throughput_mbps": None,
                    "freshness": "no_data",
                    "last_seen_utc": last_seen_utc,
                })

        cascade_detected = ts_store.detect_cascade(threshold_risk=60.0) if valid_live_measurements else False
        flapping_links = ts_store.detect_flapping_links() if valid_live_measurements else []

        if any(m.connectivity_ok is False for m in valid_live_measurements):
            network_status = "critical"
        elif any(risk_map.get(m.component_id, {}).get("risk_score", 0.0) >= 75 for m in valid_live_measurements):
            network_status = "critical"
        elif cascade_detected or any(risk_map.get(m.component_id, {}).get("risk_score", 0.0) >= 40 for m in valid_live_measurements):
            network_status = "degraded"
        else:
            network_status = "healthy"

    else:
        # Demo mode (default): behaviour unchanged, simulated noisy baselines
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
            measurements = engine.telemetry_generator.generate_baseline_with_noise()

            latest = engine.get_latest_open_incident()
            injected_measurements = None
            if latest and latest.status == "open" and latest.suspected_component_id:
                run = None
                if latest.run_id:
                    run = engine.get_run_measurements(latest.run_id)
                if run:
                    injected_measurements = run.measurements

            active_measurements = list(injected_measurements or measurements)

            live_meas = engine.get_live_measurements()
            if live_meas:
                active_map = {m.component_id: m for m in active_measurements}
                for comp_id, lm in live_meas.items():
                    active_map[comp_id] = lm
                active_measurements = list(active_map.values())

        ts_store.push_measurements_batch(active_measurements, tick=tick)
        risk_map = {r["link_id"]: r for r in ts_store.get_risk_snapshot()}

        link_payloads = []
        for m in active_measurements:
            risk_info = risk_map.get(m.component_id, {})
            r_score = risk_info.get("risk_score", 0.0)
            predicted_eta = risk_info.get("predicted_eta_minutes")
            if predicted_eta is None and (r_score >= 35.0 and m.connectivity_ok):
                predicted_eta = round(max(3.0, (100.0 - r_score) * 0.8), 1)
            freshness, last_seen_utc = engine.get_freshness(m.component_id)
            link_payloads.append({
                "link_id": m.component_id,
                "latency_ms": m.latency_ms,
                "packet_loss_pct": m.packet_loss_pct,
                "throughput_mbps": m.throughput_mbps,
                "connectivity_ok": m.connectivity_ok,
                "data_source": getattr(m, "data_source", "simulated"),
                "risk_score": r_score,
                "trend": risk_info.get("trend", "stable"),
                "alert_level": risk_info.get("alert_level", "normal"),
                "ewma_latency_ms": risk_info.get("ewma_latency_ms"),
                "ewma_loss_pct": risk_info.get("ewma_loss_pct"),
                "ewma_throughput_mbps": risk_info.get("ewma_throughput_mbps"),
                "prediction_confidence": risk_info.get("prediction_confidence"),
                "prediction_r2": risk_info.get("prediction_r2"),
                "predicted_eta_min_minutes": risk_info.get("predicted_eta_min_minutes"),
                "predicted_eta_max_minutes": risk_info.get("predicted_eta_max_minutes"),
                "freshness": freshness,
                "last_seen_utc": last_seen_utc,
                "predicted_eta_minutes": predicted_eta,
            })

        cascade_detected = ts_store.detect_cascade(threshold_risk=60.0)
        flapping_links = ts_store.detect_flapping_links()

        max_risk = max((r["risk_score"] for r in risk_map.values()), default=0.0)
        if max_risk >= 75 or not all(m.connectivity_ok for m in active_measurements):
            network_status = "critical"
        elif max_risk >= 40 or cascade_detected:
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
            "diagnostic_score": latest.diagnostic_score,
            "evidence": [
                e.model_dump() if hasattr(e, "model_dump") else e
                for e in (latest.evidence or [])
            ],
            "uncertainty_note": latest.uncertainty_note,
            "created_at": latest.created_at,
            "cause": getattr(latest, "cause", None),
            "cause_confidence": getattr(latest, "cause_confidence", None),
            "cause_reasoning": getattr(latest, "cause_reasoning", []),
            "hop_trace": [
                h.model_dump() if hasattr(h, "model_dump") else h
                for h in (getattr(latest, "hop_trace", []) or [])
            ],
        }

    return {
        "type": "telemetry_batch",
        "tick": tick,
        "timestamp_utc": now,
        "data_mode": data_mode,
        "data_source": "live" if (data_mode == "live" or any(getattr(m, "data_source", "simulated") == "live" for m in link_payloads)) else "simulated",
        "measurements": link_payloads,
        "links": link_payloads,
        "agents": agents_snapshot,
        "active_incident": incident_payload,
        "cascade_detected": cascade_detected,
        "flapping_links": flapping_links,
        "network_status": network_status,
    }


async def _streaming_loop() -> None:
    """Background coroutine: generates and broadcasts telemetry every TICK_INTERVAL_SECONDS."""
    tick = 0

    while True:
        try:
            await asyncio.sleep(TICK_INTERVAL_SECONDS)

            if not _connected_clients:
                continue

            tick += 1
            batch = build_telemetry_batch(tick=tick)
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
