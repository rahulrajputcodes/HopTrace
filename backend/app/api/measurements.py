"""
Test run measurements retrieval and live telemetry ingestion endpoints.

Implements:
- GET /api/v1/runs/{run_id}/measurements
- POST /api/v1/measurements/ingest
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Header, HTTPException, status

from app.config import settings
from app.engine.facade import (
    get_run_measurements,
    get_topology,
    ingest_live_measurements,
)
from app.engine.models import Measurement
from app.schemas.measurements import (
    MeasurementIngestItem,
    MeasurementIngestResponse,
    RunMeasurementsResponse,
)

router = APIRouter(tags=["measurements"])


@router.post(
    "/measurements/ingest",
    response_model=MeasurementIngestResponse,
    summary="Ingest live telemetry measurements",
    description="Ingests real-time network telemetry, runs diagnosis, updates time-series buffers, and streams via WebSocket.",
)
def ingest_measurements(
    items: List[MeasurementIngestItem],
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> MeasurementIngestResponse:
    # 1. API key authentication (if INGEST_API_KEY env is configured)
    configured_key = settings.ingest_api_key.strip()
    if configured_key:
        if not x_api_key or x_api_key.strip() != configured_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing X-API-Key header",
            )

    # 2. Reject unknown component IDs with 422
    topo = get_topology(force_in_memory=True)
    valid_components = {link.id for link in topo.links} | {node.id for node in topo.nodes}
    for item in items:
        if item.component_id not in valid_components:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown component_id '{item.component_id}'. Must be a valid topology link or node.",
            )

    # 3. Map to engine Measurement models and ingest
    now_iso = datetime.now(timezone.utc).isoformat()
    measurements = [
        Measurement(
            component_id=item.component_id,
            timestamp_utc=item.timestamp or now_iso,
            latency_ms=item.latency_ms,
            packet_loss_pct=item.packet_loss_pct,
            throughput_mbps=item.throughput_mbps,
            connectivity_ok=item.connectivity_ok,
            data_source="live",
        )
        for item in items
    ]

    res = ingest_live_measurements(measurements)
    return MeasurementIngestResponse(
        status="ok",
        ingested_count=len(items),
        data_source="live",
        incident_id=res.incident_id,
    )


@router.get(
    "/runs/{run_id}/measurements",
    response_model=RunMeasurementsResponse,
    summary="Get run measurements",
    description="Retrieves all simulated or measured telemetry observations captured for a specific test run.",
)
def get_measurements_by_run_id(run_id: str) -> RunMeasurementsResponse:
    """
    Retrieve telemetry measurements for a run by run_id or return 404 Not Found.

    - 200: Measurements retrieved successfully.
    - 404: Run ID not found.
    """
    run_data = get_run_measurements(run_id)
    if run_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found",
        )
    return RunMeasurementsResponse.model_validate(run_data.model_dump())
