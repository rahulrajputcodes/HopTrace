"""
Pydantic schemas for test run measurements and telemetry retrieval.

Follows docs/api-contract.md Section 7.
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field

DataSource = Literal["simulated", "measured", "live"]


class MeasurementIngestItem(BaseModel):
    component_id: str = Field(
        ...,
        description="Network component identifier (e.g. L1, L2, AP1)",
        examples=["L3"],
    )
    latency_ms: Optional[float] = Field(
        None,
        description="Observed round-trip latency in milliseconds, or null if unmeasured/unavailable",
        examples=[45.2],
    )
    packet_loss_pct: Optional[float] = Field(
        None,
        description="Observed packet loss percentage [0.0 - 100.0], or null if unmeasured/unavailable",
        examples=[1.5],
    )
    throughput_mbps: Optional[float] = Field(
        None,
        description="Observed throughput in megabits per second, or null if unmeasured/unavailable",
        examples=[48.0],
    )
    connectivity_ok: bool = Field(
        True,
        description="Whether basic connectivity/reachability check succeeded",
        examples=[True],
    )
    timestamp: Optional[str] = Field(
        None,
        description="Measurement timestamp in ISO format (defaults to current UTC if omitted)",
        examples=["2026-11-04T12:00:00Z"],
    )


class MeasurementIngestResponse(BaseModel):
    status: str = "ok"
    ingested_count: int
    data_source: str = "live"
    incident_id: Optional[str] = None


class MeasurementResponse(BaseModel):
    component_id: str = Field(
        ...,
        description="Network component identifier (e.g. L1, L2, AP1)",
        examples=["L2"],
    )
    timestamp_utc: str = Field(
        ...,
        description="Measurement timestamp in ISO 8601 UTC format (e.g. 2026-10-29T10:00:00Z)",
        examples=["2026-10-29T10:00:00Z"],
    )
    latency_ms: Optional[float] = Field(
        None,
        description="Observed round-trip latency in milliseconds, or null if unmeasured/unavailable",
        examples=[180.0],
    )
    packet_loss_pct: Optional[float] = Field(
        None,
        description="Observed packet loss percentage [0.0 - 100.0], or null if unmeasured/unavailable",
        examples=[25.0],
    )
    throughput_mbps: Optional[float] = Field(
        None,
        description="Observed throughput in megabits per second, or null if unmeasured/unavailable",
        examples=[40.0],
    )
    connectivity_ok: bool = Field(
        ...,
        description="Whether basic connectivity/reachability check succeeded",
        examples=[True],
    )
    data_source: DataSource = Field(
        ...,
        description="'simulated' or 'measured'. Must never mislabel simulated data as measured",
        examples=["simulated"],
    )


class RunMeasurementsResponse(BaseModel):
    run_id: str = Field(
        ...,
        description="Unique test run identifier (e.g. run-001)",
        examples=["run-001"],
    )
    data_source: DataSource = Field(
        ...,
        description="'simulated' or 'measured'. Data origin of the measurements batch",
        examples=["simulated"],
    )
    measurements: list[MeasurementResponse] = Field(
        ...,
        description="List of component telemetry observations captured during this test run",
    )
