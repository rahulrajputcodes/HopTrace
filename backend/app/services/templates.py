"""
Deterministic message templates for HopTrace notifications (M3).

Supported kinds:
- outage
- restored
- village_status

Supported languages:
- English: en
- Hindi: hi

Pure deterministic function, no network calls, never raises exceptions.
Unknown languages fall back to English.
Unknown message kinds return a safe documented fallback.
Branding is strictly HopTrace.
"""
from __future__ import annotations

from typing import Any, Mapping


def render_message(kind: str, lang: str, ctx: Mapping[str, Any] | None = None) -> str:
    """
    Render a localized notification message deterministically.

    Args:
        kind: Message kind ('outage', 'restored', 'village_status').
        lang: Language code ('en', 'hi', or other). Unknown languages fall back to 'en'.
        ctx: Template context values (subscriber_name, village, component_id, etc.).

    Returns:
        Rendered notification string. Never raises exceptions.
    """
    ctx_safe: dict[str, str] = {}
    if ctx and isinstance(ctx, Mapping):
        for k, v in ctx.items():
            ctx_safe[str(k)] = str(v) if v is not None else ""

    norm_lang = (lang or "en").strip().lower()
    if norm_lang not in ("en", "hi"):
        norm_lang = "en"

    name_en = ctx_safe.get("subscriber_name") or ctx_safe.get("name") or "Subscriber"
    name_hi = ctx_safe.get("subscriber_name") or ctx_safe.get("name") or "उपभोक्ता"
    village = ctx_safe.get("village") or ""

    norm_kind = (kind or "outage").strip().lower()

    if norm_kind == "outage":
        if norm_lang == "hi":
            if village:
                return (
                    f"नमस्ते {name_hi}, HopTrace सूचना: नेटवर्क खराबी के कारण {village} में इंटरनेट सेवा बाधित है। "
                    f"हमारी तकनीकी टीम जांच और बहाली का कार्य कर रही है।"
                )
            return (
                f"नमस्ते {name_hi}, HopTrace सूचना: नेटवर्क खराबी के कारण इंटरनेट सेवा बाधित है। "
                f"हमारी तकनीकी टीम जांच और बहाली का कार्य कर रही है।"
            )
        else:
            if village:
                return (
                    f"Dear {name_en}, HopTrace Alert: Internet service in {village} is currently disrupted "
                    f"due to a network fault. Our technical team is investigating and working on restoration."
                )
            return (
                f"Dear {name_en}, HopTrace Alert: Internet service is currently disrupted "
                f"due to a network fault. Our technical team is investigating and working on restoration."
            )

    elif norm_kind == "restored":
        if norm_lang == "hi":
            if village:
                return (
                    f"नमस्ते {name_hi}, HopTrace सूचना: {village} में इंटरनेट सेवा पूरी तरह से बहाल कर दी गई है। "
                    f"आपके धैर्य और सहयोग के लिए धन्यवाद।"
                )
            return (
                f"नमस्ते {name_hi}, HopTrace सूचना: इंटरनेट सेवा पूरी तरह से बहाल कर दी गई है। "
                f"आपके धैर्य और सहयोग के लिए धन्यवाद।"
            )
        else:
            if village:
                return (
                    f"Dear {name_en}, HopTrace Alert: Internet connectivity in {village} has been fully restored "
                    f"and verified. Thank you for your patience."
                )
            return (
                f"Dear {name_en}, HopTrace Alert: Internet connectivity has been fully restored "
                f"and verified. Thank you for your patience."
            )

    elif norm_kind == "village_status":
        status_val = ctx_safe.get("status") or "active"
        if norm_lang == "hi":
            village_label = village if village else "क्षेत्र"
            return (
                f"HopTrace स्थिति अपडेट ({village_label}): वर्तमान नेटवर्क स्थिति '{status_val}' है। "
                f"फील्ड टीम लगातार निगरानी कर रही है।"
            )
        else:
            village_label = village if village else "your area"
            return (
                f"HopTrace Status Update for {village_label}: Network status is currently '{status_val}'. "
                f"Field teams are actively monitoring connectivity."
            )

    # Safe fallback for unknown kind
    if norm_lang == "hi":
        return f"नमस्ते {name_hi}, HopTrace सूचना: आपके नेटवर्क कनेक्शन के संबंध में अपडेट। सहायता के लिए सपोर्ट से संपर्क करें।"
    return f"Dear {name_en}, HopTrace Notice: Update regarding your network connectivity. Please contact support for assistance."
