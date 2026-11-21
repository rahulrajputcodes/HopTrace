"""Learned per-link dynamic baselines for HopTrace v2.

Maintains EWMA (Exponentially Weighted Moving Average) baselines for network links
observed during healthy operational periods, preventing false alerts from diurnal
or environmental drift while resisting poisoning from degradation anomalies.

Key behaviors:
- Warm-up threshold: returns static defaults until >= 60 healthy samples are observed.
- Selective update: updates ONLY on healthy samples (connectivity_ok=True,
  packet_loss < 5.0%, anomaly_score < detection_threshold).
- Drift protection: learned values are clamped within ±50% of documented static defaults.
- Dict-like interface: fully transparent drop-in replacement for baseline dict.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional, Tuple

from app.engine.telemetry import BASELINE_TELEMETRY


class BaselineProvider:
    """Dynamic baseline provider with EWMA learning and static fallback."""

    def __init__(
        self,
        static_defaults: Optional[Dict[str, Dict[str, float | bool]]] = None,
        ewma_alpha: float = 0.30,
        warmup_samples: int = 60,
        clamp_ratio: float = 0.50,
        auto_load: bool = False,
    ) -> None:
        self.static_defaults: Dict[str, Dict[str, float | bool]] = (
            copy.deepcopy(static_defaults) if static_defaults is not None else copy.deepcopy(BASELINE_TELEMETRY)
        )
        self.ewma_alpha = ewma_alpha
        self.warmup_samples = warmup_samples
        self.clamp_ratio = clamp_ratio
        self._updates_since_save = 0

        # State tracking: link_id -> metric -> float value
        self._learned_values: Dict[str, Dict[str, float]] = {}
        # Sample count tracking: link_id -> count of healthy samples observed
        self._sample_counts: Dict[str, int] = {}

        if auto_load:
            self.load_from_db()

    def reset(self) -> None:
        """Resets all learned state and sample counts."""
        self._learned_values.clear()
        self._sample_counts.clear()

    def reset_link(self, link_id: str) -> None:
        """Resets learned state for a specific link."""
        self._learned_values.pop(link_id, None)
        self._sample_counts.pop(link_id, None)

    def sample_count(self, link_id: str) -> int:
        """Returns the number of healthy samples observed for a link."""
        return self._sample_counts.get(link_id, 0)

    def is_warmed_up(self, link_id: str) -> bool:
        """Returns True if the link has observed >= warmup_samples healthy readings."""
        return self.sample_count(link_id) >= self.warmup_samples

    def _clamp_metric(self, metric: str, learned_val: float, default_val: float) -> float:
        """Clamps learned value within ±clamp_ratio (default ±50%) of static default."""
        if default_val > 0.0:
            min_v = default_val * (1.0 - self.clamp_ratio)
            max_v = default_val * (1.0 + self.clamp_ratio)
            return max(min_v, min(max_v, learned_val))
        else:
            # When default is 0.0 (e.g. baseline packet_loss_pct), permit healthy range [0.0, 2.5]
            return max(0.0, min(2.5, learned_val))

    def update(
        self,
        link_id: str,
        measurement: Any,
        anomaly_score: Optional[float] = None,
        detection_threshold: float = 0.10,
    ) -> bool:
        """Updates EWMA for a link if measurement meets strict health criteria.

        Returns True if sample was accepted and baseline updated, False otherwise.
        """
        # 1. Health gating: reject disconnected, degraded, or anomalous samples
        conn_ok = getattr(measurement, "connectivity_ok", True)
        if not conn_ok:
            return False

        loss = getattr(measurement, "packet_loss_pct", None)
        if loss is not None and loss >= 5.0:
            return False

        if anomaly_score is not None and anomaly_score >= detection_threshold:
            return False

        # 2. Extract metrics to update
        lat = getattr(measurement, "latency_ms", None)
        tp = getattr(measurement, "throughput_mbps", None)

        static_def = self.static_defaults.get(link_id, {
            "latency_ms": 20.0,
            "packet_loss_pct": 0.0,
            "throughput_mbps": 50.0,
            "connectivity_ok": True,
        })

        if link_id not in self._learned_values:
            self._learned_values[link_id] = {
                "latency_ms": float(static_def.get("latency_ms", 20.0)),
                "packet_loss_pct": float(static_def.get("packet_loss_pct", 0.0)),
                "throughput_mbps": float(static_def.get("throughput_mbps", 50.0)),
            }

        learned = self._learned_values[link_id]
        alpha = self.ewma_alpha

        # Update EWMA for available metrics
        if lat is not None:
            learned["latency_ms"] = (1.0 - alpha) * learned["latency_ms"] + alpha * float(lat)

        if loss is not None:
            learned["packet_loss_pct"] = (1.0 - alpha) * learned["packet_loss_pct"] + alpha * float(loss)

        if tp is not None:
            learned["throughput_mbps"] = (1.0 - alpha) * learned["throughput_mbps"] + alpha * float(tp)

        self._sample_counts[link_id] = self._sample_counts.get(link_id, 0) + 1
        self._updates_since_save += 1
        if self._updates_since_save >= 10:
            self._updates_since_save = 0
            self.save_to_db()
        return True

    def save_to_db(self, conn: Any = None) -> int:
        """Persists learned values and sample counts into SQLite."""
        close_conn = False
        if conn is None:
            try:
                from app.db.connection import get_db_connection
                conn = get_db_connection()
                close_conn = True
            except Exception:
                return 0

        now_iso = datetime.now(timezone.utc).isoformat()
        saved = 0
        try:
            for link_id, count in self._sample_counts.items():
                learned = self._learned_values.get(link_id, {})
                lat = learned.get("latency_ms")
                loss = learned.get("packet_loss_pct")
                tp = learned.get("throughput_mbps")
                conn.execute(
                    """
                    INSERT INTO learned_baselines (link_id, sample_count, latency_ms, packet_loss_pct, throughput_mbps, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(link_id) DO UPDATE SET
                        sample_count = excluded.sample_count,
                        latency_ms = excluded.latency_ms,
                        packet_loss_pct = excluded.packet_loss_pct,
                        throughput_mbps = excluded.throughput_mbps,
                        updated_at = excluded.updated_at;
                    """,
                    (link_id, count, lat, loss, tp, now_iso),
                )
                saved += 1
            conn.commit()
        except Exception:
            pass
        finally:
            if close_conn and conn is not None:
                conn.close()
        return saved

    def load_from_db(self, conn: Any = None) -> int:
        """Loads previously learned values and sample counts from SQLite."""
        close_conn = False
        if conn is None:
            try:
                from app.db.connection import get_db_connection
                conn = get_db_connection()
                close_conn = True
            except Exception:
                return 0

        loaded = 0
        try:
            cur = conn.execute(
                """
                SELECT link_id, sample_count, latency_ms, packet_loss_pct, throughput_mbps
                FROM learned_baselines;
                """
            )
            for row in cur.fetchall():
                link_id = row[0]
                count = row[1]
                lat = row[2]
                loss = row[3]
                tp = row[4]
                self._sample_counts[link_id] = count
                vals = {}
                if lat is not None:
                    vals["latency_ms"] = float(lat)
                if loss is not None:
                    vals["packet_loss_pct"] = float(loss)
                if tp is not None:
                    vals["throughput_mbps"] = float(tp)
                if vals:
                    self._learned_values[link_id] = vals
                loaded += 1
        except Exception:
            pass
        finally:
            if close_conn and conn is not None:
                conn.close()
        return loaded

    def get_baseline(self, link_id: str) -> Dict[str, float | bool]:
        """Returns baseline metrics dictionary for link_id.

        If healthy samples < warmup_samples (60), returns static defaults.
        If >= warmup_samples, returns EWMA values clamped to ±50% of static defaults.
        """
        static_def = self.static_defaults.get(link_id, {
            "latency_ms": 20.0,
            "packet_loss_pct": 0.0,
            "throughput_mbps": 50.0,
            "connectivity_ok": True,
        }).copy()

        if not self.is_warmed_up(link_id) or link_id not in self._learned_values:
            return static_def

        learned = self._learned_values[link_id]
        result: Dict[str, float | bool] = {
            "connectivity_ok": True,
        }

        for metric in ("latency_ms", "packet_loss_pct", "throughput_mbps"):
            def_val = float(static_def.get(metric, 0.0))
            if metric in learned:
                clamped = self._clamp_metric(metric, learned[metric], def_val)
                result[metric] = round(clamped, 2)
            else:
                result[metric] = def_val

        return result

    # ── Dict-like Transparent Interface ───────────────────────────────────────

    def __getitem__(self, link_id: str) -> Dict[str, float | bool]:
        return self.get_baseline(link_id)

    def get(self, link_id: str, default: Any = None) -> Any:
        if link_id in self.static_defaults or link_id in self._sample_counts:
            return self.get_baseline(link_id)
        return default

    def __contains__(self, link_id: str) -> bool:
        return link_id in self.static_defaults

    def __iter__(self) -> Iterator[str]:
        return iter(self.static_defaults)

    def __len__(self) -> int:
        return len(self.static_defaults)

    def keys(self) -> Any:
        return self.static_defaults.keys()

    def values(self) -> List[Dict[str, float | bool]]:
        return [self.get_baseline(k) for k in self.keys()]

    def items(self) -> List[Tuple[str, Dict[str, float | bool]]]:
        return [(k, self.get_baseline(k)) for k in self.keys()]


# Global singleton provider instance
_GLOBAL_BASELINE_PROVIDER: Optional[BaselineProvider] = None


def get_baseline_provider() -> BaselineProvider:
    """Returns the process-wide BaselineProvider singleton."""
    global _GLOBAL_BASELINE_PROVIDER
    if _GLOBAL_BASELINE_PROVIDER is None:
        _GLOBAL_BASELINE_PROVIDER = BaselineProvider(auto_load=True)
    return _GLOBAL_BASELINE_PROVIDER


def reset_baseline_provider() -> None:
    """Resets the process-wide BaselineProvider singleton."""
    global _GLOBAL_BASELINE_PROVIDER
    if _GLOBAL_BASELINE_PROVIDER is not None:
        _GLOBAL_BASELINE_PROVIDER.reset()
