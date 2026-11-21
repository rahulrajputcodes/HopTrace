"""
Authentication & RBAC FastAPI dependencies (M2 Lane).
"""
from __future__ import annotations

import hmac
from typing import Any, Optional
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.security import decode_access_token
from app.config import settings

# HTTPBearer with auto_error=False so we can handle custom error messages / auth_disabled
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict[str, Any]:
    """
    Validate Bearer token and return current user payload.
    When auth_disabled=True, returns an operator identity immediately.
    """
    if getattr(settings, "auth_disabled", False):
        return {"username": "operator", "role": "operator"}

    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_access_token(token, getattr(settings, "auth_secret", ""))
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = payload.get("sub")
    role = payload.get("role")
    if not username or role not in ("operator", "viewer"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"username": username, "role": role}


async def enforce_rbac(
    request: Request,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Router-level dependency enforcing method-based RBAC:
    - GET / HEAD: requires 'viewer' or 'operator'
    - POST / PUT / DELETE / PATCH: requires 'operator'
    """
    if getattr(settings, "auth_disabled", False):
        return user

    role = user.get("role")
    if request.method in ("GET", "HEAD", "OPTIONS"):
        if role not in ("viewer", "operator"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: insufficient role permissions",
            )
    else:
        if role != "operator":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: operator role required for state modifications",
            )

    return user


async def require_agent_key(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> bool:
    """
    Validates X-API-Key header against ingest_api_key for write operations.
    Bypassed when auth_disabled=True or for read-only agent queries (GET /agent/status).
    """
    if getattr(settings, "auth_disabled", False):
        return True

    if request.method in ("GET", "HEAD", "OPTIONS"):
        return True

    expected_key = getattr(settings, "ingest_api_key", "").strip()
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ingest API key is not configured on server",
        )

    if not x_api_key or not hmac.compare_digest(x_api_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header",
        )

    return True
