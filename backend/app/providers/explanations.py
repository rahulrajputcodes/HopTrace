"""
Incident explanation provider interface and base implementations.

Defines the contract for natural language explanation generation grounded in verified
incident data. Implementations (e.g. Sarvam AI, simulated, or template providers)
plug in behind this interface to keep the API layer cleanly decoupled from external LLM providers.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any


class ExplanationProviderUnavailableError(RuntimeError):
    """Raised when the configured explanation provider is unreachable, misconfigured, or unavailable."""
    pass


class ExplanationProvider(ABC):
    """Abstract base class for incident explanation providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique identifier for this explanation provider (e.g. 'unavailable', 'sarvam', 'simulated')."""
        ...

    @abstractmethod
    def explain_incident(self, incident: dict[str, Any], language: str) -> str:
        """
        Generate a natural language explanation for a verified incident in the requested language.

        Args:
            incident: Verified incident dictionary containing diagnostic details (evidence, suspected component, summary).
            language: Target language code (e.g. 'hi' for Hindi, 'en' for English).

        Returns:
            Grounded natural language explanation string.

        Raises:
            ExplanationProviderUnavailableError: When the explanation provider is offline,
                unconfigured, or fails to generate an explanation.
        """
        ...

    def generate_speech(
        self,
        text: str,
        language_code: str = "hi-IN",
        speaker: str = "meera",
    ) -> str:
        """
        Synthesize text into speech audio bytes (base64-encoded).

        Optional capability implemented by speech-capable providers like Sarvam AI.
        """
        raise ExplanationProviderUnavailableError(
            f"Speech synthesis is not supported by {self.provider_name} provider."
        )


class UnavailableExplanationProvider(ExplanationProvider):
    """
    Default fallback provider when no live explanation service (e.g. Sarvam) is configured.

    Honest failure behavior: refuses to fabricate explanations and raises ExplanationProviderUnavailableError.
    """

    @property
    def provider_name(self) -> str:
        return "unavailable"

    def explain_incident(self, incident: dict[str, Any], language: str) -> str:
        """
        Refuses explanation generation and raises ExplanationProviderUnavailableError.

        Raises:
            ExplanationProviderUnavailableError: Always, indicating the explanation service is unavailable.
        """
        raise ExplanationProviderUnavailableError(
            "The configured incident explanation provider is not currently available. "
            "Please provide a Sarvam API key in the top bar or set SARVAM_API_KEY in .env."
        )


class SimulatedExplanationProvider(ExplanationProvider):
    """
    Simulated explanation provider for live demo or offline environments.

    Produces realistic, grounded Hindi and English incident briefings based on verified
    incident facts and telemetry metrics without requiring external API access.
    """

    @property
    def provider_name(self) -> str:
        return "simulated"

    def explain_incident(self, incident: dict[str, Any], language: str) -> str:
        component = incident.get("suspected_component_id") or "अज्ञात घटक"
        summary = incident.get("summary") or "नेटवर्क व्यवधान"
        conf = incident.get("confidence_score")
        conf_pct = int(conf * 100) if conf is not None else 90
        evidence_list = incident.get("evidence") or []
        ev_text = ""
        if isinstance(evidence_list, list) and evidence_list:
            first_ev = evidence_list[0]
            if isinstance(first_ev, dict):
                ev_text = first_ev.get("description") or f"{first_ev.get('metric')}: {first_ev.get('observed_value')}"
            else:
                ev_text = str(first_ev)

        lang_lower = language.lower()
        if lang_lower.startswith("hi"):
            return (
                f"HopTrace नेटवर्क विश्लेषण: घटक '{component}' पर गंभीर व्यवधान पाया गया है "
                f"(विश्वास स्तर: {conf_pct}%)। विवरण: {summary}। "
                + (f"निरीक्षित साक्ष्य: {ev_text}। " if ev_text else "")
                + f"प्रभावित क्षेत्र में इंटरनेट सेवा बाधित हो सकती है। कृपया नोड बिजली आपूर्ति और वायरलेस लिंक की जाँच करें।"
            )
        elif lang_lower.startswith("mr"):
            return (
                f"HopTrace नेटवर्क विश्लेषण: घटक '{component}' वर समस्या आढळली आहे "
                f"(विश्वास: {conf_pct}%)। तपशील: {summary}। "
                + (f"पुरावा: {ev_text}। " if ev_text else "")
                + f"कृपया लिंक आणि पॉवर सप्लाय तपासा."
            )
        else:
            return (
                f"HopTrace Incident Analysis: High-severity condition identified on component '{component}' "
                f"(Confidence: {conf_pct}%). Summary: {summary}. "
                + (f"Key Evidence: {ev_text}. " if ev_text else "")
                + f"Downstream subscribers may experience service outage. Recommend immediate physical link and power inspection."
            )


# Fields from the incident record that are safe and relevant to send to an external API.
# Subscriber personal data and unrelated internal fields are explicitly excluded.
_INCIDENT_FIELDS_FOR_PROMPT: tuple[str, ...] = (
    "id",
    "run_id",
    "status",
    "suspected_component_id",
    "suspected_component_type",
    "summary",
    "confidence_score",
    "diagnostic_score",
    "evidence",
    "uncertainty_note",
    "data_source",
    "created_at",
)

_SARVAM_ENDPOINT = "https://api.sarvam.ai/v1/chat/completions"
_SARVAM_TTS_ENDPOINT = "https://api.sarvam.ai/text-to-speech"

_SYSTEM_PROMPT = (
    "You are an expert network fault analyst for a rural Indian ISP. "
    "You produce ONLY a valid JSON object — no markdown, no prose outside the JSON.\n\n"
    "Output format (strict JSON):\n"
    "{\n"
    '  "executive_summary": "2-sentence plain-language summary for the ISP owner",\n'
    '  "technical_diagnosis": "Technical root-cause with evidence chain",\n'
    '  "field_operator_steps": ["Step 1: ...", "Step 2: ...", "Step 3: ..."],\n'
    '  "subscriber_impact_brief": "WhatsApp-ready message in the target language (max 160 chars)",\n'
    '  "escalation_required": true/false,\n'
    '  "estimated_resolution_minutes": <integer>\n'
    "}\n\n"
    "Rules:\n"
    "- Use ONLY facts present in the incident data. Do not fabricate.\n"
    "- field_operator_steps: 3–5 actionable steps, specific to the suspected component.\n"
    "- subscriber_impact_brief: Write in the target language specified by the user.\n"
    "- escalation_required: true if confidence < 0.6 or if multiple villages affected.\n"
    "- estimated_resolution_minutes: realistic estimate (15–240 min range).\n"
    "- Respond ONLY with the JSON object. No explanations outside it."
)


class SarvamExplanationProvider(ExplanationProvider):
    """
    Explanation provider backed by the Sarvam AI chat-completions API and Bulbul TTS API.

    Communicates with https://api.sarvam.ai/v1/chat/completions and
    https://api.sarvam.ai/text-to-speech using Python's standard-library urllib —
    no additional runtime dependencies required.

    Configuration is injected at construction time via the provider registry;
    credentials are never stored in class attributes visible in tracebacks or logs.
    """

    def __init__(self, api_key: str, model: str = "sarvam-105b", timeout_seconds: float = 30.0) -> None:
        """
        Args:
            api_key: Sarvam subscription key (api-subscription-key header value).
                     Must be non-empty; validated at explain_incident call time.
            model: Sarvam model identifier (e.g. 'sarvam-105b'). Must be non-blank.
            timeout_seconds: HTTP request timeout in seconds. Must be positive.

        Raises:
            ValueError: If model is blank or timeout_seconds is not positive.
                        Error messages never contain credentials.
        """
        if not model or not model.strip():
            raise ValueError(
                "sarvam_model must be a non-blank string (e.g. 'sarvam-105b')."
            )
        if timeout_seconds <= 0:
            raise ValueError(
                f"sarvam_timeout_seconds must be greater than zero; got {timeout_seconds!r}."
            )
        self._api_key = api_key
        self._model = model.strip()
        self._timeout = timeout_seconds

    @property
    def provider_name(self) -> str:
        return "sarvam"

    def explain_incident(self, incident: dict[str, Any], language: str) -> str:
        """
        Generate a grounded natural language explanation via the Sarvam AI API.

        Args:
            incident: Verified incident dictionary. Only a safe, relevant subset of
                      fields is forwarded to the external API.
            language: BCP-47 / ISO 639-1 language code (e.g. 'hi', 'en', 'ta').

        Returns:
            Non-empty explanation string in the requested language.

        Raises:
            ExplanationProviderUnavailableError: For missing API key, network errors,
                HTTP errors, timeouts, malformed responses, or empty content.
                The API key is never included in the error message.
        """
        if not self._api_key:
            raise ExplanationProviderUnavailableError(
                "Sarvam API key is not configured. "
                "Set SARVAM_API_KEY in your .env file or supply it in the UI to enable this provider."
            )

        safe_incident = {
            field: incident[field]
            for field in _INCIDENT_FIELDS_FOR_PROMPT
            if field in incident
        }

        user_message = (
            f"Language: {language}\n\n"
            f"Incident data:\n{json.dumps(safe_incident, indent=2, default=str)}"
        )

        payload = json.dumps(
            {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.2,
                "max_tokens": 1000,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            url=_SARVAM_ENDPOINT,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "api-subscription-key": self._api_key,
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            raise ExplanationProviderUnavailableError(
                f"Sarvam API returned HTTP {exc.code}. "
                "Check that the API key is valid and the endpoint is reachable."
            ) from exc
        except urllib.error.URLError as exc:
            raise ExplanationProviderUnavailableError(
                "Could not reach the Sarvam API. "
                "Check network connectivity and try again."
            ) from exc
        except (TimeoutError, OSError) as exc:
            raise ExplanationProviderUnavailableError(
                f"Sarvam API request timed out after {self._timeout}s."
            ) from exc

        try:
            body = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ExplanationProviderUnavailableError(
                "Sarvam API returned a response that could not be parsed as JSON."
            ) from exc

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ExplanationProviderUnavailableError(
                "Sarvam API response did not contain the expected "
                "'choices[0].message.content' field."
            ) from exc

        if not isinstance(content, str) or not content.strip():
            raise ExplanationProviderUnavailableError(
                "Sarvam API returned an empty or non-string explanation."
            )

        return content

    def generate_speech(
        self,
        text: str,
        language_code: str = "hi-IN",
        speaker: str = "meera",
    ) -> str:
        """
        Synthesize text into speech audio bytes (base64-encoded) using Sarvam Bulbul TTS API.

        Args:
            text: Text to synthesize (max 500 characters).
            language_code: Target language code (e.g. 'hi-IN', 'en-IN').
            speaker: Speaker persona ('meera', 'shubh', etc.).

        Returns:
            Base64 encoded MP3/WAV audio string.
        """
        if not self._api_key:
            raise ExplanationProviderUnavailableError(
                "Sarvam API key is not configured for voice synthesis."
            )

        clean_text = text.strip()[:500]
        if not clean_text:
            raise ValueError("Text for speech synthesis cannot be empty.")

        payload = json.dumps(
            {
                "inputs": [clean_text],
                "target_language_code": language_code,
                "speaker": speaker,
                "pitch": 0,
                "pace": 1.0,
                "loudness": 1.5,
                "speech_sample_rate": 8000,
                "enable_preprocessing": True,
                "model": "bulbul:v1",
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            url=_SARVAM_TTS_ENDPOINT,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "api-subscription-key": self._api_key,
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            raise ExplanationProviderUnavailableError(
                f"Sarvam TTS returned HTTP {exc.code}."
            ) from exc
        except urllib.error.URLError as exc:
            raise ExplanationProviderUnavailableError(
                "Could not reach the Sarvam TTS service."
            ) from exc
        except (TimeoutError, OSError) as exc:
            raise ExplanationProviderUnavailableError(
                f"Sarvam TTS request timed out after {self._timeout}s."
            ) from exc

        try:
            body = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ExplanationProviderUnavailableError(
                "Sarvam TTS response could not be parsed as JSON."
            ) from exc

        # Sarvam Bulbul returns "audios": ["<base64>"] or "audio": "<base64>"
        audio_b64 = None
        if "audios" in body and isinstance(body["audios"], list) and len(body["audios"]) > 0:
            audio_b64 = body["audios"][0]
        elif "audio" in body and isinstance(body["audio"], str):
            audio_b64 = body["audio"]

        if not audio_b64:
            raise ExplanationProviderUnavailableError(
                "Sarvam TTS response did not contain audio data."
            )

        return audio_b64
