"""Smoke test for the predictive benchmark harness (Task 2)."""

from __future__ import annotations

import pytest
from backend.benchmarks.predictive.runner import aggregate_metrics, run_single_simulation


def test_benchmark_runner_smoke() -> None:
    """Smoke test running 2 seeds across 2 scenarios to verify harness stability."""
    runs = []
    for seed in [1, 2]:
        for sc in ["ramp_linear", "stable_noisy"]:
            r = run_single_simulation(
                scenario=sc,
                link_id="L3",
                seed=seed,
                severity="medium",
                noise_level="low",
                max_ticks=25,
            )
            runs.append(r)

    metrics = aggregate_metrics(runs)
    assert metrics["runs_count"] == 4
    assert "detection_rate_pct" in metrics
    assert "lead_time_vs_failure" in metrics
    assert "false_alarms_per_link_day" in metrics
