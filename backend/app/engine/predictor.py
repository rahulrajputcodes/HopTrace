"""Predictive fault analytics for HopTrace.

Computes a per-link baseline-relative Degradation Index (D) from observed
telemetry samples and fits a linear trend to predict time-to-failure.

Design principles:
- Pure Python: no external dependencies beyond the standard library.
- Prediction is based on observed sample ORDER INDEX (not the tick field),
  so it works correctly for both lab runs and the streaming loop.
- The diagnostic engine is never queried and never receives the scenario
  name or target link ID.  Predictions come from observed samples only.
- data_source stays "simulated" throughout.

Documented Constants
--------------------
D_FAIL = 0.6
    Degradation index level at which the diagnostic engine opens a fault
    incident for a medium-to-high severity fault.  A prediction is issued
    when the trend is heading toward this threshold.

D_WARN = 0.25
    Minimum D value (on the most recent sample) below which no prediction is
    issued — the link is still too healthy to meaningfully forecast failure.

MIN_SLOPE = 0.002
    Minimum Theil-Sen slope (D-units per sample index) required before a
    prediction is issued.  Slopes below this threshold indicate a stable or
    near-stable trend where an ETA would be unreliable.

SIM_MINUTES_PER_TICK = 2.0
    Simulated minutes represented by a single streaming tick.  Used to
    convert the predicted ETA from tick-units to minutes for the operator.

MAX_HORIZON_MINUTES = 120.0
    Maximum forecast horizon in simulated minutes. Beyond this, return no ETA
    (prediction_confidence None).

WINDOW = 10
    Maximum number of most-recent samples used for prediction.

MIN_SAMPLES = 6
    Minimum number of samples required before any prediction is attempted.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from backend.app.engine.models import Measurement
from backend.app.engine.telemetry import BASELINE_TELEMETRY

# ── Frozen Predictor Configuration (Tuned on Dev Seeds 0–99) ───────────────────
# Tuned strictly on development seeds (0–99) and evaluated on untouched test seeds (1000–1199).
# Any change here requires re-running benchmarks.predictive.run and updating docs/predictive-method.md.

D_FAIL: float = 0.6
"""Degradation index level at which a fault incident is expected to open (failure threshold)."""

D_WARN: float = 0.05
"""Minimum D on the most-recent sample before a prediction is issued (warning threshold).
Set conservatively low (0.05) so predictions appear before the diagnostic engine
opens an incident, providing 8–10 minutes advance warning over the incident detector.
"""

MIN_SLOPE: float = 0.002
"""Minimum Theil-Sen slope (D per sample index) to issue a prediction."""

SIM_MINUTES_PER_TICK: float = 2.0
"""Simulated minutes per streaming tick (used to convert ETA ticks to minutes)."""

MAX_HORIZON_MINUTES: float = 120.0
"""Maximum forecast horizon in simulated minutes. Beyond this, return no ETA."""

WINDOW: int = 10
"""Sliding window size (most-recent telemetry samples) used for the trend fit."""

MIN_SAMPLES: int = 6
"""Minimum samples required in the window before predict_link() returns a prediction."""

CONFIDENCE_R2_HIGH: float = 0.8
"""R² threshold for high-confidence predictions (also requires n >= WINDOW)."""

CONFIDENCE_R2_MEDIUM: float = 0.5
"""R² threshold for medium-confidence predictions."""


# ── Degradation index ─────────────────────────────────────────────────────────

def compute_degradation_index(
    measurement: Measurement,
    baseline: Dict[str, float | bool],
) -> float:
    """Compute the baseline-relative Degradation Index D ∈ [0, 1].

    Re-implements the loss/latency/throughput sub-scores from
    DiagnosticEngine.evaluate_link with identical normalisation formulas,
    then combines them using the partial weights that exclude connectivity
    (connectivity=False means the link has *already* failed, not that it is
    *about to* fail, so it is excluded from the trend predictor).

    Formula:
        D = (0.30 * s_loss + 0.20 * s_lat + 0.10 * s_tp) / 0.60

    Sub-scores (each clamped to [0, 1]):
        s_loss = min(1, delta_loss / 25.0)           if delta_loss > 1.0
        s_lat  = min(1, delta_lat / 150.0)           if delta_lat > 10.0
        s_tp   = min(1, (drop_pct - 0.15) / 0.70)   if drop_pct > 0.15

    This matches DiagnosticEngine.evaluate_link exactly (parity test in
    tests/engine/test_predictor.py::test_parity_with_diagnostic_engine).
    """
    base_loss = float(baseline.get("packet_loss_pct", 0.0))
    base_lat = float(baseline.get("latency_ms", 20.0))
    base_tp = float(baseline.get("throughput_mbps", 50.0))

    # s_loss
    s_loss = 0.0
    if measurement.packet_loss_pct is not None:
        delta_loss = max(0.0, measurement.packet_loss_pct - base_loss)
        if delta_loss > 1.0:
            s_loss = min(1.0, delta_loss / 25.0)

    # s_lat
    s_lat = 0.0
    if measurement.latency_ms is not None:
        delta_lat = max(0.0, measurement.latency_ms - base_lat)
        if delta_lat > 10.0:
            s_lat = min(1.0, delta_lat / 150.0)

    # s_tp
    s_tp = 0.0
    if measurement.throughput_mbps is not None and base_tp > 0:
        drop_pct = max(0.0, (base_tp - measurement.throughput_mbps) / base_tp)
        if drop_pct > 0.15:
            s_tp = min(1.0, (drop_pct - 0.15) / 0.70)

    # Normalise by the combined weight of the three included terms (0.60)
    d = (0.30 * s_loss + 0.20 * s_lat + 0.10 * s_tp) / 0.60
    return round(min(1.0, max(0.0, d)), 6)


# ── Theil-Sen slope ───────────────────────────────────────────────────────────

def _pairwise_theil_sen_slopes(xs: List[float], ys: List[float]) -> List[float]:
    """Compute all pairwise slopes (y2-y1)/(x2-x1) for i < j, returned sorted."""
    slopes: List[float] = []
    n = len(xs)
    for i in range(n):
        for j in range(i + 1, n):
            dx = xs[j] - xs[i]
            if dx != 0.0:
                slopes.append((ys[j] - ys[i]) / dx)
    slopes.sort()
    return slopes


def _theil_sen_slope(xs: List[float], ys: List[float]) -> float:
    """Compute the Theil-Sen estimator slope (median of pairwise slopes).

    Returns 0.0 when fewer than two distinct x values exist.
    """
    slopes = _pairwise_theil_sen_slopes(xs, ys)
    if not slopes:
        return 0.0
    mid = len(slopes) // 2
    if len(slopes) % 2 == 1:
        return slopes[mid]
    return (slopes[mid - 1] + slopes[mid]) / 2.0


def _r_squared(xs: List[float], ys: List[float], slope: float) -> float:
    """Compute R² for the Theil-Sen fit (intercept determined by medians)."""
    n = len(xs)
    if n < 2:
        return 0.0
    x_med = sorted(xs)[n // 2]
    y_med = sorted(ys)[n // 2]
    intercept = y_med - slope * x_med
    y_mean = sum(ys) / n
    ss_res = sum((ys[i] - (slope * xs[i] + intercept)) ** 2 for i in range(n))
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    if ss_tot == 0.0:
        return 1.0 if ss_res == 0.0 else 0.0
    return max(0.0, 1.0 - ss_res / ss_tot)


# ── Main prediction function ──────────────────────────────────────────────────

def predict_link(
    link_id: str,
    samples: List[Measurement],
    baselines: Optional[Dict[str, Dict[str, float | bool]]] = None,
) -> Optional[Dict[str, Optional[float | str]]]:
    """Predict time-to-failure for a single link from its recent telemetry.

    Parameters
    ----------
    link_id:
        The link identifier (e.g. "L3").
    samples:
        All samples available for this link, in chronological order.
        Uses the last min(WINDOW, len(samples)) entries.
        Position in this slice is used as the x-axis (index 0, 1, 2, …),
        NOT the tick field — this keeps lab runs and the streaming loop
        on a consistent scale.
    baselines:
        Optional override for baseline metrics.  Defaults to BASELINE_TELEMETRY.

    Returns
    -------
    A dict with keys:
        predicted_eta_minutes     : float | None
        prediction_confidence     : str | None   ("high", "medium", "low")
        prediction_r2             : float | None
        predicted_eta_min_minutes : float | None
        predicted_eta_max_minutes : float | None
    or None if the input does not satisfy preconditions (not enough samples,
    link already failed, trend too flat, link already at/past D_FAIL, or
    predicted ETA exceeds MAX_HORIZON_MINUTES).

    Guard conditions that return None
    ----------------------------------
    - Fewer than MIN_SAMPLES samples.
    - Any sample has connectivity_ok=False (link is already down).
    - D_now >= D_FAIL (link has already crossed the failure threshold).
    - Theil-Sen slope <= MIN_SLOPE (trend is too flat to predict reliably).
    - predicted_eta_minutes > MAX_HORIZON_MINUTES (beyond predictable horizon).
    """
    bl = baselines or BASELINE_TELEMETRY
    baseline = bl.get(link_id, {})

    window = samples[-WINDOW:] if len(samples) >= WINDOW else samples
    n = len(window)

    if n < MIN_SAMPLES:
        return None

    # Guard: link already physically down
    if any(not s.connectivity_ok for s in window):
        return None

    # Compute D for each sample in the window
    d_values = [compute_degradation_index(s, baseline) for s in window]
    d_now = d_values[-1]

    # Guard: link has already crossed the failure threshold
    if d_now >= D_FAIL:
        return None

    # Guard: link is too healthy to warn about
    if d_now < D_WARN:
        # Still compute slope; if slope is meaningful re-evaluate, but
        # per spec we also require d_now >= D_WARN to issue a warning.
        return None

    xs = [float(i) for i in range(n)]
    slopes = _pairwise_theil_sen_slopes(xs, d_values)
    if not slopes:
        return None

    mid = len(slopes) // 2
    slope = slopes[mid] if len(slopes) % 2 == 1 else (slopes[mid - 1] + slopes[mid]) / 2.0

    # Guard: trend is too flat
    if slope <= MIN_SLOPE:
        return None

    eta_ticks = (D_FAIL - d_now) / slope
    predicted_eta_minutes = round(eta_ticks * SIM_MINUTES_PER_TICK, 1)

    # Guard: beyond maximum horizon
    if predicted_eta_minutes > MAX_HORIZON_MINUTES:
        return None

    # 20th and 80th percentiles of pairwise Theil-Sen slopes
    m = len(slopes)
    p20_idx = int(round(0.20 * (m - 1)))
    p80_idx = int(round(0.80 * (m - 1)))
    s_20 = slopes[p20_idx]
    s_80 = slopes[p80_idx]

    # Steeper slope (s_80) gives lower bound ETA; gentler slope (s_20) gives upper bound ETA
    if s_80 > 0:
        eta_min_ticks = (D_FAIL - d_now) / s_80
        predicted_eta_min_minutes = max(0.0, round(eta_min_ticks * SIM_MINUTES_PER_TICK, 1))
    else:
        predicted_eta_min_minutes = predicted_eta_minutes

    if s_20 > MIN_SLOPE:
        eta_max_ticks = (D_FAIL - d_now) / s_20
        predicted_eta_max_minutes = min(
            MAX_HORIZON_MINUTES, round(eta_max_ticks * SIM_MINUTES_PER_TICK, 1)
        )
    else:
        predicted_eta_max_minutes = MAX_HORIZON_MINUTES

    predicted_eta_min_minutes = min(predicted_eta_min_minutes, predicted_eta_minutes)
    predicted_eta_max_minutes = max(predicted_eta_max_minutes, predicted_eta_minutes)

    r2 = _r_squared(xs, d_values, slope)

    if r2 >= CONFIDENCE_R2_HIGH and n >= WINDOW:
        confidence: str = "high"
    elif r2 >= CONFIDENCE_R2_MEDIUM:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "predicted_eta_minutes": predicted_eta_minutes,
        "prediction_confidence": confidence,
        "prediction_r2": round(r2, 4),
        "predicted_eta_min_minutes": predicted_eta_min_minutes,
        "predicted_eta_max_minutes": predicted_eta_max_minutes,
    }
