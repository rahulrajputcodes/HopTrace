"""
Pydantic schemas for the topology endpoint.

These match the shapes documented in docs/api-contract.md exactly.
Measurement fields (latency_ms, packet_loss_pct, throughput_mbps) are
Optional[float] because the contract says they must be null when unavailable.
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


# ── Node ────────────────────────────────────────────────────────────────────

NodeType = Literal["gateway", "router", "wireless_bridge", "access_point"]
NodeStatus = Literal["healthy", "degraded", "failed", "unknown"]


class TopologyNode(BaseModel):
    id: str
    type: NodeType
    label: str
    status: NodeStatus
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)
    village: Optional[str] = None
    coverage_radius_m: Optional[int] = Field(None, gt=0)


# ── Link ────────────────────────────────────────────────────────────────────

LinkStatus = Literal["healthy", "degraded", "failed", "unknown"]


class TopologyLink(BaseModel):
    id: str
    source: str
    target: str
    status: LinkStatus
    latency_ms: Optional[float] = None
    packet_loss_pct: Optional[float] = None
    throughput_mbps: Optional[float] = None
    distance_km: Optional[float] = None
    medium: Optional[str] = None
    frequency: Optional[str] = None


# ── Top-level response ───────────────────────────────────────────────────────

DataSource = Literal["simulated", "measured"]


class TopologyResponse(BaseModel):
    nodes: list[TopologyNode]
    links: list[TopologyLink]
    data_source: DataSource
