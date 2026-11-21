"""
Outage notification service (M3).

Builds personalized outage alert messages in each subscriber's preferred language
using deterministic templates (pure, reliable) and optional Sarvam AI translation,
dispatching them via the active NotificationProvider (Console / Twilio).
Enforces HopTrace branding and provides accurate message_source metadata.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.providers.notifications import NotificationProvider
from app.services.templates import render_message
from app.services.translate import translate

logger = logging.getLogger(__name__)


def _mask_phone(phone: str) -> str:
    """Mask phone numbers before writing to logs."""
    if not phone:
        return "****"
    cleaned = phone.strip()
    if len(cleaned) <= 4:
        return "****"
    if cleaned.startswith("+") and len(cleaned) >= 7:
        return f"{cleaned[:3]}****{cleaned[-4:]}"
    return f"****{cleaned[-4:]}"

AP_TO_VILLAGE: dict[str, str] = {
    "AP1": "Rampur",
    "AP2": "Rampur",
    "AP3": "Bhatpur",
    "AP4": "Bhatpur",
    "AP5": "Daulatpur",
    "AP6": "Daulatpur",
}


def resolve_subscriber_village(subscriber: Dict[str, Any]) -> str:
    """Resolve subscriber village from village field or access_point_id."""
    v = subscriber.get("village")
    if v and isinstance(v, str) and v.strip():
        return v.strip().capitalize()
    ap = subscriber.get("access_point_id") or subscriber.get("ap_id") or ""
    return AP_TO_VILLAGE.get(ap.upper(), "")


def generate_notification_previews(
    incident: Dict[str, Any],
    subscribers: List[Dict[str, Any]],
    channel: str = "sms",
    kind: str = "outage",
    use_translation: bool = False,
    explanation_provider: Any = None,
) -> List[Dict[str, Any]]:
    """
    Build preview items for all targeted subscribers in their preferred languages.

    Args:
        incident: Incident dictionary with component and diagnosis details.
        subscribers: List of subscriber records.
        channel: Delivery channel ('sms' or 'whatsapp').
        kind: Notification kind ('outage' or 'restored').
        use_translation: If True, attempts Sarvam translation with deterministic template fallback.
        explanation_provider: Optional explanation provider for backward compatibility.
    """
    previews = []
    comp_id = incident.get("suspected_component_id") or ""
    inc_id = incident.get("id") or ""

    for sub in subscribers:
        sub_id = sub.get("id") or "UNKNOWN"
        sub_name = sub.get("display_name") or sub.get("name") or sub_id
        phone = sub.get("phone") or ""
        lang = (sub.get("preferred_language") or "hi").strip().lower()
        village = resolve_subscriber_village(sub)

        ctx = {
            "subscriber_name": sub_name,
            "village": village,
            "component_id": comp_id,
            "incident_id": inc_id,
        }

        # Deterministic template for the subscriber's preferred language
        template_msg = render_message(kind=kind, lang=lang, ctx=ctx)

        if use_translation and lang != "en":
            # Generate English base and translate to subscriber language
            en_base = render_message(kind=kind, lang="en", ctx=ctx)
            msg, source = translate(en_base, lang, fallback_text=template_msg)
        else:
            msg = template_msg
            source = "template"

        previews.append({
            "subscriber_id": sub_id,
            "subscriber_name": sub_name,
            "phone": phone,
            "preferred_language": lang,
            "channel": channel.lower(),
            "message": msg,
            "message_source": source,
            "village": village,
            "eligible": bool(phone),
        })

    return previews


def dispatch_outage_notifications(
    incident: Dict[str, Any],
    subscribers: List[Dict[str, Any]],
    notification_provider: NotificationProvider,
    channel: str = "sms",
    kind: str = "outage",
    use_translation: bool = False,
    explanation_provider: Any = None,
) -> Dict[str, Any]:
    """
    Generate and dispatch outage notifications to all target subscribers.
    Preserves exact provider and delivery failure details without fabricating.
    """
    previews = generate_notification_previews(
        incident=incident,
        subscribers=subscribers,
        channel=channel,
        kind=kind,
        use_translation=use_translation,
        explanation_provider=explanation_provider,
    )

    deliveries = []
    sent_count = 0
    failed_count = 0

    for item in previews:
        sub_id = item["subscriber_id"]
        recipient = item["phone"]
        msg = item["message"]
        source = item["message_source"]
        sub_name = item["subscriber_name"]
        lang = item["preferred_language"]

        # Validate phone
        if not recipient or not recipient.strip():
            deliveries.append({
                "subscriber_id": sub_id,
                "subscriber_name": sub_name,
                "recipient": "",
                "status": "failed",
                "error": "Missing subscriber phone number",
                "channel": channel.lower(),
                "provider": notification_provider.provider_name,
                "message": msg,
                "message_source": source,
                "language": lang,
            })
            failed_count += 1
            continue

        try:
            res = notification_provider.send_notification(
                recipient=recipient,
                message=msg,
                channel=channel,
                subscriber_id=sub_id,
            )
            actual_provider = res.get("provider", notification_provider.provider_name)
            deliveries.append({
                "subscriber_id": sub_id,
                "subscriber_name": sub_name,
                "recipient": recipient,
                "status": res.get("status", "sent"),
                "message_id": res.get("message_id"),
                "channel": channel.lower(),
                "provider": actual_provider,
                "message": msg,
                "message_source": source,
                "language": lang,
                "sandboxed": res.get("sandboxed", False),
            })
            sent_count += 1
        except Exception as exc:
            logger.error(
                "Failed to deliver notification to subscriber %s (phone: %s): %s",
                sub_id,
                _mask_phone(recipient),
                type(exc).__name__,
            )
            deliveries.append({
                "subscriber_id": sub_id,
                "subscriber_name": sub_name,
                "recipient": recipient,
                "status": "failed",
                "error": str(exc),
                "channel": channel.lower(),
                "provider": notification_provider.provider_name,
                "message": msg,
                "message_source": source,
                "language": lang,
                "sandboxed": False,
            })
            failed_count += 1

    return {
        "incident_id": incident.get("id"),
        "provider": notification_provider.provider_name,
        "channel": channel.lower(),
        "total_targeted": len(subscribers),
        "sent_count": sent_count,
        "failed_count": failed_count,
        "deliveries": deliveries,
    }
