"""GET /api/v1/topology/risk, GET /api/v1/topology/history/{link_id}, GET /api/v1/villages

Returns per-link risk snapshot (including optional Theil-Sen ETA predictions),
historical telemetry samples, and village health aggregations.

Follows docs/api-contract.md §5 (Predictive Fault AI).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.engine.facade import get_topology
from app.engine.time_series import get_time_series_store
from app.engine.topology import VILLAGE_METADATA

router = APIRouter(tags=["topology"])


class LinkRiskItem(BaseModel):
    """Per-link risk entry returned by GET /topology/risk.

    Prediction fields are optional — they are absent (null) when the
    predictor cannot issue a forecast (too few samples, link stable,
    link already failed, or connectivity lost).
    """

    link_id: str = Field(..., description="Link identifier (e.g. 'L3')")
    connectivity_ok: Optional[bool] = Field(
        None, description="Whether the link is locally link-present"
    )
    packet_loss_pct: Optional[float] = Field(
        None, description="Observed packet loss percentage"
    )
    latency_ms: Optional[float] = Field(
        None, description="Observed round-trip latency in milliseconds"
    )
    throughput_mbps: Optional[float] = Field(
        None, description="Observed throughput in Mbps"
    )
    data_source: str = Field(
        "simulated", description="'simulated' (lab/eval) or 'measured' (replay probe)"
    )
    risk_score: Optional[float] = Field(
        0.0, description="EWMA anomaly risk score (0-100)"
    )
    trend: Optional[str] = Field(
        "stable", description="Trend direction: stable | degrading | recovering"
    )
    alert_level: Optional[str] = Field(
        "normal", description="Alert level: normal | warning | critical"
    )
    flap_count: Optional[int] = Field(
        0, description="Flap toggle count in recent window"
    )
    ewma_latency_ms: Optional[float] = Field(
        None, description="EWMA smoothed latency in milliseconds"
    )
    ewma_loss_pct: Optional[float] = Field(
        None, description="EWMA smoothed packet loss percentage"
    )
    ewma_throughput_mbps: Optional[float] = Field(
        None, description="EWMA smoothed throughput in Mbps"
    )
    predicted_eta_minutes: Optional[float] = Field(
        None,
        description=(
            "Predicted time-to-failure in simulated minutes, derived from "
            "Theil-Sen slope on Degradation Index D.  Null when no prediction "
            "is issued."
        ),
    )
    prediction_confidence: Optional[str] = Field(
        None,
        description=(
            "Confidence level of the forecast: 'high' (R²≥0.80, n≥10), "
            "'medium' (R²≥0.50), 'low' (R²<0.50).  Null when no prediction."
        ),
    )
    prediction_r2: Optional[float] = Field(
        None,
        description=(
            "Coefficient of determination (R²) of the Theil-Sen fit on D. "
            "Null when no prediction is issued."
        ),
    )
    predicted_eta_min_minutes: Optional[float] = Field(
        None,
        description=(
            "Lower bound of the predicted time-to-failure in simulated minutes, "
            "derived from the 80th percentile slope (fastest degradation trend). "
            "Null when no prediction is issued."
        ),
    )
    predicted_eta_max_minutes: Optional[float] = Field(
        None,
        description=(
            "Upper bound of the predicted time-to-failure in simulated minutes, "
            "derived from the 20th percentile slope (slowest degradation trend). "
            "Null when no prediction is issued."
        ),
    )


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
    response_model=List[LinkRiskItem],
    summary="Per-link risk snapshot with predictive ETA",
    description=(
        "Returns the most-recent observed telemetry for every link that has "
        "been pushed into the time-series store, plus an optional ETA-to-failure "
        "prediction when the Theil-Sen trend fit is reliable.  "
        "All prediction fields are optional and additive — they are null when "
        "insufficient data is available or the link is stable/healthy.  "
        "Existing topology fields are not modified."
    ),
)
def topology_risk() -> List[LinkRiskItem]:
    """Return the risk snapshot from the shared time-series store.

    - 200: snapshot returned (may be empty list if store has no data yet).
    """
    store = get_time_series_store()
    raw = store.get_risk_snapshot()
    return [LinkRiskItem(**entry) for entry in raw]


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

    # Link → village mapping (village is affected if upstream link is bad)
    LINK_VILLAGE = {
        "L1": None,  # Affects all villages
        "L2": "rampur",
        "L3": "rampur",
        "L4": "rampur",
        "L5": "rampur",
        "L6": "bhatpur",
        "L7": "bhatpur",
        "L8": "bhatpur",
        "L9": "bhatpur",
        "L10": "bhatpur",
        "L11": "daulatpur",
        "L12": "daulatpur",
        "L13": "daulatpur",
        "L14": "daulatpur",
    }

    risk_map = {r["link_id"]: r["risk_score"] for r in ts_store.get_risk_snapshot()}

    village_risks: Dict[str, List[float]] = {v: [] for v in VILLAGE_METADATA}
    for link_id, village in LINK_VILLAGE.items():
        if village and link_id in risk_map:
            score = risk_map[link_id]
            if score is not None:
                village_risks[village].append(score)

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

        village_healths.append(
            VillageHealth(
                village_id=vid,
                name=meta["name"],
                population=meta["population"],
                access_points=meta["access_points"],
                description=meta["description"],
                max_risk_score=round(max_r, 1),
                status=vstatus,
            )
        )

    return VillagesResponse(villages=village_healths)
