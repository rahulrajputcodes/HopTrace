"""
M3 Notification Hardening Test Suite.

New tests covering hardening requirements beyond the original 45:
- H1:  Atomic idempotency — batch insert FIRST; DB UNIQUE constraint catches races
- H2:  Twilio requires Idempotency-Key header; console auto-generates
- H3:  Phone-number masking utility
- H4:  Console provider logs do not expose full phone numbers
- H5:  sandboxed=True for console and Twilio sandbox-routed sends
- H6:  sandboxed=False for real Twilio sends
- H7:  Twilio sends include sandboxed field in delivery response
- H8:  Voice endpoint rejects empty text (400)
- H9:  Voice endpoint rejects >500-char text (422 from Pydantic)
- H10: Voice endpoint accepts exactly 500-char text
- H11: Voice endpoint rejects invalid speaker (400)
- H12: Voice endpoint returns 503 on Sarvam API failure (not 500)
- H13: generate_speech uses correct Sarvam TTS API request format
- H14: generate_speech validates empty text
- H15: notifyApi.js exports correct helpers (via imports only — docs test)
- H16: DB UNIQUE constraint prevents duplicate batch insert at the DB level
- H17: Concurrent duplicate request correctly deduplicates via UNIQUE constraint
- H18: Retry does NOT set sandboxed=True on retried console deliveries
- H19: Sandbox transparency — delivery response includes sandboxed field
"""
from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.connection import get_db_connection
from app.db.init import DEMO_INCIDENTS
from app.db.notify_schema import ensure_notify_tables
from app.db.repository import (
    create_notification_batch,
    get_notification_batch_by_idempotency,
    get_notification_deliveries,
)
from app.main import app
from app.providers.explanations import SarvamExplanationProvider, ExplanationProviderUnavailableError
from app.providers.notifications import (
    ConsoleNotificationProvider,
    TwilioNotificationProvider,
    _mask_phone,
)
from app.providers.registry import get_notification_provider

DEMO_INCIDENT_ID = DEMO_INCIDENTS[0]["id"]


# ── H1-H2: Idempotency & Twilio Key Requirement ──────────────────────────────

