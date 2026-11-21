"""
Tests for backend authentication, token lifecycle, and RBAC enforcement (M2 Lane).
"""
from __future__ import annotations

import time
import pytest
from fastapi.testclient import TestClient

from app.auth.security import (
    create_access_token,
    decode_access_token,
    dummy_verify,
    hash_password,
    verify_password,
)
from app.config import settings
from app.db.init import init_db
from app.main import app, lifespan

TEST_AUTH_SECRET = "test-secret-key-32-bytes-minimum-length-for-hmac-sha256"


# ── 1. Unit Tests for Security Primitives ────────────────────────────────────

def test_scrypt_password_hashing_and_verification() -> None:
    """Scrypt password hashing produces formatted string and verifies in constant time."""
    password = "SuperSecretOperatorPassword123!"
    hashed = hash_password(password)

    assert hashed.startswith("scrypt$16384$8$1$")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False
    assert verify_password(password, "invalid-hash-string") is False


def test_dummy_verify_timing_mitigation() -> None:
    """Dummy verification runs calculation and returns False."""
    assert dummy_verify("any-password") is False


def test_token_creation_and_decoding() -> None:
    """Tokens are created with HS256, expiration, and decoded accurately."""
    token, expires_at = create_access_token(
        username="test_operator",
        role="operator",
        secret=TEST_AUTH_SECRET,
        expires_in_minutes=60,
    )
    assert token.count(".") == 2
    assert "T" in expires_at

    payload = decode_access_token(token, TEST_AUTH_SECRET)
    assert payload is not None
    assert payload["sub"] == "test_operator"
    assert payload["role"] == "operator"
    assert payload["exp"] > time.time()


def test_tampered_token_rejected() -> None:
    """Tampering with token payload or signature returns None."""
    token, _ = create_access_token(
        username="test_operator",
        role="operator",
        secret=TEST_AUTH_SECRET,
        expires_in_minutes=60,
    )
    parts = token.split(".")
    tampered = f"{parts[0]}.{parts[1]}.tampered_signature"
    assert decode_access_token(tampered, TEST_AUTH_SECRET) is None


def test_expired_token_rejected() -> None:
    """Expired token returns None."""
    token, _ = create_access_token(
        username="test_operator",
        role="operator",
        secret=TEST_AUTH_SECRET,
        expires_in_minutes=-5,  # 5 minutes in the past
    )
    assert decode_access_token(token, TEST_AUTH_SECRET) is None


# ── 2. Startup Validation Test ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_startup_fails_if_auth_enabled_and_secret_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """FastAPI lifespan startup raises RuntimeError if auth is enabled but secret is empty."""
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "auth_secret", "")

    with pytest.raises(RuntimeError, match="AUTH_SECRET is not configured"):
        async with lifespan(app):
            pass


# ── 3. API Login & Identity Tests ─────────────────────────────────────────────

def test_login_flow_operator_and_viewer(isolated_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Seeded operator and viewer accounts can log in and receive valid tokens."""
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "auth_secret", TEST_AUTH_SECRET)
    monkeypatch.setattr(settings, "operator_password", "OpPass123!")
    monkeypatch.setattr(settings, "viewer_password", "ViewPass123!")

    # Re-init db with passwords configured
    init_db(isolated_db, seed_demo=True)

    client = TestClient(app)

    # 1. Login operator
    res_op = client.post("/api/v1/auth/login", json={"username": "operator", "password": "OpPass123!"})
    assert res_op.status_code == 200
    data_op = res_op.json()
    assert data_op["username"] == "operator"
    assert data_op["role"] == "operator"
    assert "access_token" in data_op
    op_token = data_op["access_token"]

    # 2. Check /auth/me for operator
    res_me_op = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {op_token}"})
    assert res_me_op.status_code == 200
    assert res_me_op.json() == {"username": "operator", "role": "operator"}

    # 3. Login viewer
    res_vw = client.post("/api/v1/auth/login", json={"username": "viewer", "password": "ViewPass123!"})
    assert res_vw.status_code == 200
    data_vw = res_vw.json()
    assert data_vw["username"] == "viewer"
    assert data_vw["role"] == "viewer"
    vw_token = data_vw["access_token"]

    # 4. Check /auth/me for viewer
    res_me_vw = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {vw_token}"})
    assert res_me_vw.status_code == 200
    assert res_me_vw.json() == {"username": "viewer", "role": "viewer"}


def test_login_invalid_password_returns_401(isolated_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid password returns 401."""
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "auth_secret", TEST_AUTH_SECRET)
    monkeypatch.setattr(settings, "operator_password", "CorrectPassword123")
    init_db(isolated_db, seed_demo=True)

    client = TestClient(app)
    res = client.post("/api/v1/auth/login", json={"username": "operator", "password": "WrongPassword"})
    assert res.status_code == 401
    assert "invalid" in res.json()["detail"].lower()


