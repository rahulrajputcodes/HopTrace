"""
Sliding-window rate limiting middleware for HopTrace API.

Enforces a maximum number of requests per minute per client IP when
settings.rate_limit_per_minute > 0.

Exempts:
- Health check (/api/v1/health) to ensure load balancers and containers are never blocked
- WebSocket connections (/ws/)
- CORS preflight OPTIONS requests
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, List
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings


class InMemoryRateLimiter:
    """Thread-safe sliding-window in-memory request counter per IP."""

    def __init__(self, window_seconds: float = 60.0) -> None:
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, client_ip: str, limit: int) -> tuple[bool, int]:
        """
        Check if client_ip is within the rate limit.

        Returns:
            (allowed: bool, retry_after_seconds: int)
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds
        timestamps = self._requests[client_ip]

        # Prune expired entries
        self._requests[client_ip] = [t for t in timestamps if t > cutoff]
        current_count = len(self._requests[client_ip])

        if current_count >= limit:
            oldest = self._requests[client_ip][0]
            retry_after = max(1, int(oldest + self.window_seconds - now) + 1)
            return False, retry_after

        self._requests[client_ip].append(now)
        return True, 0

    def reset(self) -> None:
        """Clear all rate limiting history."""
        self._requests.clear()


rate_limiter = InMemoryRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """ASGI middleware applying rate limits per client IP."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        limit = settings.rate_limit_per_minute
        if limit <= 0:
            return await call_next(request)

        # Exempt CORS preflight, health check, and WebSocket connections
        path = request.url.path
        if request.method == "OPTIONS" or path.startswith("/api/v1/health") or path.startswith("/ws"):
            return await call_next(request)

        # Resolve client IP
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        elif request.client and request.client.host:
            client_ip = request.client.host
        else:
            client_ip = "127.0.0.1"

        allowed, retry_after = rate_limiter.is_allowed(client_ip, limit)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded. Maximum {limit} requests per minute allowed.",
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
