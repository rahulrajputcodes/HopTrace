"""CSV Replay Adapter for real-world network telemetry (Task 5).

Reads CSV recordings of live telemetry with columns:
  timestamp, link_id, latency_ms, packet_loss_pct, throughput_mbps, connectivity_ok

Converts rows into Measurement objects with data_source="measured", feeding
the same HopTrace predictive engine.

CRITICAL INTEGRITY RULE:
All measurements produced by this replay path are explicitly marked with
data_source="measured". Simulated and measured telemetry are never conflated.
"""

from __future__ import annotations

import csv
import io
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

from backend.app.engine.models import Measurement
from backend.app.engine.predictor import predict_link
from backend.app.engine.time_series import TimeSeriesStore, get_time_series_store


class ReplayAdapter:
    """Reads live network telemetry from CSV and feeds the HopTrace predictor."""

    def __init__(self, store: Optional[TimeSeriesStore] = None) -> None:
        self.store = store or get_time_series_store()

    def parse_csv_stream(self, file_obj: io.TextIOBase) -> Iterator[Measurement]:
        """Parses a CSV stream into Measurement objects with data_source='measured'."""
        reader = csv.DictReader(file_obj)
        for row in reader:
            link_id = row.get("link_id", "").strip()
            if not link_id:
                continue

            ts = row.get("timestamp", "").strip() or datetime.now(timezone.utc).isoformat()

            lat_raw = row.get("latency_ms", "").strip()
            lat_ms = float(lat_raw) if lat_raw and lat_raw.lower() not in ("none", "null", "") else None

            loss_raw = row.get("packet_loss_pct", "").strip()
            loss_pct = float(loss_raw) if loss_raw and loss_raw.lower() not in ("none", "null", "") else None

            tp_raw = row.get("throughput_mbps", "").strip()
            tp_mbps = float(tp_raw) if tp_raw and tp_raw.lower() not in ("none", "null", "") else None

            conn_raw = row.get("connectivity_ok", "true").strip().lower()
            conn_ok = conn_raw in ("true", "1", "yes", "t")

            yield Measurement(
                component_id=link_id,
                timestamp_utc=ts,
                latency_ms=lat_ms,
                packet_loss_pct=loss_pct,
                throughput_mbps=tp_mbps,
                connectivity_ok=conn_ok,
                data_source="measured",
            )

    def replay_file(self, csv_path: str, feed_store: bool = True) -> List[Dict[str, Any]]:
        """Replays telemetry from a CSV file and returns per-tick predictor evaluations.

        Parameters
        ----------
        csv_path:
            Path to the telemetry CSV file.
        feed_store:
            Whether to push measurements into the shared TimeSeriesStore.

        Returns
        -------
        A list of evaluation records for each row, showing whether the predictor
        issued a forecast on the measured data.
        """
        if not os.path.isfile(csv_path):
            raise FileNotFoundError(f"Replay CSV not found: {csv_path}")

        records: List[Dict[str, Any]] = []
        with open(csv_path, "r", encoding="utf-8") as f:
            for measurement in self.parse_csv_stream(f):
                if feed_store:
                    self.store.push(measurement.component_id, measurement)

                samples = self.store.get_samples(measurement.component_id)
                prediction = predict_link(measurement.component_id, samples)

                records.append({
                    "timestamp": measurement.timestamp_utc,
                    "link_id": measurement.component_id,
                    "latency_ms": measurement.latency_ms,
                    "packet_loss_pct": measurement.packet_loss_pct,
                    "throughput_mbps": measurement.throughput_mbps,
                    "connectivity_ok": measurement.connectivity_ok,
                    "data_source": measurement.data_source,
                    "predicted_eta_minutes": prediction["predicted_eta_minutes"] if prediction else None,
                    "prediction_confidence": prediction["prediction_confidence"] if prediction else None,
                })

        return records
