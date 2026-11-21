"""Stable Python interface facade for the HopTrace Network Intelligence Engine.

Exposes stable, typed Python functions for backend services to consume:
- seed_topology()
- get_topology()
- run_scenario()
- get_incident_details()
- get_latest_incident()
- get_affected_subscribers()
- get_run_measurements()
- check_neo4j_health()
- ingest_live_measurements()
- get_live_measurements()
- clear_live_measurements()

Adheres strictly to docs/api-contract.md.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from .diagnostics import DiagnosticEngine
from .graph_store import InMemoryGraphStore, Neo4jGraphStore
from .models import (
    AffectedSubscribersResponse,
    EvidenceItem,
    IncidentDetails,
    Measurement,
    NetworkTopology,
    RunMeasurementsResponse,
    ScenarioRunResponse,
)
from .neo4j_client import get_neo4j_client
from .telemetry import RAMP_TICKS, SimulatedTelemetryGenerator


class HopTraceEngine:
    """Core coordinator for graph operations, telemetry simulations, and fault diagnostics."""

    def __init__(self, prefer_neo4j: bool = True) -> None:
        self.prefer_neo4j = prefer_neo4j
        self.in_memory_store = InMemoryGraphStore()
        self.neo4j_client = get_neo4j_client()
        self.neo4j_store = Neo4jGraphStore(client=self.neo4j_client)
        self.telemetry_generator = SimulatedTelemetryGenerator()
        self.diagnostic_engine = DiagnosticEngine()

        # In-memory stores for runs and incidents (shared with API layer)
        self._runs: Dict[str, RunMeasurementsResponse] = {}
        self._incidents: Dict[str, IncidentDetails] = {}
        self._incident_order: List[str] = []
        self._live_measurements: Dict[str, Any] = {}
        self._live_metadata: Dict[str, Dict[str, Any]] = {}

        # Ramp state for gradual_degradation scenario.
        # Cleared when a baseline run or any new scenario replaces it.
        self._ramp: Optional[Dict[str, Any]] = None  # keys: target_link_id, severity, start_tick
        self._tick_counter: int = 0  # monotonic tick counter shared with streaming loop

    def is_neo4j_available(self) -> bool:
        """Checks if live Neo4j database is accessible."""
        if not self.prefer_neo4j:
            return False
        health = self.neo4j_client.check_connection()
        return bool(health.get("connected", False))

    def get_active_store(self, force_in_memory: bool = False):
        """Returns the appropriate graph store (Neo4j if connected, else InMemory)."""
        if force_in_memory or not self.is_neo4j_available():
            return self.in_memory_store
        return self.neo4j_store

    # ── Ramp state management ────────────────────────────────────────────────

    def start_ramp(self, target_link_id: str, severity: str) -> None:
        """Starts a gradual_degradation ramp on the given link.

        Records the ramp parameters and the current tick as the start tick.
        Resets any previous ramp state.
        """
        self._ramp = {
            "target_link_id": target_link_id,
            "severity": severity,
            "start_tick": self._tick_counter,
        }

    def clear_ramp(self) -> None:
        """Clears ramp state.  Called when a baseline run or a new scenario replaces the ramp."""
        self._ramp = None

    def get_ramp_state(self) -> Optional[Dict[str, Any]]:
        """Returns the current ramp state dict or None if no ramp is active."""
        return self._ramp

    @property
    def ramp_state(self) -> Optional[Dict[str, Any]]:
        """Property returning the current ramp state dict or None."""
        return self._ramp

    def advance_ramp_tick(self) -> float:
        """Increments the internal tick counter and returns the current ramp progress.

        progress = min(1.0, ticks_since_start / RAMP_TICKS).
        Returns 0.0 if no ramp is active (for streaming loop convenience).
        """
        self._tick_counter += 1
        if self._ramp is None:
            return 0.0
        ticks_since_start = self._tick_counter - self._ramp["start_tick"]
        return min(1.0, ticks_since_start / RAMP_TICKS)

    def get_current_tick(self) -> int:
        """Returns the current monotonic tick counter."""
        return self._tick_counter

    def seed_topology(self, force_in_memory: bool = False) -> Dict[str, Any]:
        """Seeds the topology idempotently into the active store.

        Also always seeds the in-memory mirror for local fallback.
        """
        mem_res = self.in_memory_store.seed_topology()
        if not force_in_memory and self.is_neo4j_available():
            try:
                neo_res = self.neo4j_store.seed_topology()
                return neo_res
            except Exception as exc:
                return {
                    "status": "seeded_in_memory_fallback",
                    "nodes_count": mem_res["nodes_count"],
                    "links_count": mem_res["links_count"],
                    "subscribers_count": mem_res["subscribers_count"],
                    "neo4j_error": str(exc),
                }
        return mem_res

    def get_topology(self, force_in_memory: bool = False) -> NetworkTopology:
        """Retrieves the network topology from the active store."""
        store = self.get_active_store(force_in_memory=force_in_memory)
        return store.get_topology()

    def run_scenario(
        self,
        scenario: str = "baseline",
        target_link_id: Optional[str] = None,
        target_node_id: Optional[str] = None,
        severity: str = "medium",
        missing_link_ids: Optional[List[str]] = None,
        ambiguous_link_ids: Optional[List[str]] = None,
        force_in_memory: bool = False,
        ramp_progress: float = 0.0,
    ) -> ScenarioRunResponse:
        """Runs a network telemetry scenario and triggers fault localization.

        CRITICAL VALIDATION RULE:
        The diagnostic engine receives ONLY observed telemetry, baseline metrics,
        and topology. It NEVER receives target_link_id or scenario name.

        For gradual_degradation: ramp_progress controls how far along the ramp
        the current tick is. At 0 the link is at baseline; at 1.0 it matches
        full degrade_link severity. The caller (lab.py or the streaming loop)
        is responsible for computing progress from the ramp state.
        """
        # Clear ramp if a non-ramp scenario is explicitly run
        if scenario == "baseline":
            self.clear_ramp()

        run_id = f"run-{uuid.uuid4().hex[:8]}"

        # 1. Generate deterministic measurements
        measurements = self.telemetry_generator.generate_measurements(
            scenario=scenario,
            target_link_id=target_link_id,
            target_node_id=target_node_id,
            severity=severity,
            missing_link_ids=missing_link_ids,
            ambiguous_link_ids=ambiguous_link_ids,
            ramp_progress=ramp_progress,
        )

        # Store run measurements in memory and persist in SQLite
        self._runs[run_id] = RunMeasurementsResponse(
            run_id=run_id,
            data_source="simulated",
            measurements=measurements,
        )
        self._persist_run(run_id=run_id, data_source="simulated", measurements=measurements)

        # 2. Retrieve topology for diagnostic context (device relationships)
        topology = self.get_topology(force_in_memory=force_in_memory)

        # 3. Diagnose root cause (without passing target_link_id)
        incident = self.diagnostic_engine.diagnose(
            measurements=measurements,
            topology=topology,
            run_id=run_id,
        )

        incident_id: Optional[str] = None
        if incident.suspected_component_id is not None or incident.status == "open":
            incident_id = incident.id
            self._incidents[incident.id] = incident
            self._incident_order.append(incident.id)
        else:
            # Baseline or any run that yields no open incident clears active faults
            self.close_open_incidents()

        return ScenarioRunResponse(
            run_id=run_id,
            data_source="simulated",
            measurements_count=len(measurements),
            incident_id=incident_id,
        )

    def ingest_live_measurements(
        self,
        measurements: List[Any],
        hop_trace: Optional[List[Any]] = None,
    ) -> ScenarioRunResponse:
        """Stores live measurements, pushes them into the time-series store, and runs diagnosis."""
        from app.config import settings
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        ttl = float(settings.live_ttl_seconds)

        # 1. Backfill separation:
        # In live mode: a measurement whose own timestamp is older than LIVE_TTL_SECONDS goes to history only.
        # In demo mode: behaviour unchanged (preserves existing tests with hardcoded demo timestamps).
        current_measurements: List[Any] = []
        backfilled_measurements: List[Any] = []

        if settings.data_mode == "live":
            for m in measurements:
                m.data_source = "live"
                ts_str = getattr(m, "timestamp_utc", None) or getattr(m, "timestamp", None)
                is_backfill = False
                if ts_str:
                    try:
                        ts_clean = str(ts_str).replace("Z", "+00:00")
                        m_dt = datetime.fromisoformat(ts_clean)
                        if m_dt.tzinfo is None:
                            m_dt = m_dt.replace(tzinfo=timezone.utc)
                        if (now - m_dt).total_seconds() > ttl:
                            is_backfill = True
                    except Exception:
                        pass

                if is_backfill:
                    backfilled_measurements.append(m)
                else:
                    current_measurements.append(m)
        else:
            current_measurements = list(measurements)
            for m in current_measurements:
                m.data_source = "live"

        # Push to time-series store and persist all measurements
        from app.engine.time_series import get_time_series_store
        ts_store = get_time_series_store()
        if measurements:
            ts_store.push_measurements_batch(measurements)

        # Backfill rule: if no current measurements exist, do not refresh received_at,
        # do not trigger diagnosis, and do not open an incident.
        if not current_measurements:
            run_id = f"backfill-{uuid.uuid4().hex[:8]}"
            self._persist_run(run_id=run_id, data_source="live", measurements=measurements)
            return ScenarioRunResponse(
                run_id=run_id,
                data_source="live",
                measurements_count=len(measurements),
                incident_id=None,
            )

        # Update live measurements and arrival metadata for current readings
        for m in current_measurements:
            self._live_measurements[m.component_id] = m
            ts_iso = getattr(m, "timestamp_utc", None) or getattr(m, "timestamp", None) or now.isoformat()
            self._live_metadata[m.component_id] = {
                "received_at": now,
                "last_seen_utc": ts_iso,
            }

        # Build active measurements:
        # In live mode: ONLY live and stale measurements. Never fill from baseline.
        # In demo mode: overlay live readings onto baseline with noise.
        if settings.data_mode == "live":
            active_measurements = []
            for comp_id, lm in self._live_measurements.items():
                freshness, _ = self.get_freshness(comp_id, now=now)
                if freshness in ("live", "stale"):
                    active_measurements.append(lm)
        else:
            baseline_meas = self.telemetry_generator.generate_baseline_with_noise()
            active_meas_map = {m.component_id: m for m in baseline_meas}
            for m in self._live_measurements.values():
                active_meas_map[m.component_id] = m
            active_measurements = list(active_meas_map.values())

        run_id = f"live-{uuid.uuid4().hex[:8]}"
        self._runs[run_id] = RunMeasurementsResponse(
            run_id=run_id,
            data_source="live",
            measurements=active_measurements,
        )
        self._persist_run(run_id=run_id, data_source="live", measurements=active_measurements)

        topology = self.get_topology(force_in_memory=True)
        incident = self.diagnostic_engine.diagnose(
            measurements=active_measurements,
            topology=topology,
            run_id=run_id,
        )

        if hop_trace is not None and hasattr(incident, "hop_trace"):
            incident.hop_trace = hop_trace

        incident_id: Optional[str] = None
        if incident.suspected_component_id is not None and incident.status == "open":
            incident_id = incident.id
            self._incidents[incident.id] = incident
            self._incident_order.append(incident.id)
            self._persist_incident(incident)
        else:
            self.close_open_incidents()

        return ScenarioRunResponse(
            run_id=run_id,
            data_source="live",
            measurements_count=len(measurements),
            incident_id=incident_id,
        )

    def _persist_run(
        self,
        run_id: str,
        data_source: str,
        measurements: List[Any],
    ) -> None:
        """Persists run and measurements into SQLite using configured retention limit."""
        try:
            from app.config import settings
            from app.db.connection import get_db_connection
            from app.db.repository import save_run
            conn = get_db_connection()
            try:
                save_run(
                    conn=conn,
                    run_id=run_id,
                    data_source=data_source,
                    measurements=measurements,
                    retention_limit=settings.runs_retention_limit,
                )
            finally:
                conn.close()
        except Exception:
            pass

    def _persist_incident(self, incident: IncidentDetails) -> None:
        """Persists open diagnostic incident with extras (cause, hop_trace) into SQLite."""
        try:
            from app.db.connection import get_db_connection
            from app.db.repository import create_incident
            conn = get_db_connection()
            try:
                inc_dict = incident.model_dump() if hasattr(incident, "model_dump") else incident.dict()
                create_incident(conn, inc_dict)
            finally:
                conn.close()
        except Exception:
            pass

    def get_live_measurements(self) -> Dict[str, Any]:
        """Returns currently ingested live measurements indexed by component ID."""
        return self._live_measurements

    def get_freshness(
        self,
        component_id: str,
        now: Optional[datetime] = None,
    ) -> Tuple[str, Optional[str]]:
        """Returns (freshness, last_seen_utc) per HopTrace Part 1 Contract §2.1.

        Rules: Let age = now - received_at:
          - age <= LIVE_TTL_SECONDS -> 'live'
          - LIVE_TTL_SECONDS < age <= 3 * LIVE_TTL_SECONDS -> 'stale'
          - older, or never seen, in live mode -> 'no_data'
          - DATA_MODE=demo and link never had live data -> 'simulated'
        """
        from app.config import settings

        if now is None:
            now = datetime.now(timezone.utc)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        meta = self._live_metadata.get(component_id)
        if not meta or "received_at" not in meta:
            if settings.data_mode == "live":
                return "no_data", None
            return "simulated", None

        received_at = meta["received_at"]
        if received_at.tzinfo is None:
            received_at = received_at.replace(tzinfo=timezone.utc)

        age = max(0.0, (now - received_at).total_seconds())
        last_seen_utc = meta.get("last_seen_utc")

        ttl = float(settings.live_ttl_seconds)
        if age <= ttl:
            return "live", last_seen_utc
        elif age <= 3.0 * ttl:
            return "stale", last_seen_utc
        else:
            if settings.data_mode == "live":
                return "no_data", last_seen_utc
            return "simulated", last_seen_utc

    def clear_live_measurements(self) -> None:
        """Clears all ingested live measurements and metadata."""
        self._live_measurements.clear()
        self._live_metadata.clear()

    def close_open_incidents(self) -> List[str]:
        """Marks all currently open incidents in the engine store and SQLite as closed."""
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        closed_ids = []
        for inc_id in self._incident_order:
            inc = self._incidents.get(inc_id)
            if inc and inc.status == "open":
                inc.status = "closed"
                if hasattr(inc, "resolved_at"):
                    inc.resolved_at = now_iso
                if hasattr(inc, "duration_seconds") and getattr(inc, "created_at", None):
                    try:
                        c_dt = datetime.fromisoformat(str(inc.created_at).replace("Z", "+00:00"))
                        if c_dt.tzinfo is None:
                            c_dt = c_dt.replace(tzinfo=timezone.utc)
                        inc.duration_seconds = max(0, int((now - c_dt).total_seconds()))
                    except Exception:
                        pass
                closed_ids.append(inc_id)

        try:
            from app.db.connection import get_db_connection
            from app.db.repository import close_open_incidents as repo_close_open
            conn = get_db_connection()
            try:
                repo_close_open(conn)
            finally:
                conn.close()
        except Exception:
            pass

        return closed_ids

    def get_latest_open_incident(self) -> Optional[IncidentDetails]:
        """Returns the most recent incident with status == 'open', or None."""
        for inc_id in reversed(self._incident_order):
            inc = self._incidents.get(inc_id)
            if inc and inc.status == "open":
                return inc
        return None

    def get_incident_details(self, incident_id: str) -> Optional[IncidentDetails]:
        """Retrieves incident details by ID."""
        return self._incidents.get(incident_id)

    def get_latest_incident(self) -> Optional[IncidentDetails]:
        """Returns the most recent incident or None if no incident exists."""
        if not self._incident_order:
            return None
        latest_id = self._incident_order[-1]
        return self._incidents.get(latest_id)

    def get_affected_subscribers(
        self,
        incident_id: str,
        force_in_memory: bool = False,
    ) -> AffectedSubscribersResponse:
        """Finds subscribers whose connectivity depends on the suspected component."""
        incident = self._incidents.get(incident_id)
        if not incident or not incident.suspected_component_id:
            return AffectedSubscribersResponse(count=0, subscribers=[])

        store = self.get_active_store(force_in_memory=force_in_memory)
        return store.get_affected_subscribers(
            suspected_component_id=incident.suspected_component_id,
            component_type=incident.suspected_component_type or "link",
        )

    def get_run_measurements(self, run_id: str) -> Optional[RunMeasurementsResponse]:
        """Retrieves measurements for a given run ID from memory, falling back to SQLite."""
        if run_id in self._runs:
            return self._runs[run_id]

        try:
            from app.db.connection import get_db_connection
            from app.db.repository import get_run
            conn = get_db_connection()
            try:
                run_dict = get_run(conn, run_id)
                if run_dict:
                    meas = [
                        Measurement(
                            component_id=m["component_id"],
                            timestamp_utc=m["timestamp_utc"],
                            latency_ms=m.get("latency_ms"),
                            packet_loss_pct=m.get("packet_loss_pct"),
                            throughput_mbps=m.get("throughput_mbps"),
                            connectivity_ok=m.get("connectivity_ok", True),
                            data_source=m.get("data_source", run_dict.get("data_source", "simulated")),
                        )
                        for m in run_dict.get("measurements", [])
                    ]
                    run_resp = RunMeasurementsResponse(
                        run_id=run_dict["run_id"],
                        data_source=run_dict.get("data_source", "simulated"),
                        measurements=meas,
                    )
                    self._runs[run_id] = run_resp
                    return run_resp
            finally:
                conn.close()
        except Exception:
            pass

        return None

    def check_neo4j_health(self) -> Dict[str, Any]:
        """Checks Neo4j database connectivity."""
        return self.neo4j_client.check_connection()


# Global engine singleton
_engine_instance: Optional[HopTraceEngine] = None


def get_engine() -> HopTraceEngine:
    """Returns the shared HopTraceEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = HopTraceEngine()
    return _engine_instance


