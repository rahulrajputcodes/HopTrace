"""
Lab test simulation runner endpoint — HopTrace v2.

POST /api/v1/lab/run

v2 changes:
- Returns full IncidentDetails embedded in response (not just incident_id)
- Returns affected_subscribers list
- Returns cascade/flapping detection flags
- network_status field
- New scenario types: cascade_fault, flapping_link
"""
from __future__ import annotations

import logging
import sqlite3
from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.db.connection import get_db
from app.db.repository import create_incident, get_incident
from app.engine.facade import get_engine, get_incident_details, get_topology, run_scenario
from app.engine.time_series import get_time_series_store
from app.schemas.lab import (
    AffectedSubscriberSchema,
    AIReportSchema,
    EvidenceItemSchema,
    IncidentSchema,
    LabRunRequest,
    LabRunResponse,
)

router = APIRouter(tags=["lab"])
logger = logging.getLogger(__name__)


@router.post(
    "/lab/run",
    response_model=LabRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Run a network test scenario (v2)",
    description=(
        "Executes a simulated telemetry lab scenario and triggers fault localization. "
        "v2: returns full incident details, affected subscribers, AI report, cascade/flapping flags."
    ),
)
def run_lab_scenario(
    payload: LabRunRequest,
    db: sqlite3.Connection = Depends(get_db),
) -> LabRunResponse:
    engine = get_engine()
    ts_store = get_time_series_store()

    # 1. Validate targets against actual topology
    try:
        topo = get_topology()
        known_links = {link.id for link in topo.links}
        known_ap_nodes = {node.id for node in topo.nodes if node.type == "access_point"}
        known_nodes = {node.id for node in topo.nodes}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Network topology unavailable: {exc}",
        ) from exc

    if payload.scenario in ("degrade_link", "flapping_link"):
        if payload.target_link_id not in known_links:
            raise HTTPException(
                status_code=422,
                detail=f"Target link '{payload.target_link_id}' not found in network topology. "
                       f"Valid links: {sorted(known_links)}",
            )
    elif payload.scenario == "gradual_degradation":
        if payload.target_link_id not in known_links:
            raise HTTPException(
                status_code=422,
                detail=f"Target link '{payload.target_link_id}' not found in network topology. "
                       f"Valid links: {sorted(known_links)}",
            )
    elif payload.scenario == "access_point_failure":
        if payload.target_node_id not in known_ap_nodes:
            raise HTTPException(
                status_code=422,
                detail=f"Target node '{payload.target_node_id}' is not a valid access point. "
                       f"Valid APs: {sorted(known_ap_nodes)}",
            )
    elif payload.scenario == "upstream_failure":
        if payload.target_node_id not in known_nodes:
            raise HTTPException(
                status_code=422,
                detail=f"Target node '{payload.target_node_id}' not found in topology.",
            )

    # 2. Execute scenario via engine facade
    try:
        engine = get_engine()

        # gradual_degradation: register ramp state, then run tick-0 snapshot.
        # At progress=0 the link is at baseline so incident_id is expected null.
        if payload.scenario == "gradual_degradation":
            engine.start_ramp(
                target_link_id=payload.target_link_id,  # type: ignore[arg-type]
                severity=payload.severity,
            )
            sim_response = engine.run_scenario(
                scenario="gradual_degradation",
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

    # 3. Push measurements into time-series store
    try:
        run_data = engine.get_run_measurements(sim_response.run_id)
        if run_data:
            ts_store.push_measurements_batch(run_data.measurements)
    except Exception:
        pass  # Non-critical

    # 4. Persist incident in SQLite if detected
    incident_details = None
    if sim_response.incident_id:
        incident_details = get_incident_details(sim_response.incident_id)
        if incident_details:
            existing = get_incident(db, incident_details.id)
            if existing is None:
                evidence_list = [
                    item.model_dump() if hasattr(item, "model_dump") else item
                    for item in (incident_details.evidence or [])
                ]
                try:
                    create_incident(db, {
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
                    })
                except Exception as exc:
                    logger.exception("Failed to persist incident %s to database", incident_details.id)
                    incident_details.status = "closed"
                    engine.close_open_incidents()
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to persist incident.",
                    ) from exc
    else:
        # A baseline run (or any run yielding no open incident) closes open incidents in the database
        try:
            from app.db.repository import close_open_incidents
            close_open_incidents(db)
        except Exception:
            pass

    # 5. Get affected subscribers
    affected_subs = []
    if incident_details and incident_details.suspected_component_id:
        try:
            affected_resp = engine.get_affected_subscribers(
                incident_id=incident_details.id,
                force_in_memory=True,
            )
            affected_subs = [
                AffectedSubscriberSchema(
                    id=s.id,
                    display_name=s.display_name,
                    access_point_id=s.access_point_id,
                )
                for s in affected_resp.subscribers
            ]
        except Exception:
            pass

    # 6. Cascade / flapping detection from time-series store
    cascade_detected = ts_store.detect_cascade(threshold_risk=60.0)
    flapping_links = ts_store.detect_flapping_links()

    # 7. Network status
    risk_snapshot = ts_store.get_risk_snapshot()
    max_risk = max((r["risk_score"] for r in risk_snapshot), default=0.0)
    if incident_details and incident_details.status == "open":
        network_status = "critical" if max_risk >= 70 else "degraded"
    elif cascade_detected:
        network_status = "degraded"
    else:
        network_status = "healthy"

    # 8. Build incident schema if available
    incident_schema = None
    if incident_details:
        evidence_schemas = [
            EvidenceItemSchema(
                metric=e.metric,
                observed_value=e.observed_value,
                baseline_value=e.baseline_value,
                threshold=e.threshold,
                status=e.status,
                severity=e.severity,
                description=e.description,
            )
            for e in (incident_details.evidence or [])
        ]

        # 9. Try Sarvam AI structured report if key provided
        ai_report_schema = None
        sarvam_key = (payload.sarvam_api_key or "").strip()
        if sarvam_key and incident_details.suspected_component_id:
            try:
                from app.providers.explanations import SarvamExplanationProvider
                provider = SarvamExplanationProvider(
                    api_key=sarvam_key,
                    model="sarvam-105b",
                    timeout_seconds=25.0,
                )
                explanation = provider.explain_incident(
                    incident=incident_details.model_dump(),
                    language=payload.language or "en",
                )
                # Parse structured JSON if returned, else wrap in executive_summary
                import json as _json
                try:
                    parsed = _json.loads(explanation)
                    ai_report_schema = AIReportSchema(
                        executive_summary=parsed.get("executive_summary"),
                        technical_diagnosis=parsed.get("technical_diagnosis"),
                        field_operator_steps=parsed.get("field_operator_steps", []),
                        subscriber_impact_brief=parsed.get("subscriber_impact_brief"),
                        escalation_required=parsed.get("escalation_required"),
                        estimated_resolution_minutes=parsed.get("estimated_resolution_minutes"),
                        language=payload.language or "en",
                        provider="sarvam",
                    )
                except (_json.JSONDecodeError, Exception):
                    ai_report_schema = AIReportSchema(
                        executive_summary=explanation,
                        language=payload.language or "en",
                        provider="sarvam",
                    )
            except Exception:
                pass

        incident_schema = IncidentSchema(
            id=incident_details.id,
            run_id=incident_details.run_id,
            status=incident_details.status,
            suspected_component_id=incident_details.suspected_component_id,
            suspected_component_type=incident_details.suspected_component_type,
            summary=incident_details.summary,
            confidence_score=incident_details.confidence_score,
            diagnostic_score=incident_details.diagnostic_score,
            evidence=evidence_schemas,
            uncertainty_note=incident_details.uncertainty_note,
            data_source=incident_details.data_source,
            created_at=incident_details.created_at,
            ai_report=ai_report_schema,
        )

        # 10. Automatically dispatch outage notifications if notification provider is enabled
        if incident_details.status == "open" and affected_subs:
            try:
                if settings.notification_provider.lower().strip() != "unavailable":
                    from app.db.repository import list_subscribers
                    from app.providers.registry import get_notification_provider, get_explanation_provider
                    from app.services.outage_notifier import dispatch_outage_notifications

                    notif_prov = get_notification_provider()
                    expl_prov = get_explanation_provider()
                    if notif_prov.provider_name != "unavailable" and expl_prov.provider_name != "unavailable":
                        all_subs = list_subscribers(db)
                        aff_ids = {s.id for s in affected_subs}
                        target_subs = [s for s in all_subs if s.get("id") in aff_ids]
                        if target_subs:
                            inc_dict = (
                                incident_details.model_dump()
                                if hasattr(incident_details, "model_dump")
                                else dict(incident_details)
                            )
                            dispatch_outage_notifications(
                                incident=inc_dict,
                                subscribers=target_subs,
                                notification_provider=notif_prov,
                                explanation_provider=expl_prov,
                                channel="sms",
                            )
            except Exception as exc:
                logger.warning("Automatic outage notification dispatch failed: %s", exc)

    return LabRunResponse(
        run_id=sim_response.run_id,
        data_source=sim_response.data_source,
        measurements_count=sim_response.measurements_count,
        incident_id=sim_response.incident_id,
        incident=incident_schema,
        affected_subscribers=affected_subs,
        affected_count=len(affected_subs),
        network_status=network_status,
        cascade_detected=cascade_detected,
        flapping_links=flapping_links,
    )
