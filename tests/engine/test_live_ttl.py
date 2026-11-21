"""Unit and integration tests for Task A1: Honest live path, TTL, and freshness semantics."""

from datetime import datetime, timedelta, timezone
import pytest

from app.config import settings
from app.engine.diagnostics import DiagnosticEngine
from app.engine.facade import get_engine, get_freshness, ingest_live_measurements
from app.engine.models import Measurement, NetworkTopology


@pytest.fixture(autouse=True)
def clean_live_state():
    """Ensure engine live state is clean before and after each test."""
    engine = get_engine()
    engine.clear_live_measurements()
    engine.close_open_incidents()
    yield
    engine.clear_live_measurements()
    engine.close_open_incidents()


def test_freshness_transitions_live_mode(monkeypatch):
    """Test TTL transitions: live -> stale -> no_data in live mode."""
    monkeypatch.setattr(settings, "data_mode", "live")
    monkeypatch.setattr(settings, "live_ttl_seconds", 30)

    engine = get_engine()
    t0 = datetime.now(timezone.utc)

    # 1. Never seen link in live mode -> no_data
    freshness, last_seen = engine.get_freshness("L1", now=t0)
    assert freshness == "no_data"
    assert last_seen is None

    # Ingest a measurement at t0
    m = Measurement(
        component_id="L1",
        timestamp_utc=t0.isoformat(),
        latency_ms=15.0,
        packet_loss_pct=0.0,
        throughput_mbps=100.0,
        connectivity_ok=True,
    )
    engine.ingest_live_measurements([m])

    # 2. Within TTL (e.g. 10s later) -> live
    t_live = t0 + timedelta(seconds=10)
    freshness, last_seen = engine.get_freshness("L1", now=t_live)
    assert freshness == "live"
    assert last_seen == t0.isoformat()

    # Boundary: age == 30s -> live
    t_boundary = t0 + timedelta(seconds=30)
    freshness, _ = engine.get_freshness("L1", now=t_boundary)
    assert freshness == "live"

    # 3. Beyond TTL but within 3x TTL (e.g. 60s later) -> stale
    t_stale = t0 + timedelta(seconds=60)
    freshness, last_seen = engine.get_freshness("L1", now=t_stale)
    assert freshness == "stale"
    assert last_seen == t0.isoformat()

    # 4. Beyond 3x TTL (e.g. 95s later) -> no_data
    t_nodata = t0 + timedelta(seconds=95)
    freshness, last_seen = engine.get_freshness("L1", now=t_nodata)
    assert freshness == "no_data"
    assert last_seen == t0.isoformat()


def test_freshness_transitions_demo_mode(monkeypatch):
    """Test freshness transitions in demo mode: link never seen -> simulated, older -> simulated."""
    monkeypatch.setattr(settings, "data_mode", "demo")
    monkeypatch.setattr(settings, "live_ttl_seconds", 30)

    engine = get_engine()
    t0 = datetime.now(timezone.utc)

    # Never seen link in demo mode -> simulated
    freshness, last_seen = engine.get_freshness("L2", now=t0)
    assert freshness == "simulated"
    assert last_seen is None

    # Ingest measurement at t0
    m = Measurement(
        component_id="L2",
        timestamp_utc=t0.isoformat(),
        latency_ms=2.0,
        packet_loss_pct=0.0,
        throughput_mbps=80.0,
        connectivity_ok=True,
    )
    engine.ingest_live_measurements([m])

    # Within TTL -> live
    freshness, _ = engine.get_freshness("L2", now=t0 + timedelta(seconds=15))
    assert freshness == "live"

    # Expired in demo mode -> simulated
    t_expired = t0 + timedelta(seconds=100)
    freshness, last_seen = engine.get_freshness("L2", now=t_expired)
    assert freshness == "simulated"
    assert last_seen == t0.isoformat()


