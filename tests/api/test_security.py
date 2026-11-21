"""
Tests for security middleware: strict CORS and rate limiting.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.middleware.rate_limit import rate_limiter


def test_cors_allowed_origin(client: TestClient) -> None:
    """Allowed origin receives Access-Control-Allow-Origin header."""
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/api/v1/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_disallowed_origin(client: TestClient) -> None:
    """Disallowed origin does NOT receive Access-Control-Allow-Origin header."""
    headers = {
        "Origin": "http://malicious-site.example.com",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/api/v1/health", headers=headers)
    assert response.headers.get("access-control-allow-origin") != "http://malicious-site.example.com"


def test_rate_limiting_enforced(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """When RATE_LIMIT_PER_MINUTE is set, requests exceeding the limit receive HTTP 429."""
    rate_limiter.reset()
    monkeypatch.setattr(settings, "rate_limit_per_minute", 3)

    client_headers = {"X-Forwarded-For": "198.51.100.42"}

    for _ in range(3):
        res = client.get("/api/v1/subscribers", headers=client_headers)
        assert res.status_code == 200

    res_429 = client.get("/api/v1/subscribers", headers=client_headers)
    assert res_429.status_code == 429
    data = res_429.json()
    assert "rate limit exceeded" in data["detail"].lower()
    assert "retry-after" in res_429.headers
    assert int(res_429.headers["retry-after"]) > 0

    rate_limiter.reset()


def test_rate_limiting_exempts_health_check(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Health check endpoint is exempt from rate limiting."""
    rate_limiter.reset()
    monkeypatch.setattr(settings, "rate_limit_per_minute", 2)

    client_headers = {"X-Forwarded-For": "198.51.100.99"}

    for _ in range(5):
        res = client.get("/api/v1/health", headers=client_headers)
        assert res.status_code == 200

    rate_limiter.reset()
