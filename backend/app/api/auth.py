"""
Authentication API endpoints (M2 Lane).

- POST /api/v1/auth/login
- GET  /api/v1/auth/me
"""
from __future__ import annotations

import collections
import time
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.auth.deps import get_current_user
from app.auth.security import create_access_token, dummy_verify, verify_password
from app.config import settings
from app.db.connection import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Stricter per-IP Rate Limiting for Login ──────────────────────────────────
_login_attempts: dict[str, collections.deque[float]] = collections.defaultdict(collections.deque)


def _check_login_rate_limit(request: Request) -> None:
    limit = getattr(settings, "login_rate_limit_per_minute", 10)
    if limit <= 0:
        return

    forwarded = request.headers.get("X-Forwarded-For")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")

    now = time.time()
    q = _login_attempts[ip]

    # Purge timestamps older than 60s
    while q and now - q[0] > 60.0:
        q.popleft()

    if len(q) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Login rate limit exceeded. Please wait a minute before retrying.",
            headers={"Retry-After": "60"},
        )

    q.append(now)


# ── Schemas ──────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    expires_at: str


class CurrentUserResponse(BaseModel):
    username: str
    role: str


# ── Endpoints ────────────────────────────────────────────────────────────────
@router.post("/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    request: Request,
    db=Depends(get_db),
) -> LoginResponse:
    """
    Authenticate with username and password. Returns signed bearer token.
    Enforces per-IP rate limiting and timing-attack protections.
    """
    _check_login_rate_limit(request)

    cur = db.execute(
        "SELECT id, username, password_hash, role FROM users WHERE username = ?",
        (req.username.strip(),),
    )
    row = cur.fetchone()

    if row is None:
        dummy_verify(req.password)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    user_id, username, password_hash, role = row[0], row[1], row[2], row[3]

    if not verify_password(req.password, password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    secret = getattr(settings, "auth_secret", "")
    if not secret:
        # If secret is empty during active auth login, server is misconfigured
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server authentication secret is not configured",
        )

    expire_minutes = getattr(settings, "auth_token_expire_minutes", 1440)
    token, expires_at = create_access_token(
        username=username,
        role=role,
        secret=secret,
        expires_in_minutes=expire_minutes,
    )

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        role=role,
        username=username,
        expires_at=expires_at,
    )


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(current_user: dict[str, Any] = Depends(get_current_user)) -> CurrentUserResponse:
    """Returns the authenticated user identity and role."""
    return CurrentUserResponse(
        username=current_user["username"],
        role=current_user["role"],
    )