# Convenience module-level functions for backend integration
def seed_topology(force_in_memory: bool = False) -> Dict[str, Any]:
    return get_engine().seed_topology(force_in_memory=force_in_memory)


def get_topology(force_in_memory: bool = False) -> NetworkTopology:
    return get_engine().get_topology(force_in_memory=force_in_memory)


def run_scenario(
    scenario: str = "baseline",
    target_link_id: Optional[str] = None,
    target_node_id: Optional[str] = None,
    severity: str = "medium",
    missing_link_ids: Optional[List[str]] = None,
    ambiguous_link_ids: Optional[List[str]] = None,
    force_in_memory: bool = False,
    ramp_progress: float = 0.0,
) -> ScenarioRunResponse:
    return get_engine().run_scenario(
        scenario=scenario,
        target_link_id=target_link_id,
        target_node_id=target_node_id,
        severity=severity,
        missing_link_ids=missing_link_ids,
        ambiguous_link_ids=ambiguous_link_ids,
        force_in_memory=force_in_memory,
        ramp_progress=ramp_progress,
    )


def ingest_live_measurements(
    measurements: List[Any],
    hop_trace: Optional[List[Any]] = None,
) -> ScenarioRunResponse:
    return get_engine().ingest_live_measurements(measurements, hop_trace=hop_trace)


def get_live_measurements() -> Dict[str, Any]:
    return get_engine().get_live_measurements()


def get_freshness(
    component_id: str,
    now: Optional[datetime] = None,
) -> Tuple[str, Optional[str]]:
    return get_engine().get_freshness(component_id, now=now)


def clear_live_measurements() -> None:
    get_engine().clear_live_measurements()


def get_incident_details(incident_id: str) -> Optional[IncidentDetails]:
    return get_engine().get_incident_details(incident_id)


def get_latest_incident() -> Optional[IncidentDetails]:
    return get_engine().get_latest_incident()


def get_latest_open_incident() -> Optional[IncidentDetails]:
    return get_engine().get_latest_open_incident()


def close_open_incidents() -> List[str]:
    return get_engine().close_open_incidents()


def get_affected_subscribers(
    incident_id: str,
    force_in_memory: bool = False,
) -> AffectedSubscribersResponse:
    return get_engine().get_affected_subscribers(
        incident_id=incident_id,
        force_in_memory=force_in_memory,
    )


def get_run_measurements(run_id: str) -> Optional[RunMeasurementsResponse]:
    return get_engine().get_run_measurements(run_id)


def check_neo4j_health() -> Dict[str, Any]:
    return get_engine().check_neo4j_health()
