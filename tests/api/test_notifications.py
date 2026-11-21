"""
Tests for outage notification provider, preview, and dispatch APIs.
"""
from __future__ import annotations

import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.init import DEMO_INCIDENTS
from app.main import app
from app.providers.notifications import (
    ConsoleNotificationProvider,
    NotificationProviderUnavailableError,
    TwilioNotificationProvider,
)
from app.providers.registry import get_notification_provider, get_explanation_provider

DEMO_INCIDENT_ID = DEMO_INCIDENTS[0]["id"]


def test_notification_preview_unknown_incident_404(client: TestClient, isolated_db: str) -> None:
    """Previewing notifications for a nonexistent incident returns 404."""
    response = client.get("/api/v1/incidents/nonexistent-id-999/notifications/preview")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_notification_preview_503_when_explanation_unavailable(
    client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When explanation provider is unavailable, preview returns HTTP 503."""
    monkeypatch.setattr(settings, "explanation_provider", "unavailable")
    response = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notifications/preview")
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()


def test_notification_preview_success_localized(
    client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Preview returns localized alert messages tailored to subscriber preferred language."""
    monkeypatch.setattr(settings, "explanation_provider", "simulated")
    response = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notifications/preview")
    assert response.status_code == 200

    data = response.json()
    assert data["incident_id"] == DEMO_INCIDENT_ID
    assert data["channel"] == "sms"
    assert data["affected_subscribers_count"] > 0
    assert len(data["previews"]) == data["affected_subscribers_count"]

    first_item = data["previews"][0]
    assert "subscriber_id" in first_item
    assert "phone" in first_item
    assert "preferred_language" in first_item
    assert "message" in first_item
    assert len(first_item["message"]) > 10


def test_notify_503_by_default_unavailable(
    client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default honest failure: NOTIFICATION_PROVIDER='unavailable' returns HTTP 503."""
    monkeypatch.setattr(settings, "notification_provider", "unavailable")
    monkeypatch.setattr(settings, "explanation_provider", "simulated")

    response = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        json={"channel": "sms"},
    )
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower() or "not configured" in response.json()["detail"].lower()


def test_notify_console_provider_success(
    client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Console provider dispatches notifications and returns sent summary."""
    monkeypatch.setattr(settings, "notification_provider", "console")
    monkeypatch.setattr(settings, "explanation_provider", "simulated")

    console = get_notification_provider()
    assert isinstance(console, ConsoleNotificationProvider)
    initial_count = len(console.sent_messages)

    response = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        json={"channel": "sms"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["incident_id"] == DEMO_INCIDENT_ID
    assert data["provider"] == "console"
    assert data["channel"] == "sms"
    assert data["total_targeted"] > 0
    assert data["sent_count"] == data["total_targeted"]
    assert data["failed_count"] == 0
    assert len(data["deliveries"]) == data["sent_count"]
    assert len(console.sent_messages) == initial_count + data["sent_count"]


def test_notify_with_subscriber_filter(
    client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Targeting specific subscriber IDs filters delivery list."""
    monkeypatch.setattr(settings, "notification_provider", "console")
    monkeypatch.setattr(settings, "explanation_provider", "simulated")

    # First get previews to find an affected subscriber ID
    prev_resp = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notifications/preview")
    assert prev_resp.status_code == 200
    target_id = prev_resp.json()["previews"][0]["subscriber_id"]

    response = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        json={"channel": "whatsapp", "subscriber_ids": [target_id]},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["channel"] == "whatsapp"
    assert data["total_targeted"] == 1
    assert data["deliveries"][0]["subscriber_id"] == target_id
    assert data["deliveries"][0]["channel"] == "whatsapp"


def test_twilio_provider_unconfigured_raises_unavailable(
    client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Configuring twilio without TWILIO_* credentials raises 503 / unavailable error."""
    monkeypatch.setattr(settings, "notification_provider", "twilio")
    monkeypatch.setattr(settings, "twilio_account_sid", "")
    monkeypatch.setattr(settings, "twilio_auth_token", "")
    monkeypatch.setattr(settings, "twilio_from_number", "")
    monkeypatch.setattr(settings, "explanation_provider", "simulated")

    with pytest.raises(NotificationProviderUnavailableError):
        TwilioNotificationProvider(
            account_sid="", auth_token="", from_number="", whatsapp_from_number=None
        )

    response = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        json={"channel": "sms"},
    )
    assert response.status_code == 503


def test_auto_dispatch_during_lab_run_with_console_provider(
    client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When notification_provider='console', lab run opening an incident auto-dispatches alerts."""
    monkeypatch.setattr(settings, "notification_provider", "console")
    monkeypatch.setattr(settings, "explanation_provider", "simulated")

    console = get_notification_provider()
    assert isinstance(console, ConsoleNotificationProvider)
    start_count = len(console.sent_messages)

    run_payload = {
        "scenario": "degrade_link",
        "target_link_id": "L2",
        "severity": "high",
    }
    response = client.post("/api/v1/lab/run", json=run_payload)
    assert response.status_code == 200
    run_data = response.json()

    if run_data.get("incident") and run_data.get("affected_count", 0) > 0:
        assert len(console.sent_messages) > start_count
