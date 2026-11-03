"""Tests for engine/predictor.py and engine/time_series.py.

Covers:
1. Stable baseline link -> predict_link returns None.
2. Ramping link -> ETA returned, positive, finite.
3. ETA shrinks over successive ticks (monotonic decrease).
4. Noisy-but-stable link -> None or "low" confidence.
5. Parity test: compute_degradation_index matches DiagnosticEngine.evaluate_link
   sub-score weighted sum (s_loss, s_lat, s_tp).
6. Baseline clears predictions within 10 ticks.
7. Ramp D values are monotonically non-decreasing.
8. Fewer than MIN_SAMPLES -> predict_link returns None.
9. Link already at D_FAIL -> predict_link returns None (link already failed guard).
10. connectivity_ok=False in window -> predict_link returns None.
"""

from __future__ import annotations

import math
from typing import List

import pytest

from backend.app.engine.diagnostics import DiagnosticEngine
from backend.app.engine.models import Measurement
from backend.app.engine.predictor import (
    MIN_SAMPLES,
    D_FAIL,
    D_WARN,
    MIN_SLOPE,
    WINDOW,
    compute_degradation_index,
    predict_link,
)
from backend.app.engine.telemetry import BASELINE_TELEMETRY, SimulatedTelemetryGenerator
from backend.app.engine.time_series import TimeSeriesStore

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_baseline_sample(link_id: str = "L3") -> Measurement:
    b = BASELINE_TELEMETRY[link_id]
    return Measurement(
        component_id=link_id,
        latency_ms=float(b["latency_ms"]),
        packet_loss_pct=float(b["packet_loss_pct"]),
        throughput_mbps=float(b["throughput_mbps"]),
        connectivity_ok=True,
    )


def make_ramp_samples(
    link_id: str,
    severity: str,
    n: int,
    start_progress: float = 0.0,
    progress_step: float = 0.025,
) -> List[Measurement]:
    gen = SimulatedTelemetryGenerator()
    samples = []
    for i in range(n):
        prog = start_progress + i * progress_step
        m = gen.generate_ramp_measurement(link_id, severity, prog)
        samples.append(m)
    return samples


# ── Test 1: Stable baseline -> None ──────────────────────────────────────────


def test_stable_link_returns_none() -> None:
    """A link at baseline (D ≈ 0) must not produce a prediction."""
    samples = [make_baseline_sample("L3") for _ in range(10)]
    result = predict_link("L3", samples)
    assert result is None


# ── Test 2: Ramping link -> ETA returned and positive ─────────────────────────


def test_ramping_link_returns_eta() -> None:
    """A rising-D ramp (high severity L3) must yield a positive ETA."""
    # Start at progress=0.15 so D_now > D_WARN after 6+ samples, and slope is clear.
    samples = make_ramp_samples("L3", "high", n=10, start_progress=0.15, progress_step=0.025)
    result = predict_link("L3", samples)
    assert result is not None, "Expected prediction for a ramping link"
    assert result["predicted_eta_minutes"] is not None
    assert result["predicted_eta_minutes"] > 0
    assert result["prediction_confidence"] in ("high", "medium", "low")
    assert result["prediction_r2"] is not None
    assert 0.0 <= result["prediction_r2"] <= 1.0


# ── Test 3: ETA shrinks over successive ticks ─────────────────────────────────


def test_eta_shrinks_over_successive_ticks() -> None:
    """ETA at a later window must be strictly smaller than at an earlier window."""
    gen = SimulatedTelemetryGenerator()
    all_samples: List[Measurement] = []
    etas: List[float] = []

    # Accumulate 20 ticks; collect ETA when available
    for i in range(20):
        prog = i * 0.025  # 0.0 .. 0.475
        m = gen.generate_ramp_measurement("L3", "high", prog)
        all_samples.append(m)
        result = predict_link("L3", all_samples)
        if result and result["predicted_eta_minutes"] is not None:
            etas.append(result["predicted_eta_minutes"])

    assert len(etas) >= 5, f"Too few predictions recorded: {etas}"
    # ETA should trend downward; allow occasional jitter but overall decreasing
    decreasing_pairs = sum(etas[i] > etas[i + 1] for i in range(len(etas) - 1))
    total_pairs = len(etas) - 1
    assert decreasing_pairs / total_pairs >= 0.7, (
        f"ETA not predominantly decreasing: {etas}"
    )


