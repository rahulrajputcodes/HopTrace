"""
Pydantic schemas for the lab simulation runner endpoint — HopTrace v2.

v2 LabRunResponse is significantly richer:
  - Embeds full IncidentDetails (not just incident_id)
  - Includes structured AIReport from Sarvam
  - Includes affected_subscribers list
  - Includes cascade/flapping detection flags
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator
from typing_extensions import Self

ScenarioType = Literal[
    "baseline",
    "degrade_link",
    "gradual_degradation",
    "access_point_failure",
    "upstream_failure",
    "ambiguous_fault",
    "cascade_fault",
    "flapping_link",
]
SeverityType = Literal["low", "medium", "high"]


class LabRunRequest(BaseModel):
    scenario: ScenarioType = Field(
        ...,
        description=(
            "Scenario to run: baseline, degrade_link, gradual_degradation, "
            "access_point_failure, upstream_failure, ambiguous_fault, cascade_fault, flapping_link"
        ),
        examples=["degrade_link"],
    )
    target_link_id: Optional[str] = Field(
        None,
        description="Target link ID (e.g. L3). Required for degrade_link and flapping_link scenarios.",
        examples=["L3"],
    )
    target_node_id: Optional[str] = Field(
        None,
        description="Target node ID (e.g. AP1). Required for component failure scenarios.",
        examples=["AP1"],
    )
    severity: SeverityType = Field(
        "medium",
        description="Fault severity: low, medium, high",
        examples=["high"],
    )
    # Optional: provide Sarvam key inline for AI explanation
    sarvam_api_key: Optional[str] = Field(
        None,
        description="Optional Sarvam AI key to generate structured AI report inline.",
    )
    language: str = Field(
        "en",
        description="Language for AI explanation (en, hi, ta, mr, te, kn, bn)",
    )

    @model_validator(mode="after")
    def validate_required_targets(self) -> Self:
        if self.scenario in ("degrade_link", "flapping_link", "gradual_degradation") and (
            not self.target_link_id or not self.target_link_id.strip()
        ):
            raise ValueError(
                "target_link_id is required for degrade_link, flapping_link, and gradual_degradation scenarios"
            )
        if self.scenario in ("access_point_failure", "upstream_failure") and (
            not self.target_node_id or not self.target_node_id.strip()
        ):
            raise ValueError("target_node_id is required for component failure scenarios")
        return self


class AIReportSchema(BaseModel):
    executive_summary: Optional[str] = None
    technical_diagnosis: Optional[str] = None
    field_operator_steps: List[str] = Field(default_factory=list)
    subscriber_impact_brief: Optional[str] = None
    escalation_required: Optional[bool] = None
    estimated_resolution_minutes: Optional[int] = None
    language: str = "en"
    provider: str = "unavailable"


class EvidenceItemSchema(BaseModel):
    metric: str
    observed_value: Any
    baseline_value: Any
    threshold: Any
    status: str = "anomaly"
    severity: str = "info"
    description: str


class IncidentSchema(BaseModel):
    id: str
    run_id: str
    status: str = "open"
    suspected_component_id: Optional[str] = None
    suspected_component_type: Optional[str] = None
    summary: str
    confidence_score: Optional[float] = None
    diagnostic_score: Optional[float] = None
    evidence: List[EvidenceItemSchema] = Field(default_factory=list)
    uncertainty_note: Optional[str] = None
    data_source: str = "simulated"
    created_at: str
    ai_report: Optional[AIReportSchema] = None


class AffectedSubscriberSchema(BaseModel):
    id: str
    display_name: str
    access_point_id: str


class LabRunResponse(BaseModel):
    run_id: str = Field(..., description="Unique test run identifier")
    data_source: str = Field("simulated", description="'simulated' or 'measured'")
    measurements_count: int = Field(..., description="Total measurements generated")
    incident_id: Optional[str] = Field(None, description="ID of generated incident, or null")
    # v2 enriched fields
    incident: Optional[IncidentSchema] = Field(None, description="Full incident details")
    affected_subscribers: List[AffectedSubscriberSchema] = Field(default_factory=list)
    affected_count: int = Field(0, description="Number of affected subscribers")
    network_status: str = Field("healthy", description="healthy | degraded | critical")
    cascade_detected: bool = Field(False)
    flapping_links: List[str] = Field(default_factory=list)
