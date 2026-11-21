"""Unit tests for learned per-link dynamic baselines (EWMA with warm-up and clamp)."""

import pytest
from app.engine.baselines import BaselineProvider
from app.engine.diagnostics import DiagnosticEngine
from app.engine.models import Measurement


def test_baseline_warmup_returns_static_defaults():
    """BaselineProvider returns static defaults until warmup_samples (60) is reached."""
    provider = BaselineProvider(warmup_samples=60)
    static_l1 = provider.static_defaults["L1"]

    # Before any samples
    assert provider.sample_count("L1") == 0
    assert provider.is_warmed_up("L1") is False
    assert provider["L1"]["latency_ms"] == static_l1["latency_ms"]

    # Feed 59 healthy samples with different latency
    for _ in range(59):
        provider.update(
            link_id="L1",
            measurement=Measurement(
                component_id="L1",
                latency_ms=25.0,  # default is 15.0
                packet_loss_pct=0.0,
                throughput_mbps=100.0,
                connectivity_ok=True,
            ),
        )

    assert provider.sample_count("L1") == 59
    assert provider.is_warmed_up("L1") is False
    # Still returns static default during warm-up
    assert provider["L1"]["latency_ms"] == static_l1["latency_ms"]


def test_baseline_healthy_drift_updates_after_warmup():
    """After 60 healthy samples, baseline reflects learned EWMA."""
    provider = BaselineProvider(warmup_samples=60, ewma_alpha=0.30)
    static_l1 = provider.static_defaults["L1"]  # 15.0 ms

    # Feed 60 samples with steady 18.0 ms latency
    for _ in range(60):
        provider.update(
            link_id="L1",
            measurement=Measurement(
                component_id="L1",
                latency_ms=18.0,
                packet_loss_pct=0.0,
                throughput_mbps=100.0,
                connectivity_ok=True,
            ),
        )

    assert provider.sample_count("L1") == 60
    assert provider.is_warmed_up("L1") is True
    learned_lat = provider["L1"]["latency_ms"]
    # Should have converged close to 18.0 ms (within 0.5 ms)
    assert abs(learned_lat - 18.0) < 0.5
    assert learned_lat != static_l1["latency_ms"]


def test_baseline_resists_anomaly_poisoning():
    """Degraded or anomalous samples are rejected and do not corrupt the baseline."""
    provider = BaselineProvider(warmup_samples=60)
    static_l1 = provider.static_defaults["L1"]  # 15.0 ms

    # Warm up with 60 healthy samples
    for _ in range(60):
        provider.update(
            link_id="L1",
            measurement=Measurement(
                component_id="L1",
                latency_ms=15.0,
                packet_loss_pct=0.0,
                throughput_mbps=100.0,
                connectivity_ok=True,
            ),
        )

    lat_before = provider["L1"]["latency_ms"]

    # 1. Reject connectivity_ok = False
    res1 = provider.update(
        link_id="L1",
        measurement=Measurement(
            component_id="L1",
            latency_ms=200.0,
            packet_loss_pct=100.0,
            throughput_mbps=0.0,
            connectivity_ok=False,
        ),
    )
    assert res1 is False

    # 2. Reject packet_loss >= 5.0%
    res2 = provider.update(
        link_id="L1",
        measurement=Measurement(
            component_id="L1",
            latency_ms=50.0,
            packet_loss_pct=12.0,
            throughput_mbps=80.0,
            connectivity_ok=True,
        ),
    )
    assert res2 is False

    # 3. Reject anomaly_score >= detection_threshold
    res3 = provider.update(
        link_id="L1",
        measurement=Measurement(
            component_id="L1",
            latency_ms=60.0,
            packet_loss_pct=1.0,
            throughput_mbps=80.0,
            connectivity_ok=True,
        ),
        anomaly_score=0.25,
        detection_threshold=0.10,
    )
    assert res3 is False

    # Baseline remains unaffected
    assert provider["L1"]["latency_ms"] == lat_before
    assert provider.sample_count("L1") == 60


