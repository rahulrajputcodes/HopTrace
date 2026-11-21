"""Benchmark execution harness and metrics aggregation for HopTrace Predictive Fault AI.

Evaluates:
- Theil-Sen predictor (HopTrace)
- Static threshold comparator
- Diagnostic engine incident comparator
- Naive OLS linear regression predictor
- EWMA risk score comparator

Calculates:
- Detection rate & Miss rate
- Lead time vs failure and vs each comparator (median + IQR)
- False alarms per link-day (720 ticks at 2.0 min/tick)
- ETA error (MAE and relative error)
- Prediction interval range coverage (20th-80th percentile band)
- Confidence band stratification (high, medium, low)
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.app.engine.models import Measurement
from backend.app.engine.predictor import (
    D_FAIL,
    SIM_MINUTES_PER_TICK,
    WINDOW,
    compute_degradation_index,
    predict_link,
)
from backend.app.engine.telemetry import (
    BASELINE_TELEMETRY,
    EXTENDED_BASELINE_TELEMETRY,
    SimulatedTelemetryGenerator,
)
from backend.benchmarks.predictive.comparators import (
    DiagnosticEngineComparator,
    EWMARiskScoreComparator,
    NaiveOLSPredictor,
    StaticThresholdComparator,
)

TICKS_PER_LINK_DAY = 720  # 24 hours at 2 minutes per tick
MAX_SIM_TICKS = 60


def _median_and_iqr(values: List[float]) -> Tuple[float, float]:
    """Returns (median, IQR) for a list of values."""
    if not values:
        return 0.0, 0.0
    med = statistics.median(values)
    if len(values) < 2:
        return round(med, 2), 0.0
    try:
        q1, _, q3 = statistics.quantiles(values, n=4)
        iqr = q3 - q1
    except Exception:
        iqr = 0.0
    return round(med, 2), round(iqr, 2)


@dataclass
class SingleRunResult:
    scenario: str
    link_id: str
    severity: str
    noise_level: str
    seed: int
    ramp_length: str
    is_failing_scenario: bool
    failure_tick: Optional[int] = None
    first_warning_tick: Optional[int] = None
    first_warning_eta_min: Optional[float] = None
    static_alert_tick: Optional[int] = None
    diag_alert_tick: Optional[int] = None
    ols_alert_tick: Optional[int] = None
    ewma_alert_tick: Optional[int] = None
    warning_count: int = 0
    eta_errors_min: List[float] = field(default_factory=list)
    eta_rel_errors: List[float] = field(default_factory=list)
    range_hits: int = 0
    range_total: int = 0
    confidence_counts: Dict[str, int] = field(default_factory=lambda: {"high": 0, "medium": 0, "low": 0})
    confidence_errors: Dict[str, List[float]] = field(default_factory=lambda: {"high": [], "medium": [], "low": []})


def run_single_simulation(
    scenario: str,
    link_id: str,
    seed: int,
    severity: str = "medium",
    noise_level: str = "normal",
    ramp_length: str = "medium",
    max_ticks: int = MAX_SIM_TICKS,
) -> SingleRunResult:
    """Simulates a link under a given scenario configuration."""
    generator = SimulatedTelemetryGenerator()
    baseline = EXTENDED_BASELINE_TELEMETRY.get(link_id, BASELINE_TELEMETRY.get(link_id, {}))

    static_comp = StaticThresholdComparator(baseline)
    diag_comp = DiagnosticEngineComparator(baseline, link_id)
    ols_comp = NaiveOLSPredictor(baseline)
    ewma_comp = EWMARiskScoreComparator(baseline)

    is_failing = scenario in ("ramp_linear", "ramp_accelerating", "step_with_noise", "flapping_precursor")

    result = SingleRunResult(
        scenario=scenario,
        link_id=link_id,
        severity=severity,
        noise_level=noise_level,
        seed=seed,
        ramp_length=ramp_length,
        is_failing_scenario=is_failing,
    )

    history: List[Measurement] = []
    first_failure_tick: Optional[int] = None

    # Pre-pass to find actual failure tick if failing scenario
    for t in range(max_ticks):
        sample = generator.generate_fault_scenario_sample(
            scenario=scenario,
            link_id=link_id,
            tick=t,
            seed=seed,
            severity=severity,
            ramp_length=ramp_length,
            noise_level=noise_level,
        )
        d_val = compute_degradation_index(sample, baseline)
        if (d_val >= D_FAIL or not sample.connectivity_ok) and first_failure_tick is None:
            first_failure_tick = t
            break

    result.failure_tick = first_failure_tick

    # Main evaluation pass
    for t in range(max_ticks):
        sample = generator.generate_fault_scenario_sample(
            scenario=scenario,
            link_id=link_id,
            tick=t,
            seed=seed,
            severity=severity,
            ramp_length=ramp_length,
            noise_level=noise_level,
        )
        history.append(sample)
        recent_window = history[-WINDOW:]

        # Comparators evaluation
        if result.static_alert_tick is None and static_comp.evaluate(sample):
            result.static_alert_tick = t
        if result.diag_alert_tick is None and diag_comp.evaluate(sample):
            result.diag_alert_tick = t
        if result.ols_alert_tick is None and ols_comp.evaluate(recent_window) is not None:
            result.ols_alert_tick = t
        if result.ewma_alert_tick is None and ewma_comp.evaluate(sample):
            result.ewma_alert_tick = t

        # Predictor evaluation
        pred = predict_link(link_id, recent_window, baselines=EXTENDED_BASELINE_TELEMETRY)
        if pred is not None and pred["predicted_eta_minutes"] is not None:
            result.warning_count += 1
            if result.first_warning_tick is None:
                result.first_warning_tick = t
                result.first_warning_eta_min = pred["predicted_eta_minutes"]

            conf = pred.get("prediction_confidence") or "low"
            result.confidence_counts[conf] = result.confidence_counts.get(conf, 0) + 1

            # Range and accuracy evaluation (only if link actually fails in the future)
            if first_failure_tick is not None and t < first_failure_tick:
                actual_remaining_ticks = first_failure_tick - t
                actual_remaining_min = actual_remaining_ticks * SIM_MINUTES_PER_TICK

                pred_min = float(pred["predicted_eta_minutes"])
                mae = abs(pred_min - actual_remaining_min)
                result.eta_errors_min.append(mae)
                if actual_remaining_min > 0:
                    result.eta_rel_errors.append(mae / actual_remaining_min)

                result.confidence_errors[conf].append(mae)

                # Check range coverage [eta_min, eta_max]
                eta_min = pred.get("predicted_eta_min_minutes")
                eta_max = pred.get("predicted_eta_max_minutes")
                if eta_min is not None and eta_max is not None:
                    result.range_total += 1
                    if eta_min <= actual_remaining_min <= eta_max:
                        result.range_hits += 1

    return result


def aggregate_metrics(runs: List[SingleRunResult]) -> Dict[str, Any]:
    """Computes summary statistics across a set of simulation runs."""
    failing_runs = [r for r in runs if r.is_failing_scenario and r.failure_tick is not None]
    healthy_runs = [r for r in runs if not r.is_failing_scenario]

    # 1. Detection & Miss Rate
    detected = sum(1 for r in failing_runs if r.first_warning_tick is not None and r.first_warning_tick < r.failure_tick)  # type: ignore[operator]
    total_failing = len(failing_runs)
    detection_rate = (detected / total_failing * 100.0) if total_failing > 0 else 100.0
    miss_rate = 100.0 - detection_rate

    # 2. Lead Time before Failure
    lead_times_fail_ticks = [
        (r.failure_tick - r.first_warning_tick)  # type: ignore[operator]
        for r in failing_runs
        if r.first_warning_tick is not None and r.first_warning_tick < r.failure_tick  # type: ignore[operator]
    ]
    lead_times_fail_min = [t * SIM_MINUTES_PER_TICK for t in lead_times_fail_ticks]
    fail_med_ticks, fail_iqr_ticks = _median_and_iqr([float(x) for x in lead_times_fail_ticks])
    fail_med_min, fail_iqr_min = _median_and_iqr(lead_times_fail_min)

    # 3. Lead Time vs Comparators
    def comp_lead_time(attr_name: str) -> Tuple[float, float, float, float]:
        ticks = []
        for r in failing_runs:
            c_tick = getattr(r, attr_name)
            if r.first_warning_tick is not None and c_tick is not None:
                ticks.append(float(c_tick - r.first_warning_tick))
        med_t, iqr_t = _median_and_iqr(ticks)
        med_m, iqr_m = _median_and_iqr([x * SIM_MINUTES_PER_TICK for x in ticks])
        return med_t, iqr_t, med_m, iqr_m

    static_med_t, static_iqr_t, static_med_m, static_iqr_m = comp_lead_time("static_alert_tick")
    diag_med_t, diag_iqr_t, diag_med_m, diag_iqr_m = comp_lead_time("diag_alert_tick")
    ols_med_t, ols_iqr_t, ols_med_m, ols_iqr_m = comp_lead_time("ols_alert_tick")
    ewma_med_t, ewma_iqr_t, ewma_med_m, ewma_iqr_m = comp_lead_time("ewma_alert_tick")

    # 4. False Alarms on Healthy Links
    total_healthy_ticks = len(healthy_runs) * MAX_SIM_TICKS
    total_false_alarms = sum(r.warning_count for r in healthy_runs)
    false_alarms_per_link_day = (
        (total_false_alarms / total_healthy_ticks * TICKS_PER_LINK_DAY) if total_healthy_ticks > 0 else 0.0
    )

    # 5. ETA Error & Range Coverage
    all_mae: List[float] = []
    all_rel: List[float] = []
    total_hits = sum(r.range_hits for r in failing_runs)
    total_range = sum(r.range_total for r in failing_runs)

    for r in failing_runs:
        all_mae.extend(r.eta_errors_min)
        all_rel.extend(r.eta_rel_errors)

    mae_med, mae_iqr = _median_and_iqr(all_mae)
    rel_med, rel_iqr = _median_and_iqr(all_rel)
    range_coverage = (total_hits / total_range * 100.0) if total_range > 0 else 0.0

    # 6. Confidence Band Stratification
    conf_summary: Dict[str, Dict[str, Any]] = {}
    for c in ("high", "medium", "low"):
        errs = []
        for r in failing_runs:
            errs.extend(r.confidence_errors.get(c, []))
        c_med, c_iqr = _median_and_iqr(errs)
        conf_summary[c] = {
            "count": len(errs),
            "mae_median_min": c_med,
            "mae_iqr_min": c_iqr,
        }

    return {
        "runs_count": len(runs),
        "failing_runs_count": total_failing,
        "healthy_runs_count": len(healthy_runs),
        "detection_rate_pct": round(detection_rate, 1),
        "miss_rate_pct": round(miss_rate, 1),
        "lead_time_vs_failure": {
            "median_ticks": fail_med_ticks,
            "iqr_ticks": fail_iqr_ticks,
            "median_min": fail_med_min,
            "iqr_min": fail_iqr_min,
        },
        "lead_time_vs_static": {
            "median_ticks": static_med_t,
            "iqr_ticks": static_iqr_t,
            "median_min": static_med_m,
            "iqr_min": static_iqr_m,
        },
        "lead_time_vs_diagnostic_engine": {
            "median_ticks": diag_med_t,
            "iqr_ticks": diag_iqr_t,
            "median_min": diag_med_m,
            "iqr_min": diag_iqr_m,
        },
        "lead_time_vs_naive_ols": {
            "median_ticks": ols_med_t,
            "iqr_ticks": ols_iqr_t,
            "median_min": ols_med_m,
            "iqr_min": ols_iqr_m,
        },
        "lead_time_vs_ewma_risk": {
            "median_ticks": ewma_med_t,
            "iqr_ticks": ewma_iqr_t,
            "median_min": ewma_med_m,
            "iqr_min": ewma_iqr_m,
        },
        "false_alarms_per_link_day": round(false_alarms_per_link_day, 2),
        "eta_mae_min": {"median": mae_med, "iqr": mae_iqr},
        "eta_rel_error": {"median": round(rel_med, 3), "iqr": round(rel_iqr, 3)},
        "range_coverage_pct": round(range_coverage, 1),
        "confidence_bands": conf_summary,
    }