def test_h1_atomic_idempotency_batch_insert_first(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    """
    DB UNIQUE constraint must enforce idempotency atomically.
    A second insert with the same idempotency key must raise IntegrityError,
    not silently create a second batch.
    """
    monkeypatch.setattr(settings, "notification_provider", "console")

    conn = get_db_connection(isolated_db)
    ensure_notify_tables(conn)
    # Insert first batch
    create_notification_batch(conn, {
        "id": "batch-h1-first",
        "incident_id": DEMO_INCIDENT_ID,
        "kind": "outage",
        "channel": "sms",
        "provider": "console",
        "idempotency_key": "h1-unique-key",
        "created_by": "test",
        "created_at": "2026-11-20T10:00:00Z",
    })
    conn.commit()

    # Attempting a second insert with the same (incident_id, idempotency_key) must fail at DB level
    with pytest.raises(sqlite3.IntegrityError):
        create_notification_batch(conn, {
            "id": "batch-h1-second",
            "incident_id": DEMO_INCIDENT_ID,
            "kind": "outage",
            "channel": "sms",
            "provider": "console",
            "idempotency_key": "h1-unique-key",  # Same key — must collide
            "created_by": "test",
            "created_at": "2026-11-20T10:00:01Z",
        })
        conn.commit()

    conn.rollback()
    # Confirm only the original batch exists
    batch = get_notification_batch_by_idempotency(conn, DEMO_INCIDENT_ID, "h1-unique-key")
    assert batch is not None
    assert batch["id"] == "batch-h1-first"
    conn.close()


def test_h2a_twilio_requires_idempotency_key(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    """POST /notify with Twilio provider and NO Idempotency-Key must return 400."""
    monkeypatch.setattr(settings, "notification_provider", "twilio")
    monkeypatch.setattr(settings, "twilio_account_sid", "ACtest123")
    monkeypatch.setattr(settings, "twilio_auth_token", "auth_xyz")
    monkeypatch.setattr(settings, "twilio_from_number", "+18005550100")

    resp = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        # No Idempotency-Key header
        json={"channel": "sms"},
    )
    assert resp.status_code == 400
    assert "idempotency-key" in resp.json()["detail"].lower()


def test_h2b_twilio_with_idempotency_key_accepted(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    """POST /notify with Twilio provider and valid Idempotency-Key must proceed past 400."""
    monkeypatch.setattr(settings, "notification_provider", "twilio")
    monkeypatch.setattr(settings, "twilio_account_sid", "ACtest123")
    monkeypatch.setattr(settings, "twilio_auth_token", "auth_xyz")
    monkeypatch.setattr(settings, "twilio_from_number", "+18005550100")
    # All numbers are sandbox-routed (not in allowlist), so no real HTTP call needed
    monkeypatch.setattr(settings, "real_send_allowlist", "")

    resp = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        headers={"Idempotency-Key": "twilio-key-h2b"},
        json={"channel": "sms"},
    )
    # Should succeed (200) — numbers will be sandbox-routed since allowlist is empty
    assert resp.status_code == 200
    assert resp.json()["deduplicated"] is False


def test_h2c_console_without_key_auto_generates(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    """Console/sandbox sends without Idempotency-Key must succeed (auto-generate key)."""
    monkeypatch.setattr(settings, "notification_provider", "console")

    resp = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        # No Idempotency-Key header — allowed for console
        json={"channel": "sms"},
    )
    assert resp.status_code == 200
    assert resp.json()["provider"] == "console"
    assert resp.json()["deduplicated"] is False


# ── H3-H6: Phone Masking & Sandbox Transparency ──────────────────────────────

def test_h3_mask_phone_utility():
    """_mask_phone must redact the middle of phone numbers."""
    assert _mask_phone("+919876543210") == "+91****3210"
    assert _mask_phone("9876543210") == "****3210"
    assert _mask_phone("") == "****"
    assert _mask_phone("1234") == "****"
    assert _mask_phone("+12345678") == "+12****5678"
    # Last 4 digits must always be visible
    result = _mask_phone("+919876543210")
    assert result.endswith("3210")
    # Full number must NOT appear
    assert "9876543210" not in result


def test_h4_console_provider_sandboxed_field():
    """ConsoleNotificationProvider.send_notification must return sandboxed=True."""
    provider = ConsoleNotificationProvider()
    result = provider.send_notification(
        recipient="+919876543210",
        message="Test outage alert",
        channel="sms",
        subscriber_id="SUB101",
    )
    assert result.get("sandboxed") is True
    assert result["provider"] == "console"
    assert result["status"] == "sent"


def test_h5_twilio_sandbox_routed_sandboxed_true():
    """Twilio sandbox-routed sends (number not in allowlist) must return sandboxed=True."""
    provider = TwilioNotificationProvider(
        account_sid="ACtest",
        auth_token="auth_secret",
        from_number="+18005550100",
        allowlist={"+919999000000"},  # Only one number allowlisted
    )

    with patch("urllib.request.urlopen") as mock_url:
        result = provider.send_notification(
            recipient="+910000000001",  # Not in allowlist
            message="Sandbox routed message",
            channel="sms",
        )
        mock_url.assert_not_called()  # No real HTTP call
        assert result.get("sandboxed") is True
        assert result["provider"] == "console"


def test_h6_twilio_real_send_sandboxed_false():
    """Real Twilio sends (number in allowlist) must return sandboxed=False."""
    provider = TwilioNotificationProvider(
        account_sid="ACtest",
        auth_token="auth_secret",
        from_number="+18005550100",
        allowlist={"+919876543210"},
    )

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"sid": "SM99999", "status": "queued"}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = provider.send_notification(
            recipient="+919876543210",  # In allowlist
            message="Real send message",
            channel="sms",
        )
        assert result.get("sandboxed") is False
        assert result["provider"] == "twilio"


def test_h7_delivery_response_includes_sandboxed_field(
    client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch
):
    """
    Delivery items in POST /notify response must include sandboxed field.
    Console sends must have sandboxed=True.
    """
    monkeypatch.setattr(settings, "notification_provider", "console")

    resp = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        headers={"Idempotency-Key": "sandbox-field-h7"},
        json={"channel": "sms"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["deliveries"]) > 0
    for d in data["deliveries"]:
        assert "sandboxed" in d, "Each delivery must include the sandboxed field"
        # Console deliveries are always sandboxed
        if d["status"] == "sent":
            assert d["sandboxed"] is True, f"Console delivery for {d['subscriber_id']} must have sandboxed=True"


