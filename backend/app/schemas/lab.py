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
    "ramp_linear",
    "ramp_accelerating",
    "step_with_noise",
    "rain_fade",
    "diurnal_load",
    "flapping_precursor",
    "stable_noisy",
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
            "ramp_linear, ramp_accelerating, step_with_noise, rain_fade, "
            "diurnal_load, flapping_precursor, stable_noisy, "
            "access_point_failure, upstream_failure, ambiguous_fault"
        ),
        examples=["degrade_link"],
    )
    target_link_id: Optional[str] = Field(
        None,
        description="Target link ID (e.g. L2, L3, L7). Required for link degradation scenarios.",
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
        link_scenarios = (
            "degrade_link",
            "gradual_degradation",
            "ramp_linear",
            "ramp_accelerating",
            "step_with_noise",
            "rain_fade",
            "flapping_precursor",
        )
        if self.scenario in link_scenarios and (
            not self.target_link_id or not self.target_link_id.strip()
        ):
            raise ValueError(f"target_link_id is required for {self.scenario} scenario")
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
