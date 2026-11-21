"""API endpoint for hop-by-hop path probe ingestion."""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Header, HTTPException, status

from app.config import settings
from app.engine.facade import get_topology, ingest_live_measurements
from app.engine.probes import derive_link_measurements
from app.schemas.probes import PathProbeRequest, PathProbeResponse

router = APIRouter(tags=["probes"])


@router.post(
    "/probes/path",
    response_model=PathProbeResponse,
    summary="Ingest hop-by-hop path probe results",
    description="Accepts agent node probe pings, derives per-link measurements via tree semantics, blames only the first failed hop, and triggers diagnosis.",
)
def ingest_path_probes(
    req: PathProbeRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> PathProbeResponse:
    # 1. API key authentication (consistent with measurements ingestion)
    configured_key = settings.ingest_api_key.strip()
    if configured_key:
        if not x_api_key or x_api_key.strip() != configured_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing X-API-Key header",
            )

    # 2. Unknown node_id validation -> HTTP 422
    topology = get_topology(force_in_memory=True)
    valid_node_ids = {n.id for n in topology.nodes}
    for item in req.results:
        if item.node_id not in valid_node_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown node_id '{item.node_id}'. Must be a valid topology node.",
            )

    # 3. Derive link measurements and hop trace
    derived_measurements, hop_trace = derive_link_measurements(
        results=req.results,
        topology=topology,
        vantage_node_id=req.vantage_node_id or "GW1",
    )

    if req.timestamp:
        for m in derived_measurements:
            m.timestamp_utc = req.timestamp

    # 4. Single batch diagnosis via ingest_live_measurements with hop_trace attached
    res = ingest_live_measurements(derived_measurements, hop_trace=hop_trace)

    first_failed = [h.node_id for h in hop_trace if h.status == "failed"]

    return PathProbeResponse(
        status="ok",
        derived_links=len(derived_measurements),
        first_failed_nodes=first_failed,
        incident_id=res.incident_id,
    )
