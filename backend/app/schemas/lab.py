"""
Pydantic schemas for the lab simulation runner endpoint.

Follows docs/api-contract.md Section 3.
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator
from typing_extensions import Self

ScenarioType = Literal[
    "baseline",
    "degrade_link",
    "gradual_degradation",
    "access_point_failure",
    "upstream_failure",
    "ambiguous_fault",
]
SeverityType = Literal["low", "medium", "high"]


class LabRunRequest(BaseModel):
    scenario: ScenarioType = Field(
        ...,
        description=(
            "Scenario to run: baseline, degrade_link, gradual_degradation, "
            "access_point_failure, upstream_failure, ambiguous_fault"
        ),
        examples=["degrade_link"],
    )
    target_link_id: Optional[str] = Field(
        None,
        description="Target link ID (e.g. L2). Required for degrade_link scenario.",
        examples=["L2"],
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

    @model_validator(mode="after")
    def validate_required_targets(self) -> Self:
        if self.scenario in ("degrade_link", "gradual_degradation") and (
            not self.target_link_id or not self.target_link_id.strip()
        ):
            raise ValueError("target_link_id is required for degrade_link and gradual_degradation scenarios")
        if self.scenario in ("access_point_failure", "upstream_failure") and (
            not self.target_node_id or not self.target_node_id.strip()
        ):
            raise ValueError("target_node_id is required for component failure scenarios")
        return self


class LabRunResponse(BaseModel):
    run_id: str = Field(..., description="Unique test run identifier")
    data_source: str = Field("simulated", description="'simulated' or 'measured'")
    measurements_count: int = Field(..., description="Total measurements generated during test run")
    incident_id: Optional[str] = Field(
        None,
        description="ID of generated incident, or null if no incident detected",
    )
