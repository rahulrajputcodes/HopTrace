"""Tests for realistic fault families with seeded stochastic noise (Task 1).

Covers:
1. Determinism: same seed produces identical measurements.
2. ramp_linear with short (20), medium (40), and long (80) ticks.
3. ramp_accelerating: quadratic degradation curve.
4. step_with_noise: baseline before step, full fault after.
5. rain_fade on 60 GHz link L7: loss/latency burst that recovers.
6. diurnal_load: cyclic load without packet loss (healthy variation).
7. flapping_precursor: growing variance then link drop.
8. stable_noisy: heavy noise on healthy baseline.
"""

from __future__ import annotations

import pytest

from backend.app.engine.models import Measurement
from backend.app.engine.telemetry import (
    BASELINE_TELEMETRY,
    EXTENDED_BASELINE_TELEMETRY,
    SimulatedTelemetryGenerator,
)


def test_seeded_stochastic_determinism() -> None:
    """Same seed and parameters must produce exact identical measurements."""
    gen = SimulatedTelemetryGenerator()
    m1 = gen.generate_fault_scenario_sample("ramp_linear", "L3", tick=10, seed=42)
    m2 = gen.generate_fault_scenario_sample("ramp_linear", "L3", tick=10, seed=42)
    assert m1.latency_ms == m2.latency_ms
    assert m1.packet_loss_pct == m2.packet_loss_pct
    assert m1.throughput_mbps == m2.throughput_mbps
    assert m1.connectivity_ok == m2.connectivity_ok


def test_different_seeds_produce_different_jitter() -> None:
    """Different seeds must yield distinct stochastic noise values."""
    gen = SimulatedTelemetryGenerator()
    m1 = gen.generate_fault_scenario_sample("ramp_linear", "L3", tick=10, seed=42)
    m2 = gen.generate_fault_scenario_sample("ramp_linear", "L3", tick=10, seed=99)
    # Even if means are identical, jitter should differ
    assert (m1.latency_ms != m2.latency_ms) or (m1.throughput_mbps != m2.throughput_mbps)


def test_ramp_linear_lengths() -> None:
    """Short (20), medium (40), and long (80) ramps reach full severity at different rates."""
    gen = SimulatedTelemetryGenerator()
    # At tick 20: short ramp should be near 100% progressed, while long should be near 25%
    m_short = gen.generate_fault_scenario_sample("ramp_linear", "L3", tick=20, seed=1, ramp_length="short")
    m_long = gen.generate_fault_scenario_sample("ramp_linear", "L3", tick=20, seed=1, ramp_length="long")

    assert m_short.packet_loss_pct is not None and m_long.packet_loss_pct is not None
    assert m_short.packet_loss_pct > m_long.packet_loss_pct


def test_ramp_accelerating_progression() -> None:
    """Quadratic ramp shows smaller change early on and steeper change later."""
    gen = SimulatedTelemetryGenerator()
    b = BASELINE_TELEMETRY["L3"]
    m0 = gen.generate_fault_scenario_sample("ramp_accelerating", "L3", tick=0, seed=5)
    m10 = gen.generate_fault_scenario_sample("ramp_accelerating", "L3", tick=10, seed=5)
    m20 = gen.generate_fault_scenario_sample("ramp_accelerating", "L3", tick=20, seed=5)
    m40 = gen.generate_fault_scenario_sample("ramp_accelerating", "L3", tick=40, seed=5)

    base_loss = float(b["packet_loss_pct"])
    # (10/40)^2 = 0.0625, (20/40)^2 = 0.25, (40/40)^2 = 1.0
    delta_first_half = (m20.packet_loss_pct or 0.0) - (m0.packet_loss_pct or 0.0)
    delta_second_half = (m40.packet_loss_pct or 0.0) - (m20.packet_loss_pct or 0.0)
    assert delta_second_half > delta_first_half


def test_step_with_noise() -> None:
    """Step fault has normal metrics before tick 15, and elevated fault after."""
    gen = SimulatedTelemetryGenerator()
    b = BASELINE_TELEMETRY["L3"]
    m_before = gen.generate_fault_scenario_sample("step_with_noise", "L3", tick=14, seed=10)
    m_after = gen.generate_fault_scenario_sample("step_with_noise", "L3", tick=16, seed=10)

    assert (m_before.packet_loss_pct or 0.0) < 5.0
    assert (m_after.packet_loss_pct or 0.0) > 10.0


def test_rain_fade_recovers_on_l7() -> None:
    """Rain fade on 60 GHz link L7 peaks during event and recovers afterwards."""
    gen = SimulatedTelemetryGenerator()
    b = EXTENDED_BASELINE_TELEMETRY["L7"]
    m_pre = gen.generate_fault_scenario_sample("rain_fade", "L7", tick=5, seed=12)
    m_peak = gen.generate_fault_scenario_sample("rain_fade", "L7", tick=18, seed=12)
    m_post = gen.generate_fault_scenario_sample("rain_fade", "L7", tick=30, seed=12)

    base_lat = float(b["latency_ms"])
    assert (m_peak.latency_ms or 0.0) > (m_pre.latency_ms or 0.0) + 10.0
    # Recovers back to near baseline
    assert abs((m_post.latency_ms or 0.0) - base_lat) < 5.0


def test_diurnal_load_no_packet_loss() -> None:
    """Diurnal load cycle fluctuates latency/throughput but maintains zero/nominal loss."""
    gen = SimulatedTelemetryGenerator()
    for t in [0, 15, 30, 45, 60]:
        m = gen.generate_fault_scenario_sample("diurnal_load", "L1", tick=t, seed=20)
        assert m.packet_loss_pct is not None
        assert m.packet_loss_pct < 1.0
        assert m.connectivity_ok is True


def test_flapping_precursor_drops() -> None:
    """Flapping precursor has increasing variance then drops connectivity at tick 35."""
    gen = SimulatedTelemetryGenerator()
    m_early = gen.generate_fault_scenario_sample("flapping_precursor", "L3", tick=10, seed=33)
    m_late = gen.generate_fault_scenario_sample("flapping_precursor", "L3", tick=36, seed=33)

    assert m_early.connectivity_ok is True
    assert m_late.connectivity_ok is False
    assert m_late.packet_loss_pct == 100.0


def test_stable_noisy_healthy() -> None:
    """Stable noisy link remains connectivity_ok and has zero-mean noise."""
    gen = SimulatedTelemetryGenerator()
    m = gen.generate_fault_scenario_sample("stable_noisy", "L2", tick=5, seed=77)
    assert m.connectivity_ok is True
    assert m.latency_ms is not None
    assert m.latency_ms > 0.0