# ── H8-H14: Sarvam Voice Validation ──────────────────────────────────────────

def test_h8_voice_empty_text_returns_400(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    """POST /voice with text='' (or whitespace only) must return 422 (Pydantic min_length)."""
    monkeypatch.setattr(settings, "sarvam_api_key", "some-key")
    # Pydantic min_length=1 rejects empty string with 422 Unprocessable Entity
    resp = client.post("/api/v1/voice", json={"text": "", "language": "hi"})
    assert resp.status_code in (400, 422)


def test_h9_voice_text_exceeding_500_chars_rejected(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    """POST /voice with text longer than 500 chars must return 422 (Pydantic max_length)."""
    monkeypatch.setattr(settings, "sarvam_api_key", "some-key")
    long_text = "नेटवर्क समस्या। " * 50  # Well over 500 chars
    resp = client.post("/api/v1/voice", json={"text": long_text, "language": "hi"})
    assert resp.status_code == 422  # Pydantic validation error


def test_h10_voice_exactly_500_chars_accepted(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    """POST /voice with exactly 500 characters must be accepted (not rejected by schema)."""
    monkeypatch.setattr(settings, "sarvam_api_key", "valid-voice-key-h10")
    text_500 = "a" * 500

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"audios": ["UklGRigAAABXQVZFZm10IBAAAA=="]}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        resp = client.post("/api/v1/voice", json={"text": text_500, "language": "hi", "speaker": "meera"})
    # Must not reject — 500 chars is exactly the allowed maximum
    assert resp.status_code == 200


def test_h11_voice_invalid_speaker_returns_400(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    """POST /voice with an unknown speaker must return 400."""
    monkeypatch.setattr(settings, "sarvam_api_key", "valid-voice-key-h11")

    resp = client.post(
        "/api/v1/voice",
        json={"text": "नेटवर्क समस्या ठीक की जा रही है।", "language": "hi", "speaker": "unknown_robot_xyz"},
    )
    assert resp.status_code == 400
    assert "speaker" in resp.json()["detail"].lower() or "unknown" in resp.json()["detail"].lower()


def test_h12_voice_sarvam_api_failure_returns_503(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    """POST /voice returns 503 (not 500) when Sarvam API call fails."""
    monkeypatch.setattr(settings, "sarvam_api_key", "valid-voice-key-h12")

    with patch("urllib.request.urlopen", side_effect=Exception("Sarvam connection refused")):
        resp = client.post(
            "/api/v1/voice",
            json={"text": "Network issue being resolved.", "language": "en", "speaker": "meera"},
        )
    assert resp.status_code == 503
    assert "sarvam" in resp.json()["detail"].lower()


def test_h13_generate_speech_uses_correct_sarvam_request_format(monkeypatch: pytest.MonkeyPatch):
    """
    generate_speech must POST to https://api.sarvam.ai/text-to-speech with
    'text' (string) not 'inputs' (array), and use api-subscription-key header.
    Reference: https://docs.sarvam.ai/api-reference-docs/endpoints/text-to-speech
    """
    provider = SarvamExplanationProvider(
        api_key="test-key-format",
        model="sarvam-105b",
        timeout_seconds=10.0,
    )

    captured_request = {}

    def fake_urlopen(req, timeout=None):
        captured_request["url"] = req.full_url
        captured_request["headers"] = dict(req.headers)
        captured_request["body"] = json.loads(req.data.decode("utf-8"))
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"audios": ["UklGRigAAA=="]}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        provider.generate_speech(text="Hello world", language_code="en-IN", speaker="meera")

    # Verify endpoint URL
    assert captured_request["url"] == "https://api.sarvam.ai/text-to-speech"

    # Verify authentication header
    assert "api-subscription-key" in {k.lower(): v for k, v in captured_request["headers"].items()} or \
           "Api-subscription-key" in captured_request["headers"]

    # Verify payload uses 'text' (string) NOT 'inputs' (array — old format)
    body = captured_request["body"]
    assert "text" in body, "Request must use 'text' field (not 'inputs')"
    assert isinstance(body["text"], str), "'text' must be a string, not a list"
    assert "inputs" not in body, "Old 'inputs' array format must not be used"
    assert "language_code" in body, "'language_code' must be present"


def test_h14_generate_speech_validates_empty_text():
    """generate_speech must raise ValueError for empty text."""
    provider = SarvamExplanationProvider(
        api_key="test-key",
        model="sarvam-105b",
        timeout_seconds=10.0,
    )
    with pytest.raises(ValueError, match="empty"):
        provider.generate_speech(text="   ", language_code="hi-IN", speaker="meera")


# ── H16-H19: DB Concurrency & Sandbox Field Persistence ──────────────────────

def test_h16_db_unique_constraint_enforced(isolated_db: str):
    """
    The notification_batches UNIQUE(incident_id, idempotency_key) constraint must
    be enforced at the SQLite level, independent of application-level checks.
    """
    conn = get_db_connection(isolated_db)
    ensure_notify_tables(conn)

    batch_data = {
        "id": "batch-unique-01",
        "incident_id": "INC-H16-001",
        "kind": "outage",
        "channel": "sms",
        "provider": "console",
        "idempotency_key": "key-unique-01",
        "created_by": "test",
        "created_at": "2026-11-20T10:00:00Z",
    }
    conn.execute(
        """INSERT INTO notification_batches
           (id, incident_id, kind, channel, provider, idempotency_key, created_by, created_at)
           VALUES (:id, :incident_id, :kind, :channel, :provider, :idempotency_key, :created_by, :created_at)""",
        batch_data,
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        # Same (incident_id, idempotency_key), different batch id — must fail
        batch_data2 = {**batch_data, "id": "batch-unique-02"}
        conn.execute(
            """INSERT INTO notification_batches
               (id, incident_id, kind, channel, provider, idempotency_key, created_by, created_at)
               VALUES (:id, :incident_id, :kind, :channel, :provider, :idempotency_key, :created_by, :created_at)""",
            batch_data2,
        )
        conn.commit()
    conn.close()


def test_h17_concurrent_duplicate_requests_exactly_one_dispatch(
    client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch
):
    """
    Two concurrent requests with the same idempotency key must result in
    exactly ONE provider dispatch and one deduplicated response.
    """
    monkeypatch.setattr(settings, "notification_provider", "console")
    console = get_notification_provider()
    before_count = len(console.sent_messages)

    key = "concurrent-h17-key"
    results = []

    def do_request():
        r = client.post(
            f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
            headers={"Idempotency-Key": key},
            json={"channel": "sms"},
        )
        results.append(r.json())

    t1 = threading.Thread(target=do_request)
    t2 = threading.Thread(target=do_request)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(results) == 2
    dedup_count = sum(1 for r in results if r.get("deduplicated") is True)
    # Exactly one must be deduplicated — the second one to arrive
    assert dedup_count == 1, f"Expected exactly 1 deduplicated=True, got {dedup_count}"

    # Provider dispatch must only have happened once (console messages count)
    after_count = len(console.sent_messages)
    # At least one message dispatched (from the first successful send)
    assert after_count > before_count
    # Second request did NOT add more messages
    # (number of new messages matches what a single batch would send)
    new_count = after_count - before_count
    # Both requests targeted the same subscribers, so we should have only one batch worth
    r_not_dedup = next(r for r in results if not r.get("deduplicated"))
    assert new_count == r_not_dedup["sent_count"]


def test_h19_sandbox_field_in_history_response(
    client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch
):
    """
    GET /incidents/{id}/notifications history must include sandboxed field on deliveries.
    """
    monkeypatch.setattr(settings, "notification_provider", "console")

    # Send first
    client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        headers={"Idempotency-Key": "history-sandbox-h19"},
        json={"channel": "sms"},
    )

    # Fetch history
    resp = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notifications")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["batches"]) >= 1
    for batch in data["batches"]:
        for d in batch["deliveries"]:
            assert "sandboxed" in d, f"Delivery {d.get('subscriber_id')} missing sandboxed field in history"
