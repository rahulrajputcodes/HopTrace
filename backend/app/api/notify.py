"""
Notification API router (M3).

Implements:
- GET /api/v1/incidents/{incident_id}/notifications/preview
- POST /api/v1/incidents/{incident_id}/notify
- GET /api/v1/notifications/status
- GET /api/v1/incidents/{incident_id}/notifications (history)
- POST /api/v1/incidents/{incident_id}/notifications/retry (retry failed deliveries)
- POST /api/v1/voice (Sarvam text-to-speech)

Follows the shared architecture contract and integrates with dependency adapter,
SQLite persistence, and notification providers.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.config import settings
from app.db.connection import get_db
from app.db.repository import (
    create_notification_batch,
    create_notification_deliveries,
    get_incident,
    get_notification_batch_by_idempotency,
    get_notification_deliveries,
    get_subscribers_by_ids,
    list_notification_batches_by_incident,
    update_notification_delivery,
)
from app.engine.facade import get_incident_details
from app.providers.dependencies import (
    DependencyAnalysisAdapter,
    GraphEngineUnavailableError,
)
from app.providers.explanations import (
    ExplanationProviderUnavailableError,
)
from app.providers.notifications import (
    NotificationDeliveryError,
    NotificationProviderUnavailableError,
)
from app.providers.registry import (
    get_dependency_adapter,
    get_explanation_provider,
    get_notification_provider,
)
from app.schemas.notification import (
    NotificationBatchItem,
    NotificationDeliveryItem,
    NotificationHistoryResponse,
    NotificationPreviewItem,
    NotificationPreviewResponse,
    NotificationSendRequest,
    NotificationSendResponse,
    NotificationStatusResponse,
    VoiceRequest,
    VoiceResponse,
)
from app.services.outage_notifier import (
    dispatch_outage_notifications,
    generate_notification_previews,
)

router = APIRouter(tags=["notifications"])


def _get_active_incident(incident_id: str, db: sqlite3.Connection) -> dict[str, Any]:
    """Retrieve incident from engine facade or SQLite, or raise 404."""
    try:
        engine_incident = get_incident_details(incident_id)
        if engine_incident is not None:
            return engine_incident.model_dump()
    except Exception:
        pass

    inc = get_incident(db, incident_id)
    if inc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )
    return inc


@router.get(
    "/incidents/{incident_id}/notifications/preview",
    response_model=NotificationPreviewResponse,
    summary="Preview outage notifications for affected subscribers",
    description=(
        "Generates preview messages tailored to each affected subscriber's preferred language. "
        "Default preview uses deterministic templates (does not invoke Sarvam). "
        "Set translate=true to request Sarvam AI translation with deterministic template fallback."
    ),
)
def preview_incident_notifications(
    incident_id: str,
    channel: str = Query("sms", description="Delivery channel ('sms' or 'whatsapp')"),
    kind: str = Query("outage", description="Notification kind ('outage' or 'restored')"),
    translate: bool = Query(False, description="Whether to request Sarvam AI translation"),
    db: sqlite3.Connection = Depends(get_db),
    adapter: DependencyAnalysisAdapter = Depends(get_dependency_adapter),
) -> NotificationPreviewResponse:
    norm_channel = channel.lower().strip()
    if norm_channel not in ("sms", "whatsapp"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid channel '{channel}'. Allowed: 'sms', 'whatsapp'.",
        )

    norm_kind = kind.lower().strip()
    if norm_kind not in ("outage", "restored", "village_status"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid notification kind '{kind}'. Allowed: 'outage', 'restored', 'village_status'.",
        )

    incident = _get_active_incident(incident_id, db)

    # Check explanation provider availability
    try:
        explanation_provider = get_explanation_provider()
        if explanation_provider.provider_name == "unavailable":
            raise ExplanationProviderUnavailableError(
                "Explanation provider is unavailable or not configured"
            )
    except ExplanationProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    # Determine affected subscribers via dependency adapter
    try:
        raw_subs = adapter.get_affected_subscribers(
            incident_id=incident_id,
            suspected_component_id=incident.get("suspected_component_id"),
            suspected_component_type=incident.get("suspected_component_type"),
            db_conn=db,
        )
    except GraphEngineUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    sub_ids = [s["id"] for s in raw_subs if "id" in s]
    if sub_ids:
        full_subs = get_subscribers_by_ids(db, sub_ids)
        subs_map = {s["id"]: s for s in full_subs}
        enriched_subs = [subs_map.get(s["id"], s) for s in raw_subs]
    else:
        enriched_subs = raw_subs

    previews_data = generate_notification_previews(
        incident=incident,
        subscribers=enriched_subs,
        channel=norm_channel,
        kind=norm_kind,
        use_translation=translate,
    )

    return NotificationPreviewResponse(
        incident_id=incident_id,
        channel=norm_channel,
        affected_subscribers_count=len(previews_data),
        previews=[NotificationPreviewItem(**p) for p in previews_data],
    )


@router.post(
    "/incidents/{incident_id}/notify",
    response_model=NotificationSendResponse,
    summary="Send notifications to affected subscribers",
    description=(
        "Dispatches outage or restoration notifications to affected subscribers. "
        "Requires Idempotency-Key header to prevent duplicate sends."
    ),
)
def send_incident_notifications(
    incident_id: str,
    payload: Optional[NotificationSendRequest] = None,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: sqlite3.Connection = Depends(get_db),
    adapter: DependencyAnalysisAdapter = Depends(get_dependency_adapter),
) -> NotificationSendResponse:
    # 1. Idempotency Key — required for Twilio; auto-generated for console/sandbox
    #    Peek at the provider config to determine if Twilio is active.
    #    If the provider is misconfigured it will raise; we catch and 503 below.
    _is_twilio = False
    try:
        _peek_provider = get_notification_provider()
        _is_twilio = _peek_provider.provider_name == "twilio"
    except NotificationProviderUnavailableError:
        # Misconfigured provider — will be caught properly at step 3 below.
        pass

    clean_idempotency_key = (idempotency_key or "").strip()
    if _is_twilio and not clean_idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Idempotency-Key header is required for Twilio sends. "
                "Supply a unique key per send attempt to prevent duplicate messages."
            ),
        )
    if not clean_idempotency_key:
        # Console/sandbox: safe to auto-generate
        clean_idempotency_key = f"auto-{uuid4().hex}"

    # 2. Verify incident exists
    incident = _get_active_incident(incident_id, db)

    # 3. Check notification provider
    try:
        notif_provider = get_notification_provider()
        if notif_provider.provider_name == "unavailable":
            raise NotificationProviderUnavailableError(
                "Outage notification provider is not configured. Set NOTIFICATION_PROVIDER=console or twilio."
            )
    except NotificationProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    # Check explanation provider if translation requested
    try:
        explanation_provider = get_explanation_provider()
        if payload and payload.translate and explanation_provider.provider_name == "unavailable":
            raise ExplanationProviderUnavailableError(
                "Explanation provider is unavailable or not configured"
            )
    except ExplanationProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    req_channel = (payload.channel if payload else "sms") or "sms"
    req_kind = (payload.kind if payload else "outage") or "outage"
    use_trans = payload.translate if payload else False

    # 4. Determine affected subscribers BEFORE attempting the atomic batch insert
    try:
        raw_subs = adapter.get_affected_subscribers(
            incident_id=incident_id,
            suspected_component_id=incident.get("suspected_component_id"),
            suspected_component_type=incident.get("suspected_component_type"),
            db_conn=db,
        )
    except GraphEngineUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    affected_sub_ids = {s["id"] for s in raw_subs if "id" in s}

    # 5. Validate subscriber selection (before we touch the DB)
    if payload and payload.subscriber_ids is not None:
        target_ids = set(payload.subscriber_ids)
        unrelated = target_ids - affected_sub_ids
        if unrelated:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Subscriber(s) {sorted(list(unrelated))} are not affected by incident '{incident_id}'.",
            )
        raw_subs = [s for s in raw_subs if s.get("id") in target_ids]

    sub_ids = [s["id"] for s in raw_subs if "id" in s]
    if sub_ids:
        full_subs = get_subscribers_by_ids(db, sub_ids)
        subs_map = {s["id"]: s for s in full_subs}
        enriched_subs = [subs_map.get(s["id"], s) for s in raw_subs]
    else:
        enriched_subs = raw_subs

    # 6. ATOMICALLY insert the batch FIRST (before dispatching) so the DB
    #    UNIQUE(incident_id, idempotency_key) constraint is the authoritative
    #    concurrency guard.  If a concurrent request already inserted the same
    #    key, the INSERT raises IntegrityError and we return the existing batch.
    now_iso = datetime.now(timezone.utc).isoformat()
    batch_id = f"batch-{uuid4().hex[:12]}"

    try:
        create_notification_batch(
            db,
            {
                "id": batch_id,
                "incident_id": incident_id,
                "kind": req_kind,
                "channel": req_channel,
                "provider": notif_provider.provider_name,
                "idempotency_key": clean_idempotency_key,
                "created_by": "operator",
                "created_at": now_iso,
            },
        )
        db.commit()
    except sqlite3.IntegrityError:
        # Duplicate batch — concurrent or repeated request; return existing batch
        db.rollback()
        existing_batch = get_notification_batch_by_idempotency(db, incident_id, clean_idempotency_key)
        if existing_batch is not None:
            deliveries = existing_batch.get("deliveries", [])
            sent_c = sum(1 for d in deliveries if d.get("status") in ("sent", "delivered"))
            failed_c = sum(1 for d in deliveries if d.get("status") == "failed")
            return NotificationSendResponse(
                incident_id=incident_id,
                provider=existing_batch.get("provider", notif_provider.provider_name),
                channel=existing_batch.get("channel", req_channel),
                total_targeted=len(deliveries),
                sent_count=sent_c,
                failed_count=failed_c,
                deliveries=[NotificationDeliveryItem(**d) for d in deliveries],
                deduplicated=True,
                batch_id=existing_batch.get("id"),
                kind=existing_batch.get("kind", req_kind),
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Idempotency constraint violated but existing batch not found.",
        )

    # 7. Dispatch notifications (batch row already committed above)
    dispatch_res = dispatch_outage_notifications(
        incident=incident,
        subscribers=enriched_subs,
        notification_provider=notif_provider,
        channel=req_channel,
        kind=req_kind,
        use_translation=use_trans,
    )

    # 8. Persist delivery records and update batch provider from actual dispatch result
    delivery_records = []
    response_deliveries = []
    for d in dispatch_res["deliveries"]:
        deliv_id = f"deliv-{uuid4().hex[:12]}"
        record = {
            "id": deliv_id,
            "batch_id": batch_id,
            "subscriber_id": d["subscriber_id"],
            "language": d.get("language") or "hi",
            "message": d["message"],
            "message_source": d.get("message_source") or "template",
            "status": d["status"],
            "message_id": d.get("message_id"),
            "error": d.get("error"),
            "sandboxed": d.get("sandboxed", False),
            "updated_at": now_iso,
        }
        delivery_records.append(record)
        response_deliveries.append({
            **d,
            "updated_at": now_iso,
        })

    create_notification_deliveries(db, delivery_records)
    db.commit()

    return NotificationSendResponse(
        incident_id=incident_id,
        provider=dispatch_res["provider"],
        channel=dispatch_res["channel"],
        total_targeted=dispatch_res["total_targeted"],
        sent_count=dispatch_res["sent_count"],
        failed_count=dispatch_res["failed_count"],
        deliveries=[NotificationDeliveryItem(**d) for d in response_deliveries],
        deduplicated=False,
        batch_id=batch_id,
        kind=req_kind,
    )


@router.get(
    "/notifications/status",
    response_model=NotificationStatusResponse,
    summary="Get notification provider and service status",
    description="Returns current notification provider configuration, allowlist count, and service readiness.",
)
def get_notification_status() -> NotificationStatusResponse:
    notif_provider = get_notification_provider()
    expl_provider = get_explanation_provider()

    notif_avail = notif_provider.provider_name != "unavailable"
    expl_avail = expl_provider.provider_name != "unavailable"
    is_available = notif_avail and expl_avail

    reason = None
    if not notif_avail:
        reason = "Outage notification provider is not configured. Set NOTIFICATION_PROVIDER=console or twilio."
    elif not expl_avail:
        reason = "Explanation provider is not configured. Set EXPLANATION_PROVIDER=simulated or sarvam."

    twilio_ok = bool(
        settings.twilio_account_sid.strip()
        and settings.twilio_auth_token.strip()
        and settings.twilio_from_number.strip()
    )
    sarvam_ok = bool(settings.sarvam_api_key.strip())

    return NotificationStatusResponse(
        available=is_available,
        provider=notif_provider.provider_name,
        reason=reason,
        real_send_allowlist_count=len(settings.real_send_allowlist_set),
        sarvam_configured=sarvam_ok,
        twilio_configured=twilio_ok,
    )


@router.get(
    "/incidents/{incident_id}/notifications",
    response_model=NotificationHistoryResponse,
    summary="Get notification dispatch history for an incident",
    description="Returns all previously dispatched notification batches and their per-subscriber delivery records.",
)
def get_incident_notifications_history(
    incident_id: str,
    db: sqlite3.Connection = Depends(get_db),
) -> NotificationHistoryResponse:
    # Verify incident exists
    _get_active_incident(incident_id, db)

    batches_data = list_notification_batches_by_incident(db, incident_id)
    batches = []
    for b in batches_data:
        delivs = [NotificationDeliveryItem(**d) for d in b.get("deliveries", [])]
        batches.append(
            NotificationBatchItem(
                id=b["id"],
                incident_id=b["incident_id"],
                kind=b["kind"],
                channel=b["channel"],
                provider=b["provider"],
                created_at=b["created_at"],
                created_by=b.get("created_by"),
                deliveries=delivs,
            )
        )

    return NotificationHistoryResponse(
        incident_id=incident_id,
        batches=batches,
    )


@router.post(
    "/incidents/{incident_id}/notifications/retry",
    response_model=List[NotificationDeliveryItem],
    summary="Retry failed deliveries for an incident",
    description="Retries only eligible failed deliveries without resending successful ones.",
)
def retry_failed_notifications(
    incident_id: str,
    payload: Optional[Dict[str, Any]] = None,
    db: sqlite3.Connection = Depends(get_db),
) -> List[NotificationDeliveryItem]:
    _get_active_incident(incident_id, db)

    notif_provider = get_notification_provider()
    if notif_provider.provider_name == "unavailable":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Notification provider is unavailable.",
        )

    batch_id = payload.get("batch_id") if payload else None
    target_delivery_ids = set(payload.get("delivery_ids", [])) if payload and payload.get("delivery_ids") else None

    # Find batches for this incident
    batches = list_notification_batches_by_incident(db, incident_id)
    if not batches:
        return []

    target_batches = [b for b in batches if b["id"] == batch_id] if batch_id else batches

    retried_items: List[NotificationDeliveryItem] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for b in target_batches:
        for d in b.get("deliveries", []):
            if d.get("status") != "failed":
                continue  # Never resend successful deliveries
            if target_delivery_ids is not None and d["id"] not in target_delivery_ids:
                continue

            sub_id = d["subscriber_id"]
            recipient = d.get("recipient") or ""
            msg = d.get("message") or ""
            ch = b.get("channel") or "sms"

            if not recipient:
                continue

            try:
                res = notif_provider.send_notification(
                    recipient=recipient,
                    message=msg,
                    channel=ch,
                    subscriber_id=sub_id,
                )
                new_status = res.get("status", "sent")
                new_msg_id = res.get("message_id")
                new_err = None
            except Exception as exc:
                new_status = "failed"
                new_msg_id = None
                new_err = str(exc)

            update_notification_delivery(
                db,
                delivery_id=d["id"],
                status=new_status,
                message_id=new_msg_id,
                error=new_err,
                updated_at=now_iso,
            )

            retried_items.append(
                NotificationDeliveryItem(
                    subscriber_id=sub_id,
                    recipient=recipient,
                    status=new_status,
                    message_id=new_msg_id,
                    channel=ch,
                    provider=res.get("provider", notif_provider.provider_name) if new_status != "failed" else notif_provider.provider_name,
                    message=msg,
                    message_source=d.get("message_source", "template"),
                    error=new_err,
                    updated_at=now_iso,
                    subscriber_name=d.get("subscriber_name"),
                    language=d.get("language"),
                )
            )

    db.commit()
    return retried_items


@router.post(
    "/voice",
    response_model=VoiceResponse,
    summary="Synthesize alert message to voice audio (Sarvam AI)",
    description=(
        "Synthesizes given text (max 500 chars) into base64 WAV audio via Sarvam AI Bulbul TTS. "
        "Returns 400 on invalid input, 503 when Sarvam is unavailable or returns an error."
    ),
)
def synthesize_voice(
    payload: VoiceRequest,
) -> VoiceResponse:
    # VoiceRequest schema enforces min_length=1 and max_length=500 via Pydantic.
    # Explicit guard for empty/whitespace text after stripping.
    clean_text = (payload.text or "").strip()
    if not clean_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Voice text must be non-empty (after stripping whitespace).",
        )

    api_key = settings.sarvam_api_key.strip()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sarvam voice service is not configured. Set SARVAM_API_KEY in environment.",
        )

    from app.providers.explanations import SarvamExplanationProvider
    provider = SarvamExplanationProvider(
        api_key=api_key,
        model=settings.sarvam_model,
        timeout_seconds=settings.sarvam_timeout_seconds,
    )

    lang_code = "hi-IN" if payload.language.lower().startswith("hi") else "en-IN"
    speaker = (payload.speaker or "meera").strip().lower()

    try:
        audio_b64 = provider.generate_speech(
            text=clean_text,
            language_code=lang_code,
            speaker=speaker,
        )
        return VoiceResponse(
            audio_base64=audio_b64,
            mime="audio/wav",
            provider="sarvam",
        )
    except ValueError as exc:
        # Input validation errors (empty text, invalid speaker)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Sarvam voice synthesis failed: {exc}",
        ) from exc
