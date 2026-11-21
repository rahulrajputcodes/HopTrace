"""
Pydantic schemas for incident natural language explanation endpoint.

Follows docs/api-contract.md Section 10.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class IncidentExplanationRequest(BaseModel):
    language: str = Field(
        ...,
        description="Target language code for the explanation (e.g. 'hi' for Hindi, 'en' for English)",
        examples=["hi"],
    )
    api_key: Optional[str] = Field(
        None,
        description="Optional Sarvam API key override passed directly from runtime UI",
    )

    @field_validator("language")
    @classmethod
    def validate_language_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("language must not be empty or whitespace")
        return v.strip()


class IncidentExplanationResponse(BaseModel):
    incident_id: str = Field(
        ...,
        description="Unique identifier of the explained incident (e.g. incident-001)",
        examples=["incident-001"],
    )
    language: str = Field(
        ...,
        description="Language code of the explanation (e.g. hi, en)",
        examples=["hi"],
    )
    explanation: str = Field(
        ...,
        description="Natural language diagnostic explanation grounded in verified incident data",
        examples=["Hindi explanation based on verified incident data"],
    )
    provider: str = Field(
        ...,
        description="Explanation provider identifier (e.g. sarvam, template, simulated)",
        examples=["sarvam"],
    )


class AudioSpeechRequest(BaseModel):
    text: str = Field(
        ...,
        description="Text content to synthesize into speech",
    )
    language_code: str = Field(
        "hi-IN",
        description="Target language code (e.g. 'hi-IN', 'en-IN')",
    )
    speaker: str = Field(
        "meera",
        description="Sarvam voice speaker persona (e.g. 'meera', 'shubh')",
    )
    api_key: Optional[str] = Field(
        None,
        description="Optional Sarvam API key override",
    )


class AudioSpeechResponse(BaseModel):
    audio_base64: str = Field(
        ...,
        description="Base64-encoded audio bytes (MP3/WAV)",
    )
    format: str = Field(
        "mp3",
        description="Audio container format",
    )
    provider: str = Field(
        "sarvam",
        description="Audio synthesis provider",
    )
