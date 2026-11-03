"""Tests for CSV Replay Adapter (Task 5).

Covers:
1. Replay adapter sets data_source="measured" on all parsed measurements.
2. Replay feeds TimeSeriesStore correctly.
3. Replaying healthy live probe series produces no false alarms (ETA is None).
4. Replaying degrading measured series correctly triggers predictive ETA.
"""

from __future__ import annotations

import io
import tempfile
import pytest

from backend.app.engine.models import Measurement
from backend.app.engine.replay import ReplayAdapter
from backend.app.engine.time_series import TimeSeriesStore


SAMPLE_HEALTHY_CSV = """timestamp,link_id,latency_ms,packet_loss_pct,throughput_mbps,connectivity_ok
2026-11-03T10:00:00Z,L3,25.1,0.0,35.0,true
2026-11-03T10:00:03Z,L3,25.4,0.0,34.8,true
2026-11-03T10:00:06Z,L3,24.9,0.0,35.2,true
2026-11-03T10:00:09Z,L3,25.2,0.0,34.9,true
2026-11-03T10:00:12Z,L3,25.0,0.0,35.1,true
2026-11-03T10:00:15Z,L3,25.3,0.0,35.0,true
2026-11-03T10:00:18Z,L3,24.8,0.0,35.0,true
2026-11-03T10:00:21Z,L3,25.1,0.0,35.1,true
"""

SAMPLE_DEGRADING_CSV = """timestamp,link_id,latency_ms,packet_loss_pct,throughput_mbps,connectivity_ok
2026-11-03T10:00:00Z,L3,35.0,2.0,30.0,true
2026-11-03T10:00:03Z,L3,45.0,4.0,27.0,true
2026-11-03T10:00:06Z,L3,55.0,6.0,24.0,true
2026-11-03T10:00:09Z,L3,65.0,8.0,21.0,true
2026-11-03T10:00:12Z,L3,75.0,10.0,18.0,true
2026-11-03T10:00:15Z,L3,85.0,12.0,15.0,true
2026-11-03T10:00:18Z,L3,95.0,14.0,12.0,true
2026-11-03T10:00:21Z,L3,105.0,16.0,9.0,true
"""


def test_replay_sets_measured_data_source() -> None:
    """All measurements parsed via ReplayAdapter must have data_source='measured'."""
    adapter = ReplayAdapter()
    stream = io.StringIO(SAMPLE_HEALTHY_CSV)
    measurements = list(adapter.parse_csv_stream(stream))
    assert len(measurements) == 8
    for m in measurements:
        assert m.data_source == "measured"
        assert m.component_id == "L3"
        assert m.connectivity_ok is True


def test_replay_healthy_series_no_alarm() -> None:
    """Replaying healthy live telemetry produces no false predictions."""
    store = TimeSeriesStore()
    adapter = ReplayAdapter(store=store)

    with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as tf:
        tf.write(SAMPLE_HEALTHY_CSV)
        tf.flush()
        records = adapter.replay_file(tf.name, feed_store=True)

    assert len(records) == 8
    for r in records:
        assert r["data_source"] == "measured"
        # Healthy series should produce no warning ETA
        assert r["predicted_eta_minutes"] is None


def test_replay_degrading_series_predicts_eta() -> None:
    """Replaying a degrading live series triggers predictions with data_source='measured'."""
    store = TimeSeriesStore()
    adapter = ReplayAdapter(store=store)

    with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as tf:
        tf.write(SAMPLE_DEGRADING_CSV)
        tf.flush()
        records = adapter.replay_file(tf.name, feed_store=True)

    assert len(records) == 8
    # Later records in the degrading series should produce non-None ETA
    late_records = [r for r in records[-3:] if r["predicted_eta_minutes"] is not None]
    assert len(late_records) > 0
    assert late_records[0]["data_source"] == "measured"
    assert late_records[0]["predicted_eta_minutes"] > 0
