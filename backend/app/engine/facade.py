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

Adheres strictly to docs/api-contract.md.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from backend.app.engine.diagnostics import DiagnosticEngine
from backend.app.engine.graph_store import InMemoryGraphStore, Neo4jGraphStore
from backend.app.engine.models import (
    AffectedSubscribersResponse,
    IncidentDetails,
    NetworkTopology,
    RunMeasurementsResponse,
    ScenarioRunResponse,
)
from backend.app.engine.neo4j_client import get_neo4j_client
from backend.app.engine.telemetry import RAMP_TICKS, SimulatedTelemetryGenerator


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

        # Store run measurements
        self._runs[run_id] = RunMeasurementsResponse(
            run_id=run_id,
            data_source="simulated",
            measurements=measurements,
        )

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

        return ScenarioRunResponse(
            run_id=run_id,
            data_source="simulated",
            measurements_count=len(measurements),
            incident_id=incident_id,
        )

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
        """Retrieves simulated measurements for a given run ID."""
        return self._runs.get(run_id)

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


def get_incident_details(incident_id: str) -> Optional[IncidentDetails]:
    return get_engine().get_incident_details(incident_id)


def get_latest_incident() -> Optional[IncidentDetails]:
    return get_engine().get_latest_incident()


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
