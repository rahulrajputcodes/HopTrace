"""Pydantic schemas for the hop-by-hop path probe endpoint."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class NodeProbeResult(BaseModel):
    node_id: str
    reachable: bool
    latency_ms: Optional[float] = None
    packet_loss_pct: Optional[float] = None


class PathProbeRequest(BaseModel):
    agent_id: str
    vantage_node_id: str = "GW1"
    timestamp: Optional[str] = None
    results: List[NodeProbeResult]


class PathProbeResponse(BaseModel):
    status: str = "ok"
    derived_links: int
    first_failed_nodes: List[str] = Field(default_factory=list)
    incident_id: Optional[str] = None
