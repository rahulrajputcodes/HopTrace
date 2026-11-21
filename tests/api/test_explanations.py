"""
Automated tests for Incident Explanation endpoint (Milestone 6).

Tests:
1. POST /api/v1/incidents/{incident_id}/explain returns 404 for unknown incident.
2. POST /api/v1/incidents/{incident_id}/explain returns 422 for invalid request body (empty/blank language).
3. POST /api/v1/incidents/{incident_id}/explain returns 503 when explanation provider is unavailable.
4. POST /api/v1/incidents/{incident_id}/explain returns 200 with grounded explanation when provider succeeds.
5. Provider registry selection for unavailable, sarvam, and invalid settings.
6. SarvamExplanationProvider initialization guards (rejects blank model, non-positive timeout).
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.init import DEMO_INCIDENTS
from app.main import app

DEMO_INCIDENT_ID = DEMO_INCIDENTS[0]["id"]
from app.providers.explanations import (
    ExplanationProvider,
    ExplanationProviderUnavailableError,
    SarvamExplanationProvider,
    UnavailableExplanationProvider,
)
from app.providers.registry import get_explanation_provider


class MockWorkingExplanationProvider(ExplanationProvider):
    """Test double provider returning verified grounded explanation."""

    @property
    def provider_name(self) -> str:
        return "mock_provider"

    def explain_incident(self, incident: dict[str, Any], language: str) -> str:
        return f"Incident {incident['id']} occurred on {incident['suspected_component_id']} in language {language}"


def test_explain_unknown_incident_returns_404(client: TestClient, isolated_db: str) -> None:
    """Non-existent incident ID must return 404 Not Found."""
    resp = client.post(
        "/api/v1/incidents/unknown-incident-9999/explain",
        json={"language": "hi"},
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_explain_empty_language_returns_422(client: TestClient, isolated_db: str) -> None:
    """Empty or whitespace-only language must return 422 Unprocessable Entity."""
    # Empty string
    r1 = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/explain",
        json={"language": ""},
    )
    assert r1.status_code == 422

    # Whitespace only
    r2 = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/explain",
        json={"language": "   "},
    )
    assert r2.status_code == 422

    # Missing field
    r3 = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/explain",
        json={},
    )
    assert r3.status_code == 422


def test_explain_provider_unavailable_returns_503(client: TestClient, isolated_db: str) -> None:
    """When the default unavailable provider is active, explain endpoint returns 503."""
    resp = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/explain",
        json={"language": "hi"},
    )
    assert resp.status_code == 503
    assert "not currently available" in resp.json()["detail"].lower()


def test_explain_success_with_provider(client: TestClient, isolated_db: str) -> None:
    """When a provider successfully returns an explanation, returns 200 with correct schema."""
    app.dependency_overrides[get_explanation_provider] = lambda: MockWorkingExplanationProvider()
    try:
        resp = client.post(
            f"/api/v1/incidents/{DEMO_INCIDENT_ID}/explain",
            json={"language": "hi"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["incident_id"] == DEMO_INCIDENT_ID
        assert data["language"] == "hi"
        assert DEMO_INCIDENT_ID in data["explanation"]
        assert data["provider"] == "mock_provider"
    finally:
        app.dependency_overrides.pop(get_explanation_provider, None)


def test_registry_explanation_provider_selection(monkeypatch) -> None:
    """Registry correctly selects UnavailableExplanationProvider or SarvamExplanationProvider."""
    # 1. unavailable
    monkeypatch.setattr(settings, "explanation_provider", "unavailable")
    p1 = get_explanation_provider()
    assert isinstance(p1, UnavailableExplanationProvider)
    assert p1.provider_name == "unavailable"

    # 2. sarvam
    monkeypatch.setattr(settings, "explanation_provider", "sarvam")
    monkeypatch.setattr(settings, "sarvam_api_key", "test-key")
    monkeypatch.setattr(settings, "sarvam_model", "sarvam-105b")
    monkeypatch.setattr(settings, "sarvam_timeout_seconds", 30.0)
    p2 = get_explanation_provider()
    assert isinstance(p2, SarvamExplanationProvider)
    assert p2.provider_name == "sarvam"

    # 3. invalid
    monkeypatch.setattr(settings, "explanation_provider", "unsupported_provider")
    with pytest.raises(ValueError) as exc:
        get_explanation_provider()
    assert "Unknown EXPLANATION_PROVIDER='unsupported_provider'" in str(exc.value)


def test_sarvam_provider_init_guards() -> None:
    """SarvamExplanationProvider rejects invalid constructor parameters."""
    # Blank model
    with pytest.raises(ValueError) as exc1:
        SarvamExplanationProvider(api_key="key", model="", timeout_seconds=10.0)
    assert "non-blank" in str(exc1.value)

    with pytest.raises(ValueError) as exc2:
        SarvamExplanationProvider(api_key="key", model="   ", timeout_seconds=10.0)
    assert "non-blank" in str(exc2.value)

    # Non-positive timeout
    with pytest.raises(ValueError) as exc3:
        SarvamExplanationProvider(api_key="key", model="sarvam-105b", timeout_seconds=0.0)
    assert "greater than zero" in str(exc3.value)

    with pytest.raises(ValueError) as exc4:
        SarvamExplanationProvider(api_key="key", model="sarvam-105b", timeout_seconds=-5.0)
    assert "greater than zero" in str(exc4.value)


def test_sarvam_provider_missing_key_raises_unavailable() -> None:
    """SarvamExplanationProvider raises ExplanationProviderUnavailableError if key is missing."""
    provider = SarvamExplanationProvider(api_key="", model="sarvam-105b", timeout_seconds=30.0)
    with pytest.raises(ExplanationProviderUnavailableError) as exc:
        provider.explain_incident({"id": "inc-1"}, "hi")
    assert "not configured" in str(exc.value).lower()


# ── Sarvam Provider Mocked End-to-End Tests ─────────────────────────────────

def _make_mock_response(content_bytes: bytes):
    """Helper to construct a mock urllib.request context manager."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = content_bytes
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None
    return mock_resp