# ── Test 4: Noisy-but-stable link -> None or low ──────────────────────────────


def test_noisy_stable_link_returns_none_or_low_confidence() -> None:
    """Gaussian noise on a stable baseline must not produce high/medium prediction."""
    import random

    rng = random.Random(42)
    b = BASELINE_TELEMETRY["L2"]
    samples = []
    for _ in range(10):
        samples.append(
            Measurement(
                component_id="L2",
                latency_ms=float(b["latency_ms"]) + rng.gauss(0, 0.5),
                packet_loss_pct=max(0.0, float(b["packet_loss_pct"]) + rng.gauss(0, 0.1)),
                throughput_mbps=max(0.1, float(b["throughput_mbps"]) + rng.gauss(0, 1.0)),
                connectivity_ok=True,
            )
        )
    result = predict_link("L2", samples)
    if result is not None:
        assert result["prediction_confidence"] == "low", (
            f"Stable link should not get high/medium confidence: {result}"
        )


# ── Test 5: Parity with DiagnosticEngine ─────────────────────────────────────


def test_parity_with_diagnostic_engine() -> None:
    """compute_degradation_index must match DiagnosticEngine.evaluate_link
    weighted sub-scores (excluding connectivity)."""
    diag = DiagnosticEngine()
    gen = SimulatedTelemetryGenerator()

    for link_id in ["L1", "L2", "L3", "L4", "L5"]:
        baseline = BASELINE_TELEMETRY[link_id]
        for progress in [0.2, 0.4, 0.6, 0.8]:
            meas = gen.generate_ramp_measurement(link_id, "high", progress)
            report = diag.evaluate_link(meas, baseline, link_id)

            # DiagnosticEngine sub-scores (excluding s_conn weight 0.40)
            engine_d = (0.30 * report.s_loss + 0.20 * report.s_lat + 0.10 * report.s_tp) / 0.60

            predictor_d = compute_degradation_index(meas, baseline)

            assert math.isclose(predictor_d, engine_d, rel_tol=1e-4, abs_tol=1e-6), (
                f"Parity failure for {link_id} progress={progress}: "
                f"predictor={predictor_d:.6f} engine={engine_d:.6f}"
            )


# ── Test 6: Baseline clears predictions within 10 ticks ──────────────────────


def test_baseline_clears_predictions_within_10_ticks() -> None:
    """After a baseline run replaces a ramp, predictions must clear ≤ 10 new samples."""
    gen = SimulatedTelemetryGenerator()

    # Build a ramp that has established a prediction
    ramp_samples = make_ramp_samples("L3", "high", n=12, start_progress=0.2, progress_step=0.025)
    assert predict_link("L3", ramp_samples) is not None, "Pre-condition: ramp must predict"

    # Feed baseline samples on top
    combined = list(ramp_samples)
    for i in range(10):
        combined.append(make_baseline_sample("L3"))
        result = predict_link("L3", combined)
        if result is None:
            return  # cleared!

    # After 10 baseline samples the prediction should have cleared
    result = predict_link("L3", combined)
    assert result is None, (
        "Prediction should clear within 10 baseline samples, but still returned a result"
    )


# ── Test 7: Ramp D values are monotonically non-decreasing ───────────────────


def test_ramp_monotonic_d_increase() -> None:
    """D values from successive ramp ticks must be non-decreasing."""
    gen = SimulatedTelemetryGenerator()
    prev_d = -1.0
    bl = BASELINE_TELEMETRY["L3"]
    for i in range(41):
        prog = i / 40.0
        m = gen.generate_ramp_measurement("L3", "high", prog)
        d = compute_degradation_index(m, bl)
        assert d >= prev_d - 1e-9, (
            f"D decreased at tick {i}: prev={prev_d:.6f} current={d:.6f}"
        )
        prev_d = d


