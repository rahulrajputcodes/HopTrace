"""Comparators for benchmarking the HopTrace predictive fault method.

Four baseline detection mechanisms evaluated against the Theil-Sen predictor:
1. StaticThresholdComparator:
   Conventional threshold alert: packet loss >= 5% OR latency >= 2x baseline
   OR throughput <= 50% baseline OR loss of connectivity.
2. DiagnosticEngineComparator:
   Our explainable diagnostic engine evaluating single-link anomaly score >= 0.10.
3. NaiveOLSPredictor:
   Unweighted Ordinary Least Squares (OLS) linear regression on D over the same
   10-sample sliding window.
4. EWMARiskScoreComparator:
   Exponentially Weighted Moving Average (EWMA) tracking latency/throughput
   deviations; triggers when composite risk >= 45.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from backend.app.engine.diagnostics import DiagnosticEngine
from backend.app.engine.models import Measurement
from backend.app.engine.predictor import (
    D_FAIL,
    D_WARN,
    MIN_SAMPLES,
    MIN_SLOPE,
    WINDOW,
    compute_degradation_index,
)


class StaticThresholdComparator:
    """Conventional rule-based threshold alert."""

    def __init__(self, baseline: Dict[str, float | bool]) -> None:
        self.base_lat = float(baseline.get("latency_ms", 20.0))
        self.base_loss = float(baseline.get("packet_loss_pct", 0.0))
        self.base_tp = float(baseline.get("throughput_mbps", 50.0))

    def evaluate(self, sample: Measurement) -> bool:
        """Returns True if any conventional static threshold is breached."""
        if not sample.connectivity_ok:
            return True
        if sample.packet_loss_pct is not None and sample.packet_loss_pct >= 5.0:
            return True
        if sample.latency_ms is not None and sample.latency_ms >= 2.0 * self.base_lat:
            return True
        if sample.throughput_mbps is not None and sample.throughput_mbps <= 0.5 * self.base_tp:
            return True
        return False


class DiagnosticEngineComparator:
    """Diagnostic engine anomaly score evaluator."""

    def __init__(self, baseline: Dict[str, float | bool], link_id: str) -> None:
        self.engine = DiagnosticEngine()
        self.baseline = baseline
        self.link_id = link_id

    def evaluate(self, sample: Measurement) -> bool:
        """Returns True if the diagnostic engine triggers an incident (score >= 0.10)."""
        report = self.engine.evaluate_link(sample, self.baseline, self.link_id)
        return report.score >= 0.10 or not sample.connectivity_ok


class NaiveOLSPredictor:
    """Naive Ordinary Least Squares linear regression on D."""

    def __init__(self, baseline: Dict[str, float | bool]) -> None:
        self.baseline = baseline

    def evaluate(self, window: List[Measurement]) -> Optional[float]:
        """Returns predicted ETA in ticks, or None if no warning."""
        n = len(window)
        if n < MIN_SAMPLES:
            return None
        if any(not s.connectivity_ok for s in window):
            return None

        d_values = [compute_degradation_index(s, self.baseline) for s in window]
        d_now = d_values[-1]

        if d_now >= D_FAIL or d_now < D_WARN:
            return None

        # OLS slope calculation
        xs = [float(i) for i in range(n)]
        x_mean = sum(xs) / n
        y_mean = sum(d_values) / n

        num = sum((xs[i] - x_mean) * (d_values[i] - y_mean) for i in range(n))
        den = sum((xs[i] - x_mean) ** 2 for i in range(n))

        if den == 0.0:
            return None
        slope = num / den

        if slope <= MIN_SLOPE:
            return None

        eta_ticks = (D_FAIL - d_now) / slope
        return eta_ticks if eta_ticks > 0 else None


class EWMARiskScoreComparator:
    """EWMA-relative deviation tracker."""

    def __init__(self, baseline: Dict[str, float | bool], alpha: float = 0.20) -> None:
        self.alpha = alpha
        self.base_lat = float(baseline.get("latency_ms", 20.0))
        self.base_tp = float(baseline.get("throughput_mbps", 50.0))
        self.ewma_lat = self.base_lat
        self.ewma_tp = self.base_tp

    def evaluate(self, sample: Measurement) -> bool:
        """Updates EWMA and returns True if composite risk score >= 45."""
        if not sample.connectivity_ok:
            return True

        lat = sample.latency_ms if sample.latency_ms is not None else self.base_lat
        tp = sample.throughput_mbps if sample.throughput_mbps is not None else self.base_tp
        loss = sample.packet_loss_pct if sample.packet_loss_pct is not None else 0.0

        # Update EWMA
        self.ewma_lat = (1.0 - self.alpha) * self.ewma_lat + self.alpha * lat
        self.ewma_tp = (1.0 - self.alpha) * self.ewma_tp + self.alpha * tp

        # Relative deviations against EWMA
        lat_dev = max(0.0, lat - self.ewma_lat)
        tp_drop = max(0.0, self.ewma_tp - tp)

        s_loss = min(1.0, loss / 20.0)
        s_lat = min(1.0, lat_dev / 50.0)
        s_tp = min(1.0, tp_drop / 30.0) if self.base_tp > 0 else 0.0

        risk = min(100.0, (40.0 * s_loss + 35.0 * s_lat + 25.0 * s_tp))
        return risk >= 45.0