def test_baseline_clamp_limits_drift():
    """Learned baseline is clamped within ±50% of documented static default."""
    # L1 static latency is 15.0 ms -> clamp range is [7.5, 22.5]
    provider = BaselineProvider(warmup_samples=10, clamp_ratio=0.50)

    # Feed extremely high latency (but below loss/score filter)
    for _ in range(30):
        provider.update(
            link_id="L1",
            measurement=Measurement(
                component_id="L1",
                latency_ms=100.0,
                packet_loss_pct=0.0,
                throughput_mbps=100.0,
                connectivity_ok=True,
            ),
            anomaly_score=0.05,
        )

    # Must be clamped at 15.0 * 1.5 = 22.5 ms
    assert provider["L1"]["latency_ms"] == 22.5

    # Feed near-zero latency
    for _ in range(30):
        provider.update(
            link_id="L1",
            measurement=Measurement(
                component_id="L1",
                latency_ms=1.0,
                packet_loss_pct=0.0,
                throughput_mbps=100.0,
                connectivity_ok=True,
            ),
            anomaly_score=0.05,
        )

    # Must be clamped at 15.0 * 0.5 = 7.5 ms
    assert provider["L1"]["latency_ms"] == 7.5


def test_baseline_provider_dict_interface():
    """BaselineProvider behaves as a dict for DiagnosticEngine compatibility."""
    provider = BaselineProvider()

    assert "L1" in provider
    assert "UNKNOWN" not in provider
    assert len(provider) == 14
    assert list(provider.keys()) == list(provider.static_defaults.keys())
    assert provider.get("L1") is not None
    assert provider.get("UNKNOWN", {"default": 1}) == {"default": 1}

    items = dict(provider.items())
    assert "L1" in items
    assert items["L1"]["connectivity_ok"] is True


def test_diagnostic_engine_updates_baseline_on_healthy_run():
    """DiagnosticEngine automatically updates healthy links via BaselineProvider."""
    provider = BaselineProvider(warmup_samples=5)
    engine = DiagnosticEngine(baselines=provider)

    measurements = [
        Measurement(
            component_id=f"L{i}",
            latency_ms=15.0,
            packet_loss_pct=0.0,
            throughput_mbps=80.0,
            connectivity_ok=True,
        )
        for i in range(1, 15)
    ]

    # Run 5 healthy diagnoses
    for _ in range(5):
        inc = engine.diagnose(measurements=measurements)
        assert inc.status == "closed"

    # All 14 links must have sample_count == 5
    for i in range(1, 15):
        assert provider.sample_count(f"L{i}") == 5


def test_baseline_persistence_save_and_load():
    """Learned baselines survive in SQLite and restore into a new BaselineProvider instance."""
    import sqlite3
    from app.db.init import SCHEMA_SQL

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)

    # 1. Warm up provider1 with 60 samples for L1
    p1 = BaselineProvider(warmup_samples=60, auto_load=False)
    for _ in range(60):
        p1.update(
            link_id="L1",
            measurement=Measurement(
                component_id="L1",
                latency_ms=18.5,
                packet_loss_pct=0.0,
                throughput_mbps=95.0,
                connectivity_ok=True,
            ),
        )

    assert p1.is_warmed_up("L1") is True
    assert p1.sample_count("L1") == 60
    lat_learned = p1["L1"]["latency_ms"]

    # Save to SQLite
    saved = p1.save_to_db(conn=conn)
    assert saved >= 1

    # 2. Simulate server restart: create brand new p2 and load from DB
    p2 = BaselineProvider(warmup_samples=60, auto_load=False)
    assert p2.sample_count("L1") == 0
    assert p2.is_warmed_up("L1") is False

    loaded = p2.load_from_db(conn=conn)
    assert loaded >= 1
    assert p2.sample_count("L1") == 60
    assert p2.is_warmed_up("L1") is True
    assert p2["L1"]["latency_ms"] == lat_learned

    conn.close()