def test_live_mode_never_fabricates_unmeasured_links(monkeypatch):
    """When DATA_MODE=live, ingest_live_measurements uses ONLY real data and never baseline fill."""
    monkeypatch.setattr(settings, "data_mode", "live")
    monkeypatch.setattr(settings, "live_ttl_seconds", 30)

    engine = get_engine()
    t0 = datetime.now(timezone.utc)

    # Report ONLY for L1
    m1 = Measurement(
        component_id="L1",
        timestamp_utc=t0.isoformat(),
        latency_ms=15.0,
        packet_loss_pct=0.0,
        throughput_mbps=100.0,
        connectivity_ok=True,
    )
    res = engine.ingest_live_measurements([m1])

    # Run should contain only L1 in live mode (no fabricated L2-L14)
    run = engine.get_run_measurements(res.run_id)
    assert run is not None
    active_comp_ids = {m.component_id for m in run.measurements}
    assert active_comp_ids == {"L1"}
    assert "L2" not in active_comp_ids


def test_demo_mode_overlays_onto_baseline(monkeypatch):
    """When DATA_MODE=demo, unmeasured links are filled from baseline with noise."""
    monkeypatch.setattr(settings, "data_mode", "demo")

    engine = get_engine()
    t0 = datetime.now(timezone.utc)

    m1 = Measurement(
        component_id="L1",
        timestamp_utc=t0.isoformat(),
        latency_ms=15.0,
        packet_loss_pct=0.0,
        throughput_mbps=100.0,
        connectivity_ok=True,
    )
    res = engine.ingest_live_measurements([m1])

    run = engine.get_run_measurements(res.run_id)
    assert run is not None
    # All 14 topology links are present via baseline simulation
    assert len(run.measurements) >= 14


def test_backfill_does_not_open_incident_or_refresh_received_at(monkeypatch):
    """Backfilled samples (> LIVE_TTL_SECONDS old) go to history only, not live state."""
    monkeypatch.setattr(settings, "data_mode", "live")
    monkeypatch.setattr(settings, "live_ttl_seconds", 30)

    engine = get_engine()
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(seconds=120)

    # An old measurement indicating complete failure
    failed_backfill = Measurement(
        component_id="L1",
        timestamp_utc=old_time.isoformat(),
        latency_ms=None,
        packet_loss_pct=100.0,
        throughput_mbps=0.0,
        connectivity_ok=False,
    )

    res = engine.ingest_live_measurements([failed_backfill])

    # Must NOT open an incident
    assert res.incident_id is None
    assert engine.get_latest_open_incident() is None

    # Must NOT update live freshness
    freshness, last_seen = engine.get_freshness("L1", now=now)
    assert freshness == "no_data"
    assert last_seen is None


def test_all_no_data_network_produces_no_incident():
    """An all-no-data network produces status closed, no open incident, and no 100% confidence."""
    diag = DiagnosticEngine()
    topo = NetworkTopology(nodes=[], links=[], data_source="live")
    from app.engine.topology import get_default_topology
    topo = get_default_topology()

    incident = diag.diagnose(measurements=[], topology=topo)
    assert incident.status == "closed"
    assert incident.suspected_component_id is None
    assert incident.confidence_score is None  # Never falsely claims 1.0 confidence
    assert "no telemetry data" in incident.summary.lower() or "unmonitored" in incident.summary.lower()


def test_provides_concept_skips_missing_throughput():
    """Measurements that do not provide throughput (e.g. path_probe) are not penalized for missing throughput."""
    diag = DiagnosticEngine()
    m_probe = Measurement(
        component_id="L1",
        latency_ms=15.0,
        packet_loss_pct=0.0,
        throughput_mbps=None,
        connectivity_ok=True,
        data_source="path_probe",
    )
    base = {"latency_ms": 15.0, "packet_loss_pct": 0.0, "throughput_mbps": 100.0, "connectivity_ok": True}
    rep = diag.evaluate_link(m_probe, base, "L1")

    # Missing metrics count should be 0 because throughput is not provided by path_probe
    assert rep.missing_metrics_count == 0
    assert not any(e.metric == "throughput_mbps" and e.status == "missing" for e in rep.evidence)
