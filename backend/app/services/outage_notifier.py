"""
Outage notification service.

Builds personalized outage alert messages in each subscriber's preferred language
using the configured ExplanationProvider (Sarvam AI / simulated) and dispatches them
via the active NotificationProvider (Console / Twilio).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.providers.explanations import ExplanationProvider
from app.providers.notifications import NotificationProvider

logger = logging.getLogger(__name__)


def extract_explanation_summary(raw_explanation: str) -> str:
    """Extract clean string summary if explanation provider returned JSON."""
    raw = (raw_explanation or "").strip()
    if raw.startswith("{") and raw.endswith("}"):
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return (
                    data.get("executive_summary")
                    or data.get("subscriber_impact_brief")
                    or data.get("technical_diagnosis")
                    or raw
                )
        except Exception:
            pass
    return raw


def build_subscriber_outage_message(
    incident: Dict[str, Any],
    subscriber: Dict[str, Any],
    explanation_provider: ExplanationProvider,
    language_cache: Optional[Dict[str, str]] = None,
) -> str:
    """
    Build a personalized outage alert in the subscriber's preferred language.

    Uses explanation_provider to generate a grounded explanation for the incident,
    cached per language to minimize LLM/service overhead.
    """
    lang = (subscriber.get("preferred_language") or "hi").lower().strip()
    cache = language_cache if language_cache is not None else {}

    if lang not in cache:
        try:
            raw_expl = explanation_provider.explain_incident(incident, language=lang)
            clean_text = extract_explanation_summary(raw_expl)
        except Exception as exc:
            logger.warning("Failed to generate explanation for language %s: %s", lang, exc)
            raise
        cache[lang] = clean_text

    base_text = cache[lang]
    sub_name = subscriber.get("display_name") or subscriber.get("id") or "Subscriber"

    # Friendly localized alert framing
    if lang.startswith("hi"):
        return f"नमस्ते {sub_name}, ग्राम नेट सूचना: {base_text} तकनीकी टीम बहाली कार्य कर रही है।"
    elif lang.startswith("ta"):
        return f"வணக்கம் {sub_name}, கிராம் நெட் அறிவிப்பு: {base_text} பழுதுபார்க்கும் பணி நடைபெறுகிறது."
    elif lang.startswith("mr"):
        return f"नमस्कार {sub_name}, ग्राम नेट सूचना: {base_text} दुरुस्तीचे काम सुरू आहे."
    elif lang.startswith("te"):
        return f"నమస్కారం {sub_name}, గ్రామ్ నెట్ సమాచారం: {base_text} సాంకేతిక బృందం పనిచేస్తోంది."
    elif lang.startswith("kn"):
        return f"ನಮಸ್ಕಾರ {sub_name}, ಗ್ರಾಮ್ ನೆಟ್ ಸೂಚನೆ: {base_text} ತಾಂತ್ರಿಕ ತಂಡ ಕಾರ್ಯನಿರ್ವಹಿಸುತ್ತಿದೆ."
    elif lang.startswith("bn"):
        return f"নমস্কার {sub_name}, গ্রাম নেট বিজ্ঞপ্তি: {base_text} মেরামতের কাজ চলছে।"
    else:
        return f"Dear {sub_name}, GramNet Alert: {base_text} Field restoration is in progress."


def generate_notification_previews(
    incident: Dict[str, Any],
    subscribers: List[Dict[str, Any]],
    explanation_provider: ExplanationProvider,
    channel: str = "sms",
) -> List[Dict[str, Any]]:
    """Build preview items for all targeted subscribers in their preferred languages."""
    lang_cache: Dict[str, str] = {}
    previews = []

    for sub in subscribers:
        phone = sub.get("phone") or "+919876543200"
        lang = (sub.get("preferred_language") or "hi").strip()
        msg = build_subscriber_outage_message(
            incident=incident,
            subscriber=sub,
            explanation_provider=explanation_provider,
            language_cache=lang_cache,
        )
        previews.append({
            "subscriber_id": sub.get("id"),
            "subscriber_name": sub.get("display_name", sub.get("id")),
            "phone": phone,
            "preferred_language": lang,
            "channel": channel.lower(),
            "message": msg,
        })

    return previews


def dispatch_outage_notifications(
    incident: Dict[str, Any],
    subscribers: List[Dict[str, Any]],
    notification_provider: NotificationProvider,
    explanation_provider: ExplanationProvider,
    channel: str = "sms",
) -> Dict[str, Any]:
    """
    Generate and dispatch outage notifications to all target subscribers.
    """
    previews = generate_notification_previews(
        incident=incident,
        subscribers=subscribers,
        explanation_provider=explanation_provider,
        channel=channel,
    )

    deliveries = []
    sent_count = 0
    failed_count = 0

    for item in previews:
        sub_id = item["subscriber_id"]
        recipient = item["phone"]
        msg = item["message"]
        try:
            res = notification_provider.send_notification(
                recipient=recipient,
                message=msg,
                channel=channel,
                subscriber_id=sub_id,
            )
            deliveries.append({
                "subscriber_id": sub_id,
                "recipient": recipient,
                "status": res.get("status", "sent"),
                "message_id": res.get("message_id"),
                "channel": channel.lower(),
                "provider": notification_provider.provider_name,
                "message": msg,
            })
            sent_count += 1
        except Exception as exc:
            logger.error("Failed to deliver notification to %s: %s", sub_id, exc)
            deliveries.append({
                "subscriber_id": sub_id,
                "recipient": recipient,
                "status": "failed",
                "error": str(exc),
                "channel": channel.lower(),
                "provider": notification_provider.provider_name,
                "message": msg,
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
