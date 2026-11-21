"""
New v2 API endpoints for topology risk scoring and link history.

GET /api/v1/topology/risk         — Per-link risk scores + trends
GET /api/v1/topology/history/{link_id} — Last N telemetry samples
GET /api/v1/villages              — Village list + aggregate health
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.engine.facade import get_topology
from app.engine.time_series import get_time_series_store
from app.engine.topology import VILLAGE_METADATA

router = APIRouter(tags=["topology"])


class LinkRiskItem(BaseModel):
    link_id: str
    risk_score: float
    trend: str
    alert_level: str
    flap_count: int
    ewma_latency_ms: Optional[float] = None
    ewma_loss_pct: Optional[float] = None
    ewma_throughput_mbps: Optional[float] = None


class TopologyRiskResponse(BaseModel):
    links: List[LinkRiskItem]
    network_status: str
    cascade_detected: bool
    flapping_links: List[str]
    max_risk_score: float


class LinkHistorySample(BaseModel):
    tick: int
    timestamp_utc: str
    latency_ms: Optional[float]
    packet_loss_pct: Optional[float]
    throughput_mbps: Optional[float]
    connectivity_ok: bool
    risk_score: float
    trend: str
    alert_level: str


class LinkHistoryResponse(BaseModel):
    link_id: str
    samples: List[LinkHistorySample]
    count: int


class VillageHealth(BaseModel):
    village_id: str
    name: str
    population: int
    access_points: List[str]
    description: str
    max_risk_score: float
    status: str


class VillagesResponse(BaseModel):
    villages: List[VillageHealth]


@router.get(
    "/topology/risk",
    response_model=TopologyRiskResponse,
    summary="Get per-link risk scores and trend analysis",
)
def get_topology_risk() -> TopologyRiskResponse:
    """Returns real-time risk scores, trends, and alert levels for all tracked links."""
    ts_store = get_time_series_store()
    risk_data = ts_store.get_risk_snapshot()
    cascade = ts_store.detect_cascade(threshold_risk=60.0)
    flapping = ts_store.detect_flapping_links()

    link_items = [
        LinkRiskItem(
            link_id=r["link_id"],
            risk_score=r["risk_score"],
            trend=r["trend"],
            alert_level=r["alert_level"],
            flap_count=r["flap_count"],
            ewma_latency_ms=r.get("ewma_latency_ms"),
            ewma_loss_pct=r.get("ewma_loss_pct"),
            ewma_throughput_mbps=r.get("ewma_throughput_mbps"),
        )
        for r in risk_data
    ]

    max_risk = max((r.risk_score for r in link_items), default=0.0)
    if max_risk >= 75 or any(r.alert_level == "critical" for r in link_items):
        network_status = "critical"
    elif max_risk >= 40 or cascade:
        network_status = "degraded"
    else:
        network_status = "healthy"

    return TopologyRiskResponse(
        links=link_items,
        network_status=network_status,
        cascade_detected=cascade,
        flapping_links=flapping,
        max_risk_score=max_risk,
    )


@router.get(
    "/topology/history/{link_id}",
    response_model=LinkHistoryResponse,
    summary="Get historical telemetry samples for a specific link",
)
def get_link_history(
    link_id: str,
    n: int = Query(50, ge=1, le=200, description="Number of recent samples to return"),
) -> LinkHistoryResponse:
    """Returns last N telemetry samples for the specified link from the time-series store."""
    # Validate link exists in topology
    try:
        topo = get_topology()
        known_links = {lk.id for lk in topo.links}
        if link_id not in known_links:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Link '{link_id}' not found in topology. Valid: {sorted(known_links)}",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    ts_store = get_time_series_store()
    history = ts_store.get_link_history(link_id, n=n)

    samples = [
        LinkHistorySample(
            tick=s["tick"],
            timestamp_utc=s["timestamp_utc"],
            latency_ms=s["latency_ms"],
            packet_loss_pct=s["packet_loss_pct"],
            throughput_mbps=s["throughput_mbps"],
            connectivity_ok=s["connectivity_ok"],
            risk_score=s["risk_score"],
            trend=s["trend"],
            alert_level=s["alert_level"],
        )
        for s in history
    ]

    return LinkHistoryResponse(link_id=link_id, samples=samples, count=len(samples))


@router.get(
    "/villages",
    response_model=VillagesResponse,
    summary="Get village list with aggregate health status",
)
def get_villages() -> VillagesResponse:
    """Returns all villages with their current network health status."""
    ts_store = get_time_series_store()

    # AP → village mapping
    AP_VILLAGE = {
        "AP1": "rampur", "AP2": "rampur",
        "AP3": "bhatpur", "AP4": "bhatpur",
        "AP5": "daulatpur", "AP6": "daulatpur",
    }

    # Link → village mapping (village is affected if upstream link is bad)
    LINK_VILLAGE = {
        "L1": None,  # Affects all villages
        "L2": "rampur", "L3": "rampur", "L4": "rampur", "L5": "rampur",
        "L6": "bhatpur", "L7": "bhatpur", "L8": "bhatpur", "L9": "bhatpur", "L10": "bhatpur",
        "L11": "daulatpur", "L12": "daulatpur", "L13": "daulatpur", "L14": "daulatpur",
    }

    risk_map = {r["link_id"]: r["risk_score"] for r in ts_store.get_risk_snapshot()}

    village_risks: Dict[str, List[float]] = {v: [] for v in VILLAGE_METADATA}
    for link_id, village in LINK_VILLAGE.items():
        if village and link_id in risk_map:
            village_risks[village].append(risk_map[link_id])

    village_healths = []
    for vid, meta in VILLAGE_METADATA.items():
        risks = village_risks.get(vid, [])
        max_r = max(risks, default=0.0)
        if max_r >= 75:
            vstatus = "critical"
        elif max_r >= 40:
            vstatus = "degraded"
        else:
            vstatus = "healthy"

        village_healths.append(VillageHealth(
            village_id=vid,
            name=meta["name"],
            population=meta["population"],
            access_points=meta["access_points"],
            description=meta["description"],
            max_risk_score=round(max_r, 1),
            status=vstatus,
        ))

    return VillagesResponse(villages=village_healths)


class VillageSlaItem(BaseModel):
    village_id: str
    village_name: str
    uptime_pct: float
    downtime_minutes: float
    total_incidents: int
    active_incidents: int
    status: str


class TopologySlaResponse(BaseModel):
    window_hours: int
    timestamp_utc: str
    villages: Dict[str, VillageSlaItem]


@router.get(
    "/topology/sla",
    response_model=TopologySlaResponse,
    summary="Get SLA availability and outage duration per village",
)
def get_topology_sla(
    window_hours: int = Query(default=24, ge=1, le=720, description="SLA calculation window in hours"),
) -> TopologySlaResponse:
    """Computes uptime percentage and outage minutes per village from historical and active incidents."""
    from app.db.connection import get_db_connection
    from app.db.repository import get_village_sla_stats
    conn = get_db_connection()
    try:
        stats = get_village_sla_stats(conn, window_hours=window_hours)
        return TopologySlaResponse(**stats)
    finally:
        conn.close()