def test_login_unknown_user_returns_401(isolated_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-existent username returns 401."""
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "auth_secret", TEST_AUTH_SECRET)
    init_db(isolated_db, seed_demo=True)

    client = TestClient(app)
    res = client.post("/api/v1/auth/login", json={"username": "non_existent_user_999", "password": "AnyPassword"})
    assert res.status_code == 401
    assert "invalid" in res.json()["detail"].lower()


# ── 4. RBAC Method Enforcement Tests ──────────────────────────────────────────

def test_rbac_method_rules(isolated_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    When auth is enabled:
    - Unauthenticated protected request returns 401.
    - Viewer can GET (200) but is blocked on POST (403).
    - Operator can both GET (200) and POST (200).
    """
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "auth_secret", TEST_AUTH_SECRET)

    client = TestClient(app)

    # 1. Unauthenticated request to protected endpoint -> 401
    res_no_auth = client.get("/api/v1/topology")
    assert res_no_auth.status_code == 401

    # Generate tokens directly
    viewer_token, _ = create_access_token("viewer", "viewer", TEST_AUTH_SECRET)
    operator_token, _ = create_access_token("operator", "operator", TEST_AUTH_SECRET)

    # 2. Viewer GET /api/v1/topology -> allowed (200)
    res_vw_get = client.get("/api/v1/topology", headers={"Authorization": f"Bearer {viewer_token}"})
    assert res_vw_get.status_code == 200

    # 3. Viewer POST /api/v1/lab/run -> blocked (403)
    res_vw_post = client.post(
        "/api/v1/lab/run",
        json={"scenario": "baseline"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert res_vw_post.status_code == 403
    assert "operator" in res_vw_post.json()["detail"].lower()

    # 4. Operator GET /api/v1/topology -> allowed (200)
    res_op_get = client.get("/api/v1/topology", headers={"Authorization": f"Bearer {operator_token}"})
    assert res_op_get.status_code == 200

    # 5. Operator POST /api/v1/lab/run -> allowed (200)
    res_op_post = client.post(
        "/api/v1/lab/run",
        json={"scenario": "baseline"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert res_op_post.status_code == 200


# ── 5. Public and Agent Route Tests ───────────────────────────────────────────

def test_public_routes_remain_open_when_auth_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Public endpoints (/health, /api/v1/health) require no token."""
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "auth_secret", TEST_AUTH_SECRET)

    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 200


def test_agent_endpoints_require_x_api_key_when_auth_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Agent endpoints require valid X-API-Key header matching ingest_api_key."""
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "auth_secret", TEST_AUTH_SECRET)
    monkeypatch.setattr(settings, "ingest_api_key", "valid-agent-key-secret")

    client = TestClient(app)

    payload = {
        "agent_id": "agent-1",
        "site_id": "rampur",
        "timestamp": "2026-11-21T10:00:00Z",
    }

    # Missing X-API-Key -> 401
    res_no_key = client.post("/api/v1/agent/heartbeat", json=payload)
    assert res_no_key.status_code == 401

    # Invalid X-API-Key -> 401
    res_bad_key = client.post(
        "/api/v1/agent/heartbeat",
        json=payload,
        headers={"X-API-Key": "wrong-key"},
    )
    assert res_bad_key.status_code == 401

    # Valid X-API-Key -> 200
    res_good_key = client.post(
        "/api/v1/agent/heartbeat",
        json=payload,
        headers={"X-API-Key": "valid-agent-key-secret"},
    )
    assert res_good_key.status_code == 200


# ── 6. WebSocket Token Authentication ─────────────────────────────────────────

def test_websocket_token_enforcement(monkeypatch: pytest.MonkeyPatch) -> None:
    """WebSocket stream requires ?token= when auth is enabled."""
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "auth_secret", TEST_AUTH_SECRET)

    client = TestClient(app)

    # Without token -> closes with code 4001
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/telemetry"):
            pass

    # With valid token -> connects successfully
    token, _ = create_access_token("operator", "operator", TEST_AUTH_SECRET)
    with client.websocket_connect(f"/ws/telemetry?token={token}") as ws:
        msg = ws.receive_json()
        assert msg["type"] in ("connected", "telemetry_batch")
