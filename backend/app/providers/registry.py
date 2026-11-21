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
from app.providers.notifications import (
    NotificationProvider,
    UnavailableNotificationProvider,
    ConsoleNotificationProvider,
    TwilioNotificationProvider,
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

_console_provider_instance = None


def get_notification_provider() -> NotificationProvider:
    """
    Factory used as a FastAPI dependency for outage notifications.

    Supported NOTIFICATION_PROVIDER values:
      unavailable - Explicitly unavailable provider (raises NotificationProviderUnavailableError)
      console     - In-memory logging provider for demos and tests
      twilio      - Twilio SMS and WhatsApp provider (requires TWILIO_* credentials)
    """
    global _console_provider_instance
    name = settings.notification_provider.lower().strip()

    if name == "unavailable":
        return UnavailableNotificationProvider()

    if name == "console":
        if _console_provider_instance is None:
            _console_provider_instance = ConsoleNotificationProvider()
        return _console_provider_instance

    if name == "twilio":
        return TwilioNotificationProvider(
            account_sid=settings.twilio_account_sid,
            auth_token=settings.twilio_auth_token,
            from_number=settings.twilio_from_number,
            whatsapp_from_number=settings.twilio_whatsapp_from_number,
        )

    raise ValueError(
        f"Unknown NOTIFICATION_PROVIDER={name!r}. "
        "Valid values: 'unavailable', 'console', 'twilio'."
    )
