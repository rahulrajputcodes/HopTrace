"""In-memory time-series store for per-link telemetry samples.

Stores a rolling ring buffer of Measurement objects for each link and
provides get_risk_snapshot(), which returns per-link current metrics merged
with Theil-Sen predictions from engine/predictor.py.

Design:
- One deque(maxlen=200) per link — keeps the last 200 samples.
- Thread-safe enough for the single-threaded asyncio event loop used by
  the WebSocket streaming task; no explicit locking needed.
- A module-level singleton is used so the WebSocket loop and the REST
  endpoint share the same store instance.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional

from backend.app.engine.models import Measurement
from backend.app.engine.predictor import predict_link
from backend.app.engine.telemetry import BASELINE_TELEMETRY

_MAX_RING: int = 200  # maximum samples retained per link


class TimeSeriesStore:
    """Rolling time-series store for simulated link telemetry."""

    def __init__(self, max_ring: int = _MAX_RING) -> None:
        self._max_ring = max_ring
        self._store: Dict[str, deque[Measurement]] = {}

    # ── Write ──────────────────────────────────────────────────────────────────

    def push(self, link_id: str, measurement: Measurement) -> None:
        """Append a measurement to the ring buffer for link_id."""
        if link_id not in self._store:
            self._store[link_id] = deque(maxlen=self._max_ring)
        self._store[link_id].append(measurement)

    def push_batch(self, measurements: List[Measurement]) -> None:
        """Append a list of measurements (one per link)."""
        for m in measurements:
            self.push(m.component_id, m)

    def clear(self, link_id: Optional[str] = None) -> None:
        """Clear samples for one link or all links."""
        if link_id is not None:
            self._store.pop(link_id, None)
        else:
            self._store.clear()

    # ── Read ───────────────────────────────────────────────────────────────────

    def get_samples(self, link_id: str, n: Optional[int] = None) -> List[Measurement]:
        """Return the last n samples for link_id (oldest first).

        Returns all stored samples if n is None.
        """
        buf = self._store.get(link_id)
        if not buf:
            return []
        samples = list(buf)
        if n is not None:
            samples = samples[-n:]
        return samples

    def get_link_ids(self) -> List[str]:
        """Return all link IDs that have at least one sample."""
        return [lid for lid, buf in self._store.items() if buf]

    # ── Risk snapshot ──────────────────────────────────────────────────────────

    def get_risk_snapshot(
        self,
        baselines: Optional[Dict[str, Dict[str, float | bool]]] = None,
    ) -> List[Dict[str, Any]]:
        """Return a per-link risk snapshot including optional ETA predictions.

        For each link with at least one sample, returns a dict containing:
            link_id              : str
            connectivity_ok      : bool | None
            packet_loss_pct      : float | None
            latency_ms           : float | None
            throughput_mbps      : float | None
            data_source          : str ("simulated")
            predicted_eta_minutes: float | None   (optional, from predictor)
            prediction_confidence: str | None     (optional: high/medium/low)
            prediction_r2        : float | None   (optional)

        All prediction fields are absent (None) when the predictor cannot
        issue a forecast (too few samples, link stable, link already failed).
        """
        bl = baselines or BASELINE_TELEMETRY
        snapshot: List[Dict[str, Any]] = []

        for link_id in sorted(self.get_link_ids()):
            samples = self.get_samples(link_id)
            if not samples:
                continue
            latest = samples[-1]

            entry: Dict[str, Any] = {
                "link_id": link_id,
                "connectivity_ok": latest.connectivity_ok,
                "packet_loss_pct": latest.packet_loss_pct,
                "latency_ms": latest.latency_ms,
                "throughput_mbps": latest.throughput_mbps,
                "data_source": latest.data_source,
                "predicted_eta_minutes": None,
                "prediction_confidence": None,
                "prediction_r2": None,
            }

            prediction = predict_link(link_id, samples, baselines=bl)
            if prediction is not None:
                entry["predicted_eta_minutes"] = prediction["predicted_eta_minutes"]
                entry["prediction_confidence"] = prediction["prediction_confidence"]
                entry["prediction_r2"] = prediction["prediction_r2"]

            snapshot.append(entry)

        return snapshot


# ── Module-level singleton ────────────────────────────────────────────────────

_store_instance: Optional[TimeSeriesStore] = None


def get_time_series_store() -> TimeSeriesStore:
    """Return the shared TimeSeriesStore singleton."""
    global _store_instance
    if _store_instance is None:
        _store_instance = TimeSeriesStore()
    return _store_instance
