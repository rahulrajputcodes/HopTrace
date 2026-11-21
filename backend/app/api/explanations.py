"""
Incident explanation endpoint.

Implements:
- POST /api/v1/incidents/{incident_id}/explain
- POST /api/v1/incidents/{incident_id}/explain/audio
- POST /api/v1/explanations/audio

Follows docs/api-contract.md Section 10 with enhanced Sarvam AI voice capabilities.
"""
from __future__ import annotations

import sqlite3
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.db.connection import get_db
from app.db.repository import get_incident
from app.providers.explanations import (
    ExplanationProvider,
    ExplanationProviderUnavailableError,
    SarvamExplanationProvider,
)
from app.providers.registry import get_explanation_provider
from app.schemas.explanation import (
    AudioSpeechRequest,
    AudioSpeechResponse,
    IncidentExplanationRequest,
    IncidentExplanationResponse,
)

router = APIRouter(tags=["explanations"])


def _resolve_active_provider(
    default_provider: ExplanationProvider,
    api_key_override: Optional[str] = None,
) -> ExplanationProvider:
    """Selects Sarvam provider if dynamic or configured API key exists, else defaults to injected provider."""
    effective_key = (api_key_override or "").strip() or settings.sarvam_api_key.strip()
    if effective_key:
        return SarvamExplanationProvider(
            api_key=effective_key,
            model=settings.sarvam_model,
            timeout_seconds=settings.sarvam_timeout_seconds,
        )
    return default_provider


@router.post(
    "/incidents/{incident_id}/explain",
    response_model=IncidentExplanationResponse,
    status_code=status.HTTP_200_OK,
    summary="Explain incident in natural language",
    description=(
        "Generates an explainable root-cause summary for an incident in the requested language (e.g. Hindi). "
        "Explanations are grounded in verified diagnostic incident data via Sarvam AI."
    ),
)
def explain_incident(
    incident_id: str,
    payload: IncidentExplanationRequest,
    db: sqlite3.Connection = Depends(get_db),
    provider: ExplanationProvider = Depends(get_explanation_provider),
) -> IncidentExplanationResponse:
    """
    Validate incident existence, generate natural language explanation via configured or dynamic provider, and return result.

    - 200: Incident successfully explained.
    - 404: Incident not found in database.
    - 422: Invalid request payload (e.g. empty or blank language).
    - 503: Configured explanation provider is unavailable or offline.
    """
    # 1. Verify target incident exists in operational storage
    incident = get_incident(db, incident_id)
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )

    active_provider = _resolve_active_provider(provider, payload.api_key)

    # 2. Invoke explanation provider
    try:
        explanation_text = active_provider.explain_incident(incident, payload.language)
    except ExplanationProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return IncidentExplanationResponse(
        incident_id=incident_id,
        language=payload.language,
        explanation=explanation_text,
        provider=active_provider.provider_name,
    )


@router.post(
    "/incidents/{incident_id}/explain/audio",
    response_model=AudioSpeechResponse,
    status_code=status.HTTP_200_OK,
    summary="Synthesize incident explanation audio via Sarvam Bulbul TTS",
)
def synthesize_incident_audio(
    incident_id: str,
    payload: AudioSpeechRequest,
    provider: ExplanationProvider = Depends(get_explanation_provider),
) -> AudioSpeechResponse:
    """Converts diagnostic briefing text into neural voice audio using Sarvam AI Bulbul TTS."""
    active_provider = _resolve_active_provider(provider, payload.api_key)

    try:
        audio_b64 = active_provider.generate_speech(
            text=payload.text,
            language_code=payload.language_code,
            speaker=payload.speaker,
        )
    except ExplanationProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Speech synthesis error: {str(exc)}",
        ) from exc

    return AudioSpeechResponse(
        audio_base64=audio_b64,
        format="mp3",
        provider=active_provider.provider_name,
    )


@router.post(
    "/explanations/audio",
    response_model=AudioSpeechResponse,
    status_code=status.HTTP_200_OK,
    summary="Synthesize general text audio via Sarvam Bulbul TTS",
)
def synthesize_general_audio(
    payload: AudioSpeechRequest,
    provider: ExplanationProvider = Depends(get_explanation_provider),
) -> AudioSpeechResponse:
    """Converts arbitrary briefing text into neural voice audio using Sarvam AI Bulbul TTS."""
    active_provider = _resolve_active_provider(provider, payload.api_key)

    try:
        audio_b64 = active_provider.generate_speech(
            text=payload.text,
            language_code=payload.language_code,
            speaker=payload.speaker,
        )
    except ExplanationProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return AudioSpeechResponse(
        audio_base64=audio_b64,
        format="mp3",
        provider=active_provider.provider_name,
    )
