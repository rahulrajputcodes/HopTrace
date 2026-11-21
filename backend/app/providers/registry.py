"""
Provider registry.

Selects topology providers, dependency adapters, and explanation providers from application settings.
"""
from __future__ import annotations

from app.config import settings
from app.providers.base import TopologyProvider
from app.providers.dependencies import (
    DependencyAnalysisAdapter,
    EngineDependencyAdapter,
    GraphEngineUnavailableError,
    SimulatedDependencyAdapter,
    UnavailableDependencyAdapter,
)
from app.providers.explanations import (
    ExplanationProvider,
    ExplanationProviderUnavailableError,
    SarvamExplanationProvider,
    SimulatedExplanationProvider,
    UnavailableExplanationProvider,
)
from app.providers.simulated import SimulatedTopologyProvider


def get_topology_provider() -> TopologyProvider:
    """
    Factory used as a FastAPI dependency for network topology.

    Supported TOPOLOGY_PROVIDER values:
      simulated - Standalone simulated topology
      engine    - HopTrace graph engine (Neo4j with in-memory fallback)
    """
    name = settings.topology_provider.lower()

    if name == "simulated":
        return SimulatedTopologyProvider()

    if name == "engine":
        from app.providers.engine_topology import EngineTopologyProvider

        return EngineTopologyProvider()

    raise ValueError(
        f"Unknown TOPOLOGY_PROVIDER={name!r}. "
        "Valid values: 'simulated', 'engine'."
    )


def get_dependency_adapter() -> DependencyAnalysisAdapter:
    """
    Factory used as a FastAPI dependency for affected-subscriber analysis.

    Supported DEPENDENCY_ADAPTER values:
      unavailable - Explicitly unavailable adapter (returns 503)
      simulated   - Standalone demo mapping (hardcoded topology-based)
      engine      - HopTrace graph engine (Neo4j with in-memory fallback)
    """
    name = settings.dependency_adapter.lower()

    if name == "unavailable":
        return UnavailableDependencyAdapter()

    if name == "simulated":
        return SimulatedDependencyAdapter()

    if name == "engine":
        return EngineDependencyAdapter()

    raise ValueError(
        f"Unknown DEPENDENCY_ADAPTER={name!r}. "
        "Valid values: 'unavailable', 'simulated', 'engine'."
    )


def get_explanation_provider() -> ExplanationProvider:
    """
    Factory used as a FastAPI dependency for incident explanations.

    Supported EXPLANATION_PROVIDER values:
      unavailable - Explicitly unavailable provider (raises ExplanationProviderUnavailableError)
      sarvam      - Sarvam AI chat-completions endpoint (requires SARVAM_API_KEY)
      simulated   - High-fidelity offline / demo explanations (grounded in incident facts)
    """
    name = settings.explanation_provider.lower()

    if name == "unavailable":
        return UnavailableExplanationProvider()

    if name == "sarvam":
        return SarvamExplanationProvider(
            api_key=settings.sarvam_api_key,
            model=settings.sarvam_model,
            timeout_seconds=settings.sarvam_timeout_seconds,
        )

    if name == "simulated":
        return SimulatedExplanationProvider()

    raise ValueError(
        f"Unknown EXPLANATION_PROVIDER={name!r}. "
        "Valid values: 'unavailable', 'sarvam', 'simulated'."
    )
