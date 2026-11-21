"""Data models and schemas for the HopTrace Network Intelligence Engine.

All models adhere to docs/api-contract.md.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class NodeType(str, Enum):
    GATEWAY = "gateway"
    ROUTER = "router"
    WIRELESS_BRIDGE = "wireless_bridge"
    ACCESS_POINT = "access_point"


class ComponentType(str, Enum):
    LINK = "link"
    NODE = "node"
    GATEWAY = "gateway"
    ROUTER = "router"
    WIRELESS_BRIDGE = "wireless_bridge"
    ACCESS_POINT = "access_point"


class NodeStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


class LinkStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"


class TopologyNode(BaseModel):
    id: str
    type: str  # gateway, router, wireless_bridge, access_point
    label: str
    status: str = "healthy"
    properties: Dict[str, Any] = Field(default_factory=dict)


class TopologyLink(BaseModel):
    id: str
    source: str
    target: str
    status: str = "healthy"
    latency_ms: Optional[float] = None
    packet_loss_pct: Optional[float] = None
    throughput_mbps: Optional[float] = None
    properties: Dict[str, Any] = Field(default_factory=dict)


class NetworkTopology(BaseModel):
    nodes: List[TopologyNode]
    links: List[TopologyLink]
    data_source: str = "simulated"


class Subscriber(BaseModel):
    id: str
    display_name: str
    access_point_id: str
    plan: Optional[str] = "Standard"
    plan_price: Optional[float] = 399.0
    status: Optional[str] = "active"
    payment_status: Optional[str] = "paid"
    due_date: Optional[str] = "2026-11-01"


class AffectedSubscriber(BaseModel):
    id: str
    display_name: str
    access_point_id: str


class AffectedSubscribersResponse(BaseModel):
    count: int
    subscribers: List[AffectedSubscriber]


class Measurement(BaseModel):
    component_id: str
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    latency_ms: Optional[float] = None
    packet_loss_pct: Optional[float] = None
    throughput_mbps: Optional[float] = None
    connectivity_ok: bool = True
    data_source: str = "simulated"


class RunMeasurementsResponse(BaseModel):
    run_id: str
    data_source: str = "simulated"
    measurements: List[Measurement]


class EvidenceItem(BaseModel):
    metric: str
    observed_value: Any
    baseline_value: Any
    threshold: Any
    status: str = "anomaly"  # normal, anomaly, missing
    severity: str = "info"   # low, medium, high, critical
    description: str


class IncidentDetails(BaseModel):
    id: str
    run_id: str
    status: str = "open"
    suspected_component_id: Optional[str] = None
    suspected_component_type: Optional[str] = None  # link or node
    summary: str
    confidence_score: Optional[float] = None
    diagnostic_score: Optional[float] = None
    evidence: List[EvidenceItem] = Field(default_factory=list)
    uncertainty_note: Optional[str] = None
    data_source: str = "simulated"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ScenarioRunResponse(BaseModel):
    run_id: str
    data_source: str = "simulated"
    measurements_count: int
    incident_id: Optional[str] = None


class AIReport(BaseModel):
    """Structured AI-generated fault analysis from Sarvam 105B."""
    executive_summary: Optional[str] = None
    technical_diagnosis: Optional[str] = None
    field_operator_steps: List[str] = Field(default_factory=list)
    subscriber_impact_brief: Optional[str] = None
    escalation_required: Optional[bool] = None
    estimated_resolution_minutes: Optional[int] = None
    language: str = "en"
    provider: str = "unavailable"
