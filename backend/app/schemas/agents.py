"""
Schemas for agent heartbeat and status monitoring endpoints.

Adheres to HopTrace Part 1 Contract §2.4.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class AgentHeartbeatRequest(BaseModel):
    agent_id: str = Field(..., description="Unique agent identifier (e.g. agent-rampur-1)")
    site_id: str = Field(..., description="Physical site/village location (e.g. rampur)")
    timestamp: str = Field(..., description="Timestamp of heartbeat generation (ISO 8601 UTC)")
    buffered_count: int = Field(0, description="Number of unsent batches currently stored in local buffer")
    version: str = Field("2.1", description="Agent software version")


class AgentHeartbeatResponse(BaseModel):
    status: str = Field("ok", description="Status acknowledgement")
    agent_id: str = Field(..., description="Agent identifier acknowledged")


class AgentStatusItem(BaseModel):
    agent_id: str = Field(..., description="Unique agent identifier")
    site_id: str = Field(..., description="Physical site identifier")
    last_seen_utc: str = Field(..., description="Last received heartbeat timestamp (ISO 8601 UTC)")
    status: str = Field(..., description="Connection status: 'online' or 'silent'")
    silent_for_seconds: int = Field(..., description="Elapsed seconds since last heartbeat")
    buffered_count: int = Field(0, description="Buffer backlog count reported by agent")


class AgentStatusResponse(BaseModel):
    agents: List[AgentStatusItem] = Field(default_factory=list, description="List of monitored agents")