def test_sarvam_provider_mock_hindi_success(client: TestClient, isolated_db: str, monkeypatch) -> None:
    """End-to-end: configured Sarvam provider generates Hindi explanation grounded in incident data."""
    import json

    monkeypatch.setattr(settings, "explanation_provider", "sarvam")
    monkeypatch.setattr(settings, "sarvam_api_key", "mock-secret-key-xyz")
    monkeypatch.setattr(settings, "sarvam_model", "sarvam-105b")
    monkeypatch.setattr(settings, "sarvam_timeout_seconds", 30.0)

    hindi_text = "नेटवर्क में लिंक L2 पर गंभीर खराबी पाई गई है। 2 ग्राहक प्रभावित हो सकते हैं।"
    sarvam_payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": hindi_text,
                }
            }
        ]
    }
    raw_response = json.dumps(sarvam_payload).encode("utf-8")

    with patch("urllib.request.urlopen", return_value=_make_mock_response(raw_response)):
        resp = client.post(
            f"/api/v1/incidents/{DEMO_INCIDENT_ID}/explain",
            json={"language": "hi"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["incident_id"] == DEMO_INCIDENT_ID
        assert data["language"] == "hi"
        assert data["explanation"] == hindi_text
        assert data["provider"] == "sarvam"


def test_sarvam_provider_mock_auth_failure_returns_503(
    client: TestClient, isolated_db: str, monkeypatch
) -> None:
    """When Sarvam API returns HTTP 401 Unauthorized, endpoint returns 503 without leaking credentials."""
    import urllib.error

    monkeypatch.setattr(settings, "explanation_provider", "sarvam")
    monkeypatch.setattr(settings, "sarvam_api_key", "secret-invalid-key")
    monkeypatch.setattr(settings, "sarvam_model", "sarvam-105b")

    http_error = urllib.error.HTTPError(
        url="https://api.sarvam.ai/v1/chat/completions",
        code=401,
        msg="Unauthorized",
        hdrs={},  # type: ignore[arg-type]
        fp=None,
    )

    with patch("urllib.request.urlopen", side_effect=http_error):
        resp = client.post(
            f"/api/v1/incidents/{DEMO_INCIDENT_ID}/explain",
            json={"language": "hi"},
        )
        assert resp.status_code == 503
        detail = resp.json()["detail"]
        assert "401" in detail
        # Strict security assertion: API key must never appear in response
        assert "secret-invalid-key" not in detail


def test_sarvam_provider_mock_timeout_returns_503(
    client: TestClient, isolated_db: str, monkeypatch
) -> None:
    """When Sarvam API times out, endpoint returns 503 with timeout message."""
    monkeypatch.setattr(settings, "explanation_provider", "sarvam")
    monkeypatch.setattr(settings, "sarvam_api_key", "mock-key")
    monkeypatch.setattr(settings, "sarvam_timeout_seconds", 5.0)

    with patch("urllib.request.urlopen", side_effect=TimeoutError()):
        resp = client.post(
            f"/api/v1/incidents/{DEMO_INCIDENT_ID}/explain",
            json={"language": "hi"},
        )
        assert resp.status_code == 503
        detail = resp.json()["detail"]
        assert "timed out after 5.0s" in detail


def test_sarvam_provider_mock_network_error_returns_503(
    client: TestClient, isolated_db: str, monkeypatch
) -> None:
    """When network connection to Sarvam fails, endpoint returns 503."""
    import urllib.error

    monkeypatch.setattr(settings, "explanation_provider", "sarvam")
    monkeypatch.setattr(settings, "sarvam_api_key", "mock-key")

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("DNS resolution failed")):
        resp = client.post(
            f"/api/v1/incidents/{DEMO_INCIDENT_ID}/explain",
            json={"language": "hi"},
        )
        assert resp.status_code == 503
        assert "could not reach the sarvam api" in resp.json()["detail"].lower()


def test_sarvam_provider_mock_malformed_response_returns_503(
    client: TestClient, isolated_db: str, monkeypatch
) -> None:
    """When Sarvam returns non-JSON or unexpected structure, endpoint returns 503."""
    monkeypatch.setattr(settings, "explanation_provider", "sarvam")
    monkeypatch.setattr(settings, "sarvam_api_key", "mock-key")

    # Non-JSON
    with patch("urllib.request.urlopen", return_value=_make_mock_response(b"<html>502 Bad Gateway</html>")):
        resp1 = client.post(
            f"/api/v1/incidents/{DEMO_INCIDENT_ID}/explain",
            json={"language": "hi"},
        )
        assert resp1.status_code == 503
        assert "could not be parsed as json" in resp1.json()["detail"].lower()

    # Missing choices
    with patch("urllib.request.urlopen", return_value=_make_mock_response(b'{"status": "ok"}')):
        resp2 = client.post(
            f"/api/v1/incidents/{DEMO_INCIDENT_ID}/explain",
            json={"language": "hi"},
        )
        assert resp2.status_code == 503
        assert "did not contain the expected" in resp2.json()["detail"].lower()


def test_sarvam_provider_missing_key_via_api_returns_503(
    client: TestClient, isolated_db: str, monkeypatch
) -> None:
    """When EXPLANATION_PROVIDER=sarvam but SARVAM_API_KEY is empty, endpoint returns 503."""
    monkeypatch.setattr(settings, "explanation_provider", "sarvam")
    monkeypatch.setattr(settings, "sarvam_api_key", "")

    resp = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/explain",
        json={"language": "hi"},
    )
    assert resp.status_code == 503
    assert "sarvam api key is not configured" in resp.json()["detail"].lower()
