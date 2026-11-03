"""
Lab test simulation runner endpoint.

Implements:
- POST /api/v1/lab/run

Follows docs/api-contract.md Section 3.
"""
from __future__ import annotations

import sqlite3
from fastapi import APIRouter, Depends, HTTPException, status

from app.db.connection import get_db
from app.db.repository import create_incident, get_incident
from app.engine.facade import get_engine, get_incident_details, get_topology, run_scenario
from app.engine.telemetry import BASELINE_TELEMETRY, EXTENDED_BASELINE_TELEMETRY
from app.schemas.lab import LabRunRequest, LabRunResponse

router = APIRouter(tags=["lab"])


@router.post(
    "/lab/run",
    response_model=LabRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Run a network test scenario",
    description=(
        "Executes a simulated telemetry lab scenario and triggers fault localization. "
        "Diagnostic engine infers suspected faults from observations without receiving the injected fault."
    ),
)
def run_lab_scenario(
    payload: LabRunRequest,
    db: sqlite3.Connection = Depends(get_db),
) -> LabRunResponse:
    """
    Validate test scenario and targets, execute telemetry simulation, and persist detected incidents.

    - 200: Test scenario executed successfully.
    - 422: Invalid scenario, invalid severity, missing required target, or invalid target ID.
    - 500: Persistence or execution failure.
    - 503: Network topology is currently unavailable.
    """
    # 1. Target validation against actual topology
    try:
        topo = get_topology()
        known_links = {link.id for link in topo.links} | set(EXTENDED_BASELINE_TELEMETRY.keys())
        known_ap_nodes = {node.id for node in topo.nodes if node.type == "access_point"}
        known_nodes = {node.id for node in topo.nodes}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Network topology is currently unavailable: {exc}",
        ) from exc

    link_scenarios = (
        "degrade_link",
        "gradual_degradation",
        "ramp_linear",
        "ramp_accelerating",
        "step_with_noise",
        "rain_fade",
        "flapping_precursor",
    )
    if payload.scenario in link_scenarios:
        if payload.target_link_id not in known_links:
            raise HTTPException(
                status_code=422,
                detail=f"Target link '{payload.target_link_id}' not found in network topology",
            )

    elif payload.scenario == "access_point_failure":
        if payload.target_node_id not in known_ap_nodes:
            raise HTTPException(
                status_code=422,
                detail=f"Target node '{payload.target_node_id}' is not a valid access point in network topology",
            )

    elif payload.scenario == "upstream_failure":
        if payload.target_node_id not in known_nodes:
            raise HTTPException(
                status_code=422,
                detail=f"Target node '{payload.target_node_id}' not found in network topology",
            )

    # 2. Execute scenario via engine facade
    # CRITICAL: Diagnostic engine infers root-cause solely from observations.
    # We do NOT pass or manufacture ground-truth fault into diagnosis.
    try:
        engine = get_engine()

        # Gradual/ramp scenarios: register ramp state, then run tick-0 snapshot.
        # At progress=0 the link is at baseline so incident_id is expected null.
        ramp_scenarios = (
            "gradual_degradation",
            "ramp_linear",
            "ramp_accelerating",
            "step_with_noise",
            "rain_fade",
            "flapping_precursor",
        )
        if payload.scenario in ramp_scenarios:
            if payload.target_link_id:
                engine.start_ramp(
                    target_link_id=payload.target_link_id,
                    severity=payload.severity,
                )
            sim_response = engine.run_scenario(
                scenario=payload.scenario,
                target_link_id=payload.target_link_id,
                severity=payload.severity,
                ramp_progress=0.0,
                force_in_memory=True,
            )
        else:
            # Any non-ramp scenario clears the ramp so the streaming loop reverts to baseline.
            if payload.scenario != "baseline":
                # Non-baseline, non-ramp: clear any stale ramp state
                engine.clear_ramp()
            sim_response = engine.run_scenario(
                scenario=payload.scenario,
                target_link_id=payload.target_link_id,
                target_node_id=payload.target_node_id,
                severity=payload.severity,
                force_in_memory=True,
            )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation execution failed: {exc}",
        ) from exc

    # 3. Persist incident in SQLite if engine detected an incident
    if sim_response.incident_id:
        incident_details = get_incident_details(sim_response.incident_id)
        if incident_details is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Incident details for '{sim_response.incident_id}' not found in engine",
            )

        existing = get_incident(db, incident_details.id)
        if existing is None:
            evidence_list = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in (incident_details.evidence or [])
            ]
            incident_record = {
                "id": incident_details.id,
                "run_id": incident_details.run_id,
                "status": incident_details.status,
                "suspected_component_id": incident_details.suspected_component_id,
                "suspected_component_type": incident_details.suspected_component_type,
                "summary": incident_details.summary,
                "confidence_score": incident_details.confidence_score,
                "evidence": evidence_list,
                "uncertainty_note": incident_details.uncertainty_note,
                "data_source": incident_details.data_source,
                "created_at": incident_details.created_at,
            }
            try:
                create_incident(db, incident_record)
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to persist incident in database: {exc}",
                ) from exc

    return LabRunResponse(
        run_id=sim_response.run_id,
        data_source=sim_response.data_source,
        measurements_count=sim_response.measurements_count,
        incident_id=sim_response.incident_id,
    )
