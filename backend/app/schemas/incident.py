"""
Pydantic schemas for incident retrieval and affected-subscriber endpoints.

Follows docs/api-contract.md Sections 4, 5, and 6.
"""
from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

DataSource = Literal["simulated", "measured"]


class IncidentResponse(BaseModel):
    id: str = Field(..., description="Unique incident identifier (e.g. incident-001)")
    run_id: Optional[str] = Field(None, description="Associated test run ID if triggered by lab test")
    status: str = Field(..., description="Incident status (e.g. open, resolved)")
    suspected_component_id: Optional[str] = Field(None, description="Suspected faulty component ID (e.g. L2)")
    suspected_component_type: Optional[str] = Field(None, description="Type of suspected component (e.g. link, node)")
    summary: str = Field(..., description="Human-readable incident summary")
    confidence_score: Optional[float] = Field(
        None,
        description="Confidence score in range [0.0, 1.0]. Null until a validated scoring method is implemented.",
    )
    evidence: list[Any] = Field(
        default_factory=list,
        description="Observed metrics, baselines, and thresholds supporting the diagnosis.",
    )
    uncertainty_note: Optional[str] = Field(
        None,
        description="Explanation of diagnostic uncertainty or ambiguity.",
    )
    data_source: DataSource = Field(
        ...,
        description="'simulated' or 'measured'. Must never mislabel simulated data as measured.",
    )
    created_at: str = Field(
        ...,
        description="Creation timestamp in ISO 8601 UTC format (e.g. 2026-10-29T10:00:00Z).",
    )


class AffectedSubscriberItem(BaseModel):
    id: str = Field(..., description="Subscriber identifier (e.g. SUB101)")
    display_name: str = Field(..., description="Subscriber display name")
    access_point_id: str = Field(..., description="Access point subscriber connects through")


class AffectedSubscribersResponse(BaseModel):
    count: int = Field(..., description="Total count of affected subscribers. Must match len(subscribers).")
    subscribers: list[AffectedSubscriberItem] = Field(
        ...,
        description="List of subscriber records determined by network dependencies.",
    )


class BusinessImpactSubscriber(BaseModel):
    id: str = Field(..., description="Subscriber identifier (e.g. SUB101)")
    display_name: str = Field(..., description="Subscriber display name")
    plan: str = Field(..., description="Subscription plan (e.g. Basic, Enterprise, Community)")
    plan_price: float = Field(..., description="Monthly plan price in INR")
    access_point_id: str = Field(..., description="Connected Access Point ID")
    village: Optional[str] = Field(None, description="Village name")
    status: Optional[str] = Field("active", description="Subscription status")
    payment_status: Optional[str] = Field("paid", description="Payment status")
    due_date: Optional[str] = Field(None, description="Payment due date")


class BusinessImpactResponse(BaseModel):
    incident_id: str = Field(..., description="Incident identifier")
    status: str = Field(..., description="Incident status (e.g. open, closed)")
    suspected_component_id: Optional[str] = Field(None, description="Suspected faulty component")
    affected_count: int = Field(..., description="Count of affected subscribers / households")
    monthly_revenue_at_risk: float = Field(..., description="Monthly recurring revenue at risk in INR")
    revenue_at_risk: float = Field(..., description="Alias for monthly_revenue_at_risk")
    outage_duration_seconds: float = Field(..., description="Outage duration so far in seconds")
    outage_duration_minutes: float = Field(..., description="Outage duration so far in minutes")
    outage_duration_formatted: str = Field(..., description="Formatted outage duration string (e.g. '45m', '1h 15m')")
    sla_credit_rate_per_hour: float = Field(..., description="Configured SLA credit rate per hour")
    estimated_sla_credit_owed: float = Field(..., description="Estimated compensation / credit owed under SLA in INR")
    sla_credits_owed: float = Field(..., description="Alias for estimated_sla_credit_owed")
    households_by_village: dict[str, int] = Field(..., description="Number of affected households by village")
    affected_subscribers: list[BusinessImpactSubscriber] = Field(..., description="Detailed affected subscribers")