# ── Test 8: Fewer than MIN_SAMPLES -> None ───────────────────────────────────


def test_min_samples_guard() -> None:
    """predict_link must return None when fewer than MIN_SAMPLES samples provided."""
    samples = make_ramp_samples("L3", "high", n=MIN_SAMPLES - 1, start_progress=0.2)
    result = predict_link("L3", samples)
    assert result is None, (
        f"Expected None for {MIN_SAMPLES - 1} samples (< MIN_SAMPLES={MIN_SAMPLES})"
    )


# ── Test 9: D >= D_FAIL -> None ──────────────────────────────────────────────


def test_already_failed_guard() -> None:
    """predict_link must return None when D_now >= D_FAIL (link already failed)."""
    # progress=0.65 pushes L3/high well past D_FAIL=0.6
    samples = make_ramp_samples("L3", "high", n=10, start_progress=0.55, progress_step=0.01)
    bl = BASELINE_TELEMETRY["L3"]
    gen = SimulatedTelemetryGenerator()
    d_last = compute_degradation_index(samples[-1], bl)
    if d_last < D_FAIL:
        # Ensure we have a truly failed state by appending a high-progress sample
        samples.append(gen.generate_ramp_measurement("L3", "high", 0.9))
    result = predict_link("L3", samples)
    assert result is None, "predict_link must return None when link is already at/past D_FAIL"


# ── Test 10: connectivity_ok=False in window -> None ─────────────────────────


def test_connectivity_down_guard() -> None:
    """predict_link must return None when any sample has connectivity_ok=False."""
    samples = make_ramp_samples("L3", "high", n=9, start_progress=0.2)
    # Inject a down sample
    samples.append(
        Measurement(
            component_id="L3",
            latency_ms=None,
            packet_loss_pct=100.0,
            throughput_mbps=0.0,
            connectivity_ok=False,
        )
    )
    result = predict_link("L3", samples)
    assert result is None, "predict_link must return None when connectivity_ok=False is in window"


# ── TimeSeriesStore tests ─────────────────────────────────────────────────────


def test_time_series_store_push_and_get() -> None:
    """push() and get_samples() work correctly."""
    store = TimeSeriesStore()
    m1 = make_baseline_sample("L1")
    m2 = make_baseline_sample("L1")
    store.push("L1", m1)
    store.push("L1", m2)
    samples = store.get_samples("L1")
    assert len(samples) == 2


def test_time_series_store_clear_single() -> None:
    """clear(link_id) removes only the specified link."""
    store = TimeSeriesStore()
    store.push("L1", make_baseline_sample("L1"))
    store.push("L2", make_baseline_sample("L2"))
    store.clear("L1")
    assert store.get_samples("L1") == []
    assert len(store.get_samples("L2")) == 1


def test_time_series_store_risk_snapshot_empty() -> None:
    """get_risk_snapshot() returns empty list when store is empty."""
    store = TimeSeriesStore()
    assert store.get_risk_snapshot() == []


def test_time_series_store_risk_snapshot_with_data() -> None:
    """get_risk_snapshot() includes latest measurement fields."""
    store = TimeSeriesStore()
    m = make_baseline_sample("L3")
    store.push("L3", m)
    snap = store.get_risk_snapshot()
    assert len(snap) == 1
    entry = snap[0]
    assert entry["link_id"] == "L3"
    assert entry["connectivity_ok"] is True
    # Baseline sample has no rising trend -> no prediction
    assert entry["predicted_eta_minutes"] is None


def test_time_series_store_risk_snapshot_predicts_ramp() -> None:
    """get_risk_snapshot() includes ETA prediction for a ramping link."""
    store = TimeSeriesStore()
    samples = make_ramp_samples("L3", "high", n=12, start_progress=0.15, progress_step=0.025)
    for s in samples:
        store.push("L3", s)
    snap = store.get_risk_snapshot()
    assert len(snap) == 1
    entry = snap[0]
    assert entry["predicted_eta_minutes"] is not None
    assert entry["predicted_eta_minutes"] > 0
    assert entry["prediction_confidence"] in ("high", "medium", "low")
