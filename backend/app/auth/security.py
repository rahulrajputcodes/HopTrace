"""
Cryptographic security primitives for HopTrace (M2 Lane).

- Password hashing: scrypt (scrypt$n$r$p$salt$hash)
- Signed expiring bearer tokens: HMAC-SHA256 (HS256) base64url encoded
- Timing-attack mitigations: hmac.compare_digest and dummy scrypt verification
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Optional, Tuple


# Default scrypt parameters (OWASP / RFC 7914 recommendation for interactive logins)
SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32

def _b64url_encode(data: bytes) -> str:
    """Encode bytes to unpadded base64url string."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    """Decode unpadded or padded base64url string to bytes."""
    pad = len(s) % 4
    if pad:
        s += "=" * (4 - pad)
    return base64.urlsafe_b64decode(s.encode("ascii"))


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using standard library scrypt.
    Format: scrypt$n$r$p$salt$hash
    """
    salt = secrets.token_hex(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt.encode("ascii"),
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    ).hex()
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt}${derived}"


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verify a plaintext password against a stored scrypt hash string.
    Uses hmac.compare_digest for constant-time comparison.
    """
    try:
        parts = stored_hash.split("$")
        if len(parts) != 6 or parts[0] != "scrypt":
            return False
        n = int(parts[1])
        r = int(parts[2])
        p = int(parts[3])
        salt = parts[4].encode("ascii")
        expected_hex = parts[5]

        computed_hex = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(bytes.fromhex(expected_hex)),
        ).hex()

        return hmac.compare_digest(computed_hex, expected_hex)
    except Exception:
        return False


# Pre-computed dummy hash to mitigate user enumeration timing side channels
_DUMMY_HASH = hash_password("dummy-hoptrace-account-password-not-real")


def dummy_verify(password: str) -> bool:
    """
    Execute constant-time scrypt calculation against dummy hash for non-existent users.
    Always returns False.
    """
    verify_password(password, _DUMMY_HASH)
    return False


def create_access_token(
    username: str,
    role: str,
    secret: str,
    expires_in_minutes: int = 1440,
) -> Tuple[str, str]:
    """
    Create a signed HMAC-SHA256 bearer token with expiration.
    Returns (token_string, expires_at_iso_utc).
    """
    if not secret:
        raise ValueError("auth_secret must not be empty when generating access token.")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=expires_in_minutes)

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": username,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }

    h_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    p_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    h_b64 = _b64url_encode(h_bytes)
    p_b64 = _b64url_encode(p_bytes)

    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)

    token = f"{h_b64}.{p_b64}.{sig_b64}"
    return token, expires_at.isoformat()


def decode_access_token(token: str, secret: str) -> Optional[dict[str, Any]]:
    """
    Validate signature and expiration of an HS256 token.
    Returns decoded payload dict if valid, or None if invalid/expired/tampered.
    """
    if not token or not secret:
        return None

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        h_b64, p_b64, sig_b64 = parts

        # Verify signature in constant time
        signing_input = f"{h_b64}.{p_b64}".encode("ascii")
        expected_sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)

        if not hmac.compare_digest(actual_sig, expected_sig):
            return None

        header = json.loads(_b64url_decode(h_b64).decode("utf-8"))
        if header.get("alg") != "HS256":
            return None

        payload = json.loads(_b64url_decode(p_b64).decode("utf-8"))
        exp = payload.get("exp")
        if exp is None or not isinstance(exp, (int, float)):
            return None

        now_ts = int(time.time())
        if now_ts >= exp:
            return None

        return payload
    except Exception:
        return None
