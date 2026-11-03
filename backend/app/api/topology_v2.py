"""GET /api/v1/topology/risk

Returns a per-link risk snapshot that includes the latest observed telemetry
and (optionally) a Theil-Sen ETA-to-failure prediction when the time-series
store has enough samples to support one.

All prediction fields (predicted_eta_minutes, prediction_confidence,
prediction_r2) are OPTIONAL and additive.  Existing topology fields are
never renamed or removed.  A teammate's map can safely ignore them.

Follows docs/api-contract.md §5 (Predictive Fault AI).
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.engine.time_series import get_time_series_store

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
    data_source: str = Field("simulated", description="Always 'simulated'")

    # ── Optional predictive fields (additive, never renamed/removed) ──────────
    predicted_eta_minutes: Optional[float] = Field(
        None,
        description=(
            "Predicted simulated minutes until this link crosses the D_FAIL "
            "degradation threshold.  Null when no reliable prediction is available."
        ),
    )
    prediction_confidence: Optional[str] = Field(
        None,
        description=(
            "Confidence level of the prediction: 'high' (R²≥0.8, n≥10), "
            "'medium' (R²≥0.5), or 'low'.  Null when no prediction is issued."
        ),
    )
    prediction_r2: Optional[float] = Field(
        None,
        description=(
            "R² of the Theil-Sen trend fit used for the prediction. "
            "Null when no prediction is issued."
        ),
    )


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
