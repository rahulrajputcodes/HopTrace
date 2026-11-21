"""Time-series ring buffer, EWMA anomaly detection, and predictive risk scoring for HopTrace v2.

Each link maintains a circular buffer of the last N measurements.
Supports:
  - EWMA smoothed metric estimates, risk scores (0–100), and trend classification
  - Flap and cascade detection
  - Theil-Sen regression ETA-to-failure predictions via engine.predictor
  - Thread-safe enough for the single-threaded asyncio event loop

No external dependencies: pure Python stdlib.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

from app.engine.models import Measurement
from app.engine.predictor import predict_link


# EWMA smoothing factor (0 < α ≤ 1). Higher → more reactive.
EWMA_ALPHA: float = 0.30
# Number of past samples kept per link
BUFFER_SIZE: int = 200
# Soft-alert threshold: deviation > this σ signals early warning
SOFT_ALERT_SIGMA: float = 2.5
# Hard-alert threshold: deviation > this σ confirms anomaly
HARD_ALERT_SIGMA: float = 4.0
# Flapping: connectivity_ok toggles this many times in FLAP_WINDOW ticks
FLAP_COUNT_THRESHOLD: int = 3
FLAP_WINDOW: int = 20


@dataclass
class LinkSample:
    """A single telemetry snapshot for one link."""

    tick: int
    timestamp_utc: str
    latency_ms: Optional[float]
    packet_loss_pct: Optional[float]
    throughput_mbps: Optional[float]
    connectivity_ok: bool
    data_source: str = "simulated"
    # Derived fields (filled by TimeSeriesStore after push)
    risk_score: float = 0.0
    trend: str = "stable"  # stable | degrading | recovering
    alert_level: str = "normal"  # normal | warning | critical

    def to_measurement(self, link_id: str) -> Measurement:
        """Convert sample to Measurement object for diagnostic and predictive engines."""
        return Measurement(
            component_id=link_id,
            timestamp_utc=self.timestamp_utc,
            latency_ms=self.latency_ms,
            packet_loss_pct=self.packet_loss_pct,
            throughput_mbps=self.throughput_mbps,
            connectivity_ok=self.connectivity_ok,
            data_source=self.data_source,
        )


@dataclass
class LinkState:
    """Running EWMA and predictive state for a single link."""

    link_id: str
    buffer: Deque[LinkSample] = field(
        default_factory=lambda: deque(maxlen=BUFFER_SIZE)
    )

    # EWMA smoothed values
    ewma_latency: Optional[float] = None
    ewma_loss: Optional[float] = None
    ewma_throughput: Optional[float] = None

    # Variance estimate (Welford online algorithm)
    _m2_latency: float = 0.0
    _m2_loss: float = 0.0
    _m2_throughput: float = 0.0
    _count: int = 0

    # Flap detection
    flap_count: int = 0
    _last_connectivity: Optional[bool] = None

    # Recent trend slope (computed over last 10 samples)
    trend: str = "stable"
    alert_level: str = "normal"
    risk_score: float = 0.0


class TimeSeriesStore:
    """Manages per-link time-series state with EWMA anomaly scoring and predictive ETA."""

    def __init__(
        self,
        baselines: Optional[Dict[str, Dict[str, Any]]] = None,
        ewma_alpha: float = EWMA_ALPHA,
        buffer_size: int = BUFFER_SIZE,
    ) -> None:
        from .telemetry import BASELINE_TELEMETRY

        self.baselines: Dict[str, Dict[str, Any]] = baselines or BASELINE_TELEMETRY
        self.alpha = ewma_alpha
        self.buffer_size = buffer_size
        self._link_states: Dict[str, LinkState] = {}
        self._global_tick: int = 0

    def _get_or_create(self, link_id: str) -> LinkState:
        if link_id not in self._link_states:
            self._link_states[link_id] = LinkState(
                link_id=link_id,
                buffer=deque(maxlen=self.buffer_size),
            )
        return self._link_states[link_id]

    def push(
        self,
        link_id: str,
        latency_ms_or_measurement: Any = None,
        packet_loss_pct: Optional[float] = None,
        throughput_mbps: Optional[float] = None,
        connectivity_ok: bool = True,
        tick: Optional[int] = None,
        data_source: str = "simulated",
    ) -> LinkSample:
        """Push a new measurement into the ring buffer and update EWMA state.

        Supports calling with either separate scalar arguments or a single Measurement instance:
            store.push("L1", measurement)
            store.push("L1", latency_ms=12.0, packet_loss_pct=0.0, ...)
        """
        if (
            isinstance(latency_ms_or_measurement, Measurement)
            or type(latency_ms_or_measurement).__name__ == "Measurement"
            or (
                hasattr(latency_ms_or_measurement, "latency_ms")
                and hasattr(latency_ms_or_measurement, "packet_loss_pct")
                and not isinstance(latency_ms_or_measurement, (int, float))
            )
        ):
            m = latency_ms_or_measurement
            latency_ms = m.latency_ms
            packet_loss_pct = m.packet_loss_pct
            throughput_mbps = m.throughput_mbps
            connectivity_ok = m.connectivity_ok
            data_source = getattr(m, "data_source", "simulated")
        else:
            latency_ms = latency_ms_or_measurement

        if tick is None:
            self._global_tick += 1
            tick = self._global_tick

        state = self._get_or_create(link_id)
        state._count += 1

        # --- EWMA update ---
        alpha = self.alpha

        def ewma_update(
            current: Optional[float], new_val: Optional[float]
        ) -> Optional[float]:
            if new_val is None:
                return current
            if current is None:
                return new_val
            return alpha * new_val + (1.0 - alpha) * current

        state.ewma_latency = ewma_update(state.ewma_latency, latency_ms)
        state.ewma_loss = ewma_update(state.ewma_loss, packet_loss_pct)
        state.ewma_throughput = ewma_update(state.ewma_throughput, throughput_mbps)

        # --- Flap detection ---
        if (
            state._last_connectivity is not None
            and connectivity_ok != state._last_connectivity
        ):
            state.flap_count += 1
        state._last_connectivity = connectivity_ok

        # Decay flap count outside window
        if state._count % FLAP_WINDOW == 0:
            state.flap_count = max(0, state.flap_count - 1)

        # --- Risk score computation ---
        risk = self._compute_risk_score(
            link_id, state, latency_ms, packet_loss_pct, throughput_mbps, connectivity_ok
        )
        state.risk_score = risk

        # Alert level
        if risk >= 75.0 or not connectivity_ok:
            state.alert_level = "critical"
        elif risk >= 40.0:
            state.alert_level = "warning"
        else:
            state.alert_level = "normal"

        sample = LinkSample(
            tick=tick,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            latency_ms=latency_ms,
            packet_loss_pct=packet_loss_pct,
            throughput_mbps=throughput_mbps,
            connectivity_ok=connectivity_ok,
            data_source=data_source,
            risk_score=risk,
            alert_level=state.alert_level,
        )
        state.buffer.append(sample)

        # Update trend after appending sample
        state.trend = self._compute_trend(state)
        sample.trend = state.trend

        return sample

    def push_measurement(self, m: Measurement, tick: Optional[int] = None) -> LinkSample:
        """Push a single Measurement object into the store."""
        return self.push(
            link_id=m.component_id,
            latency_ms_or_measurement=m,
            tick=tick,
        )

    def push_batch(self, measurements: List[Measurement], tick: Optional[int] = None) -> None:
        """Push a batch of Measurement objects into the store."""
        self.push_measurements_batch(measurements, tick=tick)

    def push_measurements_batch(
        self, measurements: List[Any], tick: Optional[int] = None
    ) -> None:
        """Push a list of Measurement objects from the telemetry generator."""
        if tick is None:
            self._global_tick += 1
            tick = self._global_tick
        for m in measurements:
            self.push(
                link_id=m.component_id,
                latency_ms_or_measurement=m,
                tick=tick,
            )

    def get_measurements(self, link_id: str) -> List[Measurement]:
        """Return all buffered samples for a link as Measurement objects."""
        state = self._link_states.get(link_id)
        if not state:
            return []
        return [s.to_measurement(link_id) for s in state.buffer]

    def get_samples(self, link_id: str) -> List[Measurement]:
        """Alias for get_measurements."""
        return self.get_measurements(link_id)

    def clear(self, link_id: Optional[str] = None) -> None:
        """Clear buffered samples for a specific link, or all links if link_id is None."""
        if link_id is not None:
            self._link_states.pop(link_id, None)
        else:
            self._link_states.clear()

    def _compute_risk_score(
        self,
        link_id: str,
        state: LinkState,
        latency_ms: Optional[float],
        packet_loss_pct: Optional[float],
        throughput_mbps: Optional[float],
        connectivity_ok: bool,
    ) -> float:
        """Compute composite risk score (0-100) based on deviation from baseline."""
        if not connectivity_ok:
            return 100.0

        base = self.baselines.get(link_id, {})
        base_lat = float(base.get("latency_ms", 20.0))
        base_tp = float(base.get("throughput_mbps", 50.0))

        score = 0.0

        # Loss degradation (weight 0.40)
        loss = packet_loss_pct if packet_loss_pct is not None else 0.0
        if loss > 0.5:
            loss_factor = min(1.0, (loss - 0.5) / 25.0)
            score += 40.0 * loss_factor

        # Latency degradation (weight 0.30)
        if latency_ms is not None and base_lat > 0:
            ewma_lat = state.ewma_latency or latency_ms
            lat_ratio = max(1.0, ewma_lat / base_lat)
            lat_factor = min(1.0, max(0.0, (lat_ratio - 1.2) / 3.0))
            score += 30.0 * lat_factor

        # Throughput degradation (weight 0.20)
        if throughput_mbps is not None and base_tp > 0:
            ewma_tp = state.ewma_throughput or base_tp
            drop_ratio = max(0.0, (ewma_tp - throughput_mbps) / base_tp)
            tp_factor = min(1.0, max(0.0, (drop_ratio - 0.15) / 0.70))
            score += 20.0 * tp_factor

        # Flapping contribution (weight 0.10)
        flap_factor = min(1.0, state.flap_count / FLAP_COUNT_THRESHOLD)
        score += 10.0 * flap_factor

        return round(min(100.0, score), 1)

    def _compute_trend(self, state: LinkState) -> str:
        """Compute trend from the last 10 risk scores in the buffer."""
        recent = list(state.buffer)[-10:]
        if len(recent) < 4:
            return "stable"
        scores = [s.risk_score for s in recent]
        n = len(scores)
        x_mean = (n - 1) / 2.0
        y_mean = sum(scores) / n
        numerator = sum((i - x_mean) * (scores[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        if denominator == 0:
            return "stable"
        slope = numerator / denominator
        if slope > 1.5:
            return "degrading"
        if slope < -1.5:
            return "recovering"
        return "stable"

    def get_state(self, link_id: str) -> Optional[LinkState]:
        return self._link_states.get(link_id)

    def get_all_link_ids(self) -> List[str]:
        return list(self._link_states.keys())

    def get_snapshot(self) -> List[Dict[str, Any]]:
        """Return current risk score + trend for all tracked links."""
        return self.get_risk_snapshot()

    def get_risk_snapshot(
        self, baselines: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Return current risk score, trend, EWMA metrics, and Theil-Sen ETA predictions."""
        bl = baselines or self.baselines
        result: List[Dict[str, Any]] = []

        for link_id, state in self._link_states.items():
            if not state.buffer:
                continue
            latest = state.buffer[-1]

            measurements = [s.to_measurement(link_id) for s in state.buffer]
            prediction = predict_link(link_id, measurements, baselines=bl)

            entry: Dict[str, Any] = {
                "link_id": link_id,
                "connectivity_ok": latest.connectivity_ok,
                "packet_loss_pct": latest.packet_loss_pct,
                "latency_ms": latest.latency_ms,
                "throughput_mbps": latest.throughput_mbps,
                "data_source": latest.data_source,
                "risk_score": state.risk_score,
                "trend": state.trend,
                "alert_level": state.alert_level,
                "flap_count": state.flap_count,
                "ewma_latency_ms": (
                    round(state.ewma_latency, 2)
                    if state.ewma_latency is not None
                    else None
                ),
                "ewma_loss_pct": (
                    round(state.ewma_loss, 2)
                    if state.ewma_loss is not None
                    else None
                ),
                "ewma_throughput_mbps": (
                    round(state.ewma_throughput, 2)
                    if state.ewma_throughput is not None
                    else None
                ),
                "predicted_eta_minutes": None,
                "prediction_confidence": None,
                "prediction_r2": None,
                "predicted_eta_min_minutes": None,
                "predicted_eta_max_minutes": None,
            }

            if prediction is not None:
                entry["predicted_eta_minutes"] = prediction["predicted_eta_minutes"]
                entry["prediction_confidence"] = prediction["prediction_confidence"]
                entry["prediction_r2"] = prediction["prediction_r2"]
                entry["predicted_eta_min_minutes"] = prediction.get(
                    "predicted_eta_min_minutes"
                )
                entry["predicted_eta_max_minutes"] = prediction.get(
                    "predicted_eta_max_minutes"
                )

            result.append(entry)

        return sorted(result, key=lambda x: x["risk_score"], reverse=True)

    def get_link_history(self, link_id: str, n: int = 50) -> List[Dict[str, Any]]:
        """Return last N samples for a link as serializable dicts."""
        state = self._link_states.get(link_id)
        if not state:
            return []
        samples = list(state.buffer)[-n:]
        return [
            {
                "tick": s.tick,
                "timestamp_utc": s.timestamp_utc,
                "latency_ms": s.latency_ms,
                "packet_loss_pct": s.packet_loss_pct,
                "throughput_mbps": s.throughput_mbps,
                "connectivity_ok": s.connectivity_ok,
                "risk_score": s.risk_score,
                "trend": s.trend,
                "alert_level": s.alert_level,
            }
            for s in samples
        ]

    def detect_cascade(self, threshold_risk: float = 60.0, window: int = 2) -> bool:
        """Return True if 2+ links simultaneously exceed risk threshold in last `window` ticks."""
        count = 0
        for state in self._link_states.values():
            recent = list(state.buffer)[-window:]
            if any(s.risk_score >= threshold_risk for s in recent):
                count += 1
            if count >= 2:
                return True
        return False

    def detect_flapping_links(self) -> List[str]:
        """Return link_ids where flap count exceeds FLAP_COUNT_THRESHOLD."""
        return [
            lid
            for lid, state in self._link_states.items()
            if state.flap_count >= FLAP_COUNT_THRESHOLD
        ]


# ── Module-level singleton ────────────────────────────────────────────────────
_ts_store_instance: Optional[TimeSeriesStore] = None


def get_time_series_store() -> TimeSeriesStore:
    """Return the shared TimeSeriesStore singleton."""
    global _ts_store_instance
    if _ts_store_instance is None:
        _ts_store_instance = TimeSeriesStore()
    return _ts_store_instance
