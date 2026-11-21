"""
Agent heartbeat and status endpoints for monitoring blind-spot detection.

Implements:
- POST /api/v1/agent/heartbeat
- GET /api/v1/agent/status
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Header, HTTPException, status

from app.config import settings
from app.schemas.agents import (
    AgentHeartbeatRequest,
    AgentHeartbeatResponse,
    AgentStatusResponse,
)
from app.services.agent_monitor import agent_monitor

router = APIRouter(prefix="/agent", tags=["agents"])


def _check_api_key(x_api_key: Optional[str]) -> None:
    configured_key = settings.ingest_api_key.strip()
    if configured_key:
        if not x_api_key or x_api_key.strip() != configured_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing X-API-Key header",
            )


@router.post(
    "/heartbeat",
    response_model=AgentHeartbeatResponse,
    status_code=status.HTTP_200_OK,
    summary="Record monitoring agent heartbeat",
)
def record_heartbeat_endpoint(
    payload: AgentHeartbeatRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> AgentHeartbeatResponse:
    """Record heartbeat from an edge monitoring agent.

    Honours optional INGEST_API_KEY via X-API-Key header.
    """
    _check_api_key(x_api_key)

    agent_monitor.record_heartbeat(
        agent_id=payload.agent_id,
        site_id=payload.site_id,
        timestamp=payload.timestamp,
        buffered_count=payload.buffered_count,
        version=payload.version,
    )

    return AgentHeartbeatResponse(status="ok", agent_id=payload.agent_id)


@router.get(
    "/status",
    response_model=AgentStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get status snapshot of all monitoring agents",
)
def get_agent_status_endpoint() -> AgentStatusResponse:
    """Return current status of all registered monitoring agents.

    Identifies silent agents that indicate monitoring blind spots.
    """
    snapshot = agent_monitor.get_status_snapshot()
    return AgentStatusResponse(agents=snapshot)
