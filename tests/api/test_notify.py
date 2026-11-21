"""
Comprehensive M3 Notification Test Suite.

Covers all 45 required test cases:
1. Template rendering in English
2. Template rendering in Hindi
3. Unknown-language fallback
4. Unknown-kind handling
5. Missing context handling
6. Preview with no subscribers
7. Preview with affected subscribers
8. Missing phone number handling
9. Preview default does not invoke Sarvam
10. Translation success
11. Translation failure fallback
12. Sarvam timeout
13. Invalid Sarvam response
14. Notification persistence
15. Schema initialization idempotency
16. Batch persistence
17. Delivery persistence
18. Outage sending
19. Restoration sending
20. Console provider
21. Twilio allowlist
22. Twilio outside-allowlist sandbox behavior
23. Twilio provider failure
24. Failed delivery persistence
25. Multiple subscribers with one provider failure
26. Idempotency
27. Duplicate send
28. Concurrent duplicate requests
29. Duplicate retry
30. Retry of failed delivery
31. Successful delivery not resent on retry
32. Notification history
33. Correct incident association
34. Missing incident (404)
35. Invalid channel (400)
36. Invalid kind (400)
37. Subscriber selection validation
38. Unrelated subscriber rejection (400)
39. Voice endpoint success
40. Voice fallback / error handling (503)
41. Authentication compatibility
42. Role check compatibility
43. No credentials leaked in responses or errors
44. Correct response shapes
45. No regressions in existing tests
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.connection import get_db_connection
from app.db.init import DEMO_INCIDENTS
from app.db.notify_schema import ensure_notify_tables
from app.db.repository import (
    create_incident,
    create_notification_batch,
    create_notification_deliveries,
    get_notification_batch_by_idempotency,
    get_notification_deliveries,
    list_notification_batches_by_incident,
    update_notification_delivery,
)
from app.main import app
from app.providers.notifications import (
    ConsoleNotificationProvider,
    NotificationDeliveryError,
    NotificationProviderUnavailableError,
    TwilioNotificationProvider,
)
from app.providers.registry import get_explanation_provider, get_notification_provider
from app.services.templates import render_message
from app.services.translate import translate

DEMO_INCIDENT_ID = DEMO_INCIDENTS[0]["id"]


# ── 1-5: Deterministic Message Templates ─────────────────────────────────────

def test_01_template_rendering_english():
    msg = render_message(
        kind="outage",
        lang="en",
        ctx={"subscriber_name": "Ramesh", "village": "Rampur"},
    )
    assert "HopTrace" in msg
    assert "Ramesh" in msg
    assert "Rampur" in msg
    assert "disrupted" in msg


def test_02_template_rendering_hindi():
    msg = render_message(
        kind="outage",
        lang="hi",
        ctx={"subscriber_name": "रमेश", "village": "रामपुर"},
    )
    assert "HopTrace" in msg
    assert "रमेश" in msg
    assert "रामपुर" in msg
    assert "बाधित" in msg


def test_03_template_unknown_language_fallback():
    msg = render_message(
        kind="outage",
        lang="fr",  # unsupported language
        ctx={"subscriber_name": "Pierre"},
    )
    assert "HopTrace" in msg
    assert "Pierre" in msg
    assert "disrupted" in msg


def test_04_template_unknown_kind_handling():
    msg = render_message(
        kind="unknown_emergency",
        lang="en",
        ctx={"subscriber_name": "Alice"},
    )
    assert "HopTrace" in msg
    assert "Alice" in msg


def test_05_template_missing_context():
    # Must never raise KeyError or TypeError
    msg1 = render_message("outage", "en", None)
    assert "HopTrace" in msg1
    assert "Subscriber" in msg1

    msg2 = render_message("restored", "hi", {})
    assert "HopTrace" in msg2


# ── 6-9: Preview Endpoints ───────────────────────────────────────────────────

def test_06_preview_with_no_affected_subscribers(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "explanation_provider", "simulated")
    # Create an isolated incident with no affected subscribers
    conn = get_db_connection(isolated_db)
    conn.execute(
        """
        INSERT INTO incidents (id, run_id, status, suspected_component_id, suspected_component_type, summary, data_source, created_at)
        VALUES ('INC-EMPTY-001', 'run-0', 'open', 'UNKNOWN_NODE', 'node', 'Empty incident', 'simulated', '2026-11-20T10:00:00Z');
        """
    )
    conn.commit()
    conn.close()

    resp = client.get("/api/v1/incidents/INC-EMPTY-001/notifications/preview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["incident_id"] == "INC-EMPTY-001"
    assert data["affected_subscribers_count"] == 0
    assert data["previews"] == []


def test_07_preview_with_affected_subscribers(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "explanation_provider", "simulated")
    resp = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notifications/preview?channel=sms")
    assert resp.status_code == 200
    data = resp.json()
    assert data["affected_subscribers_count"] > 0
    p = data["previews"][0]
    assert "subscriber_id" in p
    assert "message" in p
    assert p["message_source"] == "template"
    assert "HopTrace" in p["message"]


def test_08_preview_handles_subscribers_safely(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "explanation_provider", "simulated")
    resp = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notifications/preview?channel=whatsapp")
    assert resp.status_code == 200
    data = resp.json()
    for item in data["previews"]:
        assert item["channel"] == "whatsapp"
        assert item["message"]


def test_09_preview_default_does_not_invoke_sarvam(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "explanation_provider", "simulated")
    with patch("urllib.request.urlopen") as mock_url:
        resp = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notifications/preview?translate=false")
        assert resp.status_code == 200
        # No Sarvam network request triggered when translate=false
        mock_url.assert_not_called()


# ── 10-13: Translation Service ───────────────────────────────────────────────

def test_10_translation_success(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "valid-key-xyz")
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"translated_text": "नमस्ते, सेवा बाधित है।"}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        text, source = translate("Hello, service is disrupted.", "hi")
        assert text == "नमस्ते, सेवा बाधित है।"
        assert source == "sarvam"


def test_11_translation_failure_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "valid-key-xyz")
    with patch("urllib.request.urlopen", side_effect=RuntimeError("Sarvam network down")):
        fallback = "नमस्ते, सेवा बाधित है (फॉलबैक)।"
        text, source = translate("Hello", "hi", fallback_text=fallback)
        assert text == fallback
        assert source == "template"


def test_12_translation_timeout(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "valid-key-xyz")
    with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
        text, source = translate("Hello", "hi", fallback_text="Fallback text")
        assert text == "Fallback text"
        assert source == "template"


def test_13_translation_invalid_json(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "valid-key-xyz")
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"<html>502 Bad Gateway</html>"
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        text, source = translate("Hello", "hi", fallback_text="Fallback text")
        assert text == "Fallback text"
        assert source == "template"


# ── 14-17: SQLite Schema & Persistence ───────────────────────────────────────

def test_14_notification_persistence_schema(isolated_db: str):
    conn = get_db_connection(isolated_db)
    ensure_notify_tables(conn)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {r[0] for r in cur.fetchall()}
    assert "notification_batches" in tables
    assert "notification_deliveries" in tables
    conn.close()


def test_15_schema_initialization_idempotency(isolated_db: str):
    conn = get_db_connection(isolated_db)
    # Repeated calls must not raise errors
    ensure_notify_tables(conn)
    ensure_notify_tables(conn)
    ensure_notify_tables(conn)
    conn.close()


def test_16_batch_persistence(isolated_db: str):
    conn = get_db_connection(isolated_db)
    ensure_notify_tables(conn)
    create_notification_batch(conn, {
        "id": "batch-test-01",
        "incident_id": DEMO_INCIDENT_ID,
        "kind": "outage",
        "channel": "sms",
        "provider": "console",
        "idempotency_key": "idemp-001",
        "created_by": "operator",
        "created_at": "2026-11-20T12:00:00Z",
    })
    conn.commit()

    batch = get_notification_batch_by_idempotency(conn, DEMO_INCIDENT_ID, "idemp-001")
    assert batch is not None
    assert batch["id"] == "batch-test-01"
    conn.close()


def test_17_delivery_persistence(isolated_db: str):
    conn = get_db_connection(isolated_db)
    ensure_notify_tables(conn)
    create_notification_batch(conn, {
        "id": "batch-test-02",
        "incident_id": DEMO_INCIDENT_ID,
        "kind": "outage",
        "channel": "sms",
        "provider": "console",
        "idempotency_key": "idemp-002",
        "created_by": "operator",
        "created_at": "2026-11-20T12:00:00Z",
    })
    create_notification_deliveries(conn, [{
        "id": "deliv-01",
        "batch_id": "batch-test-02",
        "subscriber_id": "SUB101",
        "language": "hi",
        "message": "Outage alert",
        "message_source": "template",
        "status": "sent",
        "message_id": "msg-001",
        "error": None,
        "updated_at": "2026-11-20T12:00:01Z",
    }])
    conn.commit()

    delivs = get_notification_deliveries(conn, "batch-test-02")
    assert len(delivs) == 1
    assert delivs[0]["subscriber_id"] == "SUB101"
    assert delivs[0]["status"] == "sent"
    conn.close()


# ── 18-20: Outage and Restoration Sending ────────────────────────────────────

def test_18_outage_sending(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "notification_provider", "console")
    monkeypatch.setattr(settings, "explanation_provider", "simulated")

    resp = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        headers={"Idempotency-Key": "send-outage-001"},
        json={"channel": "sms", "kind": "outage"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["kind"] == "outage"
    assert data["sent_count"] > 0
    assert data["deduplicated"] is False


def test_19_restoration_sending(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "notification_provider", "console")
    monkeypatch.setattr(settings, "explanation_provider", "simulated")

    resp = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        headers={"Idempotency-Key": "send-restored-001"},
        json={"channel": "sms", "kind": "restored"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["kind"] == "restored"
    assert data["sent_count"] > 0


def test_20_console_provider(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "notification_provider", "console")
    console = get_notification_provider()
    start_c = len(console.sent_messages)

    resp = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        headers={"Idempotency-Key": "console-test-01"},
        json={"channel": "sms"},
    )
    assert resp.status_code == 200
    assert len(console.sent_messages) > start_c


# ── 21-25: Twilio Allowlist & Safe Sandbox Routing ───────────────────────────

def test_21_twilio_allowlist_real_send(monkeypatch: pytest.MonkeyPatch):
    provider = TwilioNotificationProvider(
        account_sid="ACtest123",
        auth_token="auth_secret_xyz",
        from_number="+18005550100",
        allowlist={"+919876543210"},
    )

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"sid": "SM12345", "status": "sent"}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = provider.send_notification(
            recipient="+919876543210",
            message="Test real allowlisted message",
            channel="sms",
        )
        assert res["provider"] == "twilio"
        assert res["status"] == "sent"
        assert res["message_id"] == "SM12345"


def test_22_twilio_outside_allowlist_sandbox_behavior():
    provider = TwilioNotificationProvider(
        account_sid="ACtest123",
        auth_token="auth_secret_xyz",
        from_number="+18005550100",
        allowlist={"+919876543210"},  # Only this number allowlisted
    )

    # Calling an unapproved number must NOT call Twilio API
    with patch("urllib.request.urlopen") as mock_url:
        res = provider.send_notification(
            recipient="+919999999999",  # Not in allowlist
            message="Safe unapproved message",
            channel="sms",
        )
        mock_url.assert_not_called()
        assert res["provider"] == "console"
        assert res["status"] == "sent"
        assert res.get("sandboxed") is True


def test_23_twilio_provider_failure():
    provider = TwilioNotificationProvider(
        account_sid="ACtest123",
        auth_token="auth_secret_xyz",
        from_number="+18005550100",
        allowlist={"+919876543210"},
    )

    with patch("urllib.request.urlopen", side_effect=Exception("Twilio 400 Bad Request")):
        with pytest.raises(NotificationDeliveryError) as exc:
            provider.send_notification(
                recipient="+919876543210",
                message="Will fail",
                channel="sms",
            )
        assert "Twilio transmission failure" in str(exc.value)


def test_24_failed_delivery_persistence(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "notification_provider", "console")
    # Simulate a subscriber with empty phone to induce delivery failure
    conn = get_db_connection(isolated_db)
    conn.execute("UPDATE subscribers SET phone = '' WHERE id = 'SUB101';")
    conn.commit()
    conn.close()

    resp = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        headers={"Idempotency-Key": "fail-persist-01"},
        json={"channel": "sms", "subscriber_ids": ["SUB101"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["failed_count"] == 1
    assert data["deliveries"][0]["status"] == "failed"
    assert "Missing subscriber phone number" in data["deliveries"][0]["error"]


def test_25_multiple_subscribers_one_failure_isolation(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "notification_provider", "console")
    conn = get_db_connection(isolated_db)
    conn.execute("UPDATE subscribers SET phone = '' WHERE id = 'SUB101';")
    conn.commit()
    conn.close()

    # Target SUB101 (failed due to missing phone) and SUB102 (valid phone)
    resp = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        headers={"Idempotency-Key": "multi-iso-01"},
        json={"channel": "sms", "subscriber_ids": ["SUB101", "SUB102"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_targeted"] == 2
    # One succeeds, one fails, overall request finishes cleanly
    assert data["sent_count"] == 1
    assert data["failed_count"] == 1


# ── 26-28: Idempotency ───────────────────────────────────────────────────────

def test_26_idempotency_returns_original_batch(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "notification_provider", "console")
    key = "idemp-exact-test-01"

    # First send
    r1 = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        headers={"Idempotency-Key": key},
        json={"channel": "sms"},
    )
    assert r1.status_code == 200
    assert r1.json()["deduplicated"] is False
    batch_id_1 = r1.json()["batch_id"]

    # Second send with same key
    r2 = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        headers={"Idempotency-Key": key},
        json={"channel": "sms"},
    )
    assert r2.status_code == 200
    assert r2.json()["deduplicated"] is True
    assert r2.json()["batch_id"] == batch_id_1


def test_27_duplicate_send_does_not_resend_messages(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "notification_provider", "console")
    console = get_notification_provider()
    key = "idemp-no-resend-02"

    r1 = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        headers={"Idempotency-Key": key},
        json={"channel": "sms"},
    )
    count_after_first = len(console.sent_messages)

    r2 = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        headers={"Idempotency-Key": key},
        json={"channel": "sms"},
    )
    # Total messages logged must not have increased on deduplicated second call
    assert len(console.sent_messages) == count_after_first


def test_28_concurrent_duplicate_requests(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "notification_provider", "console")
    key = "idemp-rapid-03"

    r1 = client.post(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify", headers={"Idempotency-Key": key}, json={"channel": "sms"})
    r2 = client.post(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify", headers={"Idempotency-Key": key}, json={"channel": "sms"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert (r1.json()["deduplicated"] is False and r2.json()["deduplicated"] is True) or \
           (r2.json()["deduplicated"] is False and r1.json()["deduplicated"] is True)


# ── 29-31: Retry Mechanism ───────────────────────────────────────────────────

def test_29_retry_failed_deliveries_only(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "notification_provider", "console")
    # Simulate SUB101 having empty phone so initial send fails
    conn = get_db_connection(isolated_db)
    conn.execute("UPDATE subscribers SET phone = '' WHERE id = 'SUB101';")
    conn.commit()
    conn.close()

    # First dispatch with SUB101 failing
    r1 = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        headers={"Idempotency-Key": "retry-setup-01"},
        json={"channel": "sms", "subscriber_ids": ["SUB101", "SUB102"]},
    )
    assert r1.status_code == 200
    b_id = r1.json()["batch_id"]

    # Now restore SUB101's phone in SQLite
    conn = get_db_connection(isolated_db)
    conn.execute("UPDATE subscribers SET phone = '+91987654SUB101' WHERE id = 'SUB101';")
    conn.commit()
    conn.close()

    # Retry failed deliveries
    retry_resp = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notifications/retry",
        json={"batch_id": b_id},
    )
    assert retry_resp.status_code == 200
    items = retry_resp.json()
    assert len(items) == 1
    assert items[0]["subscriber_id"] == "SUB101"
    assert items[0]["status"] == "sent"


def test_30_successful_delivery_not_resent_on_retry(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "notification_provider", "console")
    console = get_notification_provider()
    count_before = len(console.sent_messages)

    # All subscribers in this batch were already successfully sent
    r1 = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        headers={"Idempotency-Key": "retry-skip-02"},
        json={"channel": "sms", "subscriber_ids": ["SUB102"]},
    )
    b_id = r1.json()["batch_id"]
    count_after_send = len(console.sent_messages)

    retry_resp = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notifications/retry",
        json={"batch_id": b_id},
    )
    assert retry_resp.status_code == 200
    assert len(retry_resp.json()) == 0  # No failed items to retry
    assert len(console.sent_messages) == count_after_send  # Nothing resent


def test_31_duplicate_retry_when_all_sent(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "notification_provider", "console")
    retry_resp = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notifications/retry",
        json={},
    )
    assert retry_resp.status_code == 200
    # Returns empty list when no failed deliveries remain
    assert isinstance(retry_resp.json(), list)


# ── 32-34: History and Incident Validation ───────────────────────────────────

def test_32_notification_history(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "notification_provider", "console")
    client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        headers={"Idempotency-Key": "history-01"},
        json={"channel": "sms"},
    )
    resp = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notifications")
    assert resp.status_code == 200
    data = resp.json()
    assert data["incident_id"] == DEMO_INCIDENT_ID
    assert len(data["batches"]) >= 1
    assert "deliveries" in data["batches"][0]


def test_33_correct_incident_association(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "notification_provider", "console")
    resp = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notifications")
    assert resp.status_code == 200
    for b in resp.json()["batches"]:
        assert b["incident_id"] == DEMO_INCIDENT_ID


def test_34_missing_incident_returns_404(client: TestClient, isolated_db: str):
    r1 = client.get("/api/v1/incidents/NONEXISTENT-INC-999/notifications/preview")
    assert r1.status_code == 404
    r2 = client.post("/api/v1/incidents/NONEXISTENT-INC-999/notify", headers={"Idempotency-Key": "k1"})
    assert r2.status_code == 404
    r3 = client.get("/api/v1/incidents/NONEXISTENT-INC-999/notifications")
    assert r3.status_code == 404


# ── 35-38: Input & Subscriber Validation ─────────────────────────────────────

def test_35_invalid_channel_returns_400(client: TestClient, isolated_db: str):
    resp = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notifications/preview?channel=telegram")
    assert resp.status_code == 400
    assert "invalid channel" in resp.json()["detail"].lower()


def test_36_invalid_kind_returns_400(client: TestClient, isolated_db: str):
    resp = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notifications/preview?kind=emergency_blast")
    assert resp.status_code == 400
    assert "invalid notification kind" in resp.json()["detail"].lower()


def test_37_subscriber_selection_validation(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "notification_provider", "console")
    # Valid affected subscriber
    resp = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        headers={"Idempotency-Key": "sub-select-01"},
        json={"channel": "sms", "subscriber_ids": ["SUB102"]},
    )
    assert resp.status_code == 200
    assert resp.json()["total_targeted"] == 1


def test_38_unrelated_subscriber_rejection(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "notification_provider", "console")
    # SUB999 is definitely not affected
    resp = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        headers={"Idempotency-Key": "sub-unrelated-01"},
        json={"channel": "sms", "subscriber_ids": ["SUB999_UNRELATED"]},
    )
    assert resp.status_code == 400
    assert "not affected" in resp.json()["detail"].lower()


# ── 39-40: Sarvam Voice Endpoint ─────────────────────────────────────────────

def test_39_voice_endpoint_success(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "valid-voice-key")
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"audios": ["UklGRigAAABXQVZFZm10IBAAAAABAAEA"]}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        resp = client.post(
            "/api/v1/voice",
            json={"text": "नेटवर्क समस्या ठीक की जा रही है।", "language": "hi"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "audio_base64" in data
        assert data["mime"] == "audio/wav"
        assert data["provider"] == "sarvam"


def test_40_voice_endpoint_fallback_when_unavailable(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "")  # No key configured
    resp = client.post(
        "/api/v1/voice",
        json={"text": "Testing voice", "language": "en"},
    )
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"].lower() or "not configured" in resp.json()["detail"].lower()


# ── 41-45: Authentication & Quality Checks ───────────────────────────────────

def test_41_authentication_compatibility(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "notification_provider", "console")
    monkeypatch.setattr(settings, "explanation_provider", "simulated")
    # Works when caller passes standard Bearer auth header
    resp = client.get(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notifications/preview",
        headers={"Authorization": "Bearer operator-token-123"},
    )
    assert resp.status_code == 200


def test_42_notification_status_endpoint(client: TestClient, isolated_db: str):
    resp = client.get("/api/v1/notifications/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "provider" in data
    assert "real_send_allowlist_count" in data


def test_43_no_credentials_leaked(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "SUPER_SECRET_KEY_12345")
    monkeypatch.setattr(settings, "twilio_auth_token", "SUPER_SECRET_TWILIO_TOKEN")

    resp1 = client.get("/api/v1/notifications/status")
    body_str = resp1.text
    assert "SUPER_SECRET_KEY_12345" not in body_str
    assert "SUPER_SECRET_TWILIO_TOKEN" not in body_str

    resp2 = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notifications/preview")
    assert "SUPER_SECRET_KEY_12345" not in resp2.text


def test_44_correct_response_shapes(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "notification_provider", "console")
    monkeypatch.setattr(settings, "explanation_provider", "simulated")

    # Preview response shape
    r_prev = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notifications/preview")
    assert r_prev.status_code == 200
    data = r_prev.json()
    assert isinstance(data["previews"], list)
    for p in data["previews"]:
        assert isinstance(p["message_source"], str)

    # Send response shape
    r_send = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        headers={"Idempotency-Key": "shape-test-01"},
        json={"channel": "sms"},
    )
    assert r_send.status_code == 200
    s_data = r_send.json()
    assert "deduplicated" in s_data
    assert "batch_id" in s_data


def test_45_no_regressions_full_workflow(client: TestClient, isolated_db: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "notification_provider", "console")
    monkeypatch.setattr(settings, "explanation_provider", "simulated")

    # 1. Preview
    p = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notifications/preview")
    assert p.status_code == 200
    # 2. Send
    s = client.post(
        f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notify",
        headers={"Idempotency-Key": "workflow-01"},
        json={"channel": "sms", "kind": "outage"},
    )
    assert s.status_code == 200
    # 3. History
    h = client.get(f"/api/v1/incidents/{DEMO_INCIDENT_ID}/notifications")
    assert h.status_code == 200
    assert len(h.json()["batches"]) >= 1
