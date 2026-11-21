"""
Translation service with Sarvam AI integration and deterministic fallback (M3).

Implements:
- translate(text: str, lang: str, fallback_text: str | None = None) -> tuple[str, str]
Returns:
  (text, source) where source is 'sarvam' or 'template'.

Never raises exceptions. Never returns empty string.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

_SARVAM_TRANSLATE_ENDPOINT = "https://api.sarvam.ai/translate"


def translate(
    text: str,
    lang: str,
    fallback_text: Optional[str] = None,
) -> tuple[str, str]:
    """
    Translate text to the target language using Sarvam AI if available,
    falling back deterministically to template text.

    Args:
        text: Source text to translate (typically English template).
        lang: Target language code ('hi', 'en', etc.).
        fallback_text: Optional pre-rendered deterministic fallback text
                       in target language.

    Returns:
        tuple of (translated_or_fallback_text, source)
        where source is either 'sarvam' or 'template'.
    """
    safe_text = (text or "").strip()
    safe_fallback = (fallback_text or safe_text).strip() or safe_text
    norm_lang = (lang or "en").strip().lower()

    # English target needs no AI translation
    if norm_lang == "en" or norm_lang.startswith("en-"):
        return safe_text, "template"

    api_key = getattr(settings, "sarvam_api_key", "").strip()
    if not api_key:
        return safe_fallback, "template"

    # Map simple codes to Sarvam BCP-47 codes (e.g. 'hi' -> 'hi-IN')
    target_code = f"{norm_lang}-IN" if "-" not in norm_lang else norm_lang
    timeout_sec = getattr(settings, "sarvam_timeout_seconds", 10.0)

    try:
        payload = json.dumps({
            "input": safe_text,
            "source_language_code": "en-IN",
            "target_language_code": target_code,
            "speaker_gender": "Female",
            "mode": "formal",
            "model": "mayura:v1",
        }).encode("utf-8")

        req = urllib.request.Request(
            url=_SARVAM_TRANSLATE_ENDPOINT,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "api-subscription-key": api_key,
            },
        )

        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8")

        body = json.loads(raw)
        translated = body.get("translated_text")
        if isinstance(translated, str) and translated.strip():
            return translated.strip(), "sarvam"

    except Exception as exc:
        logger.warning("Sarvam translation failed for lang %s: %s; using template fallback", norm_lang, exc)

    return safe_fallback, "template"
