"""Admin dashboard authentication helpers.

The admin dashboard intentionally uses a separate secret from normal Clerk user
auth. Keep this module small and dependency-free beyond PyJWT so route guards
can validate admin access without touching tenant-scoped state.
"""

from __future__ import annotations

import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt

_DEFAULT_ADMIN_TOKEN_TTL_MINUTES = 30


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _admin_token_secret() -> str:
    secret = os.getenv("ADMIN_TOKEN_SECRET", "").strip()
    if not secret:
        raise RuntimeError("ADMIN_TOKEN_SECRET is required")
    return secret


def _admin_token_ttl_minutes() -> int:
    raw = os.getenv("ADMIN_TOKEN_TTL_MINUTES", str(_DEFAULT_ADMIN_TOKEN_TTL_MINUTES)).strip()
    try:
        ttl = int(raw)
    except ValueError:
        return _DEFAULT_ADMIN_TOKEN_TTL_MINUTES
    return max(1, ttl)


def admin_token_ttl_seconds() -> int:
    return _admin_token_ttl_minutes() * 60


def validate_admin_secret(candidate: str) -> bool:
    expected = os.getenv("ADMIN_DASHBOARD_SECRET", "")
    if not expected:
        return False
    return hmac.compare_digest(candidate or "", expected)


def issue_admin_token(*, now: datetime | None = None) -> str:
    issued_at = now or _utcnow()
    expires_at = issued_at + timedelta(minutes=_admin_token_ttl_minutes())
    payload: Dict[str, Any] = {
        "scope": "admin",
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, _admin_token_secret(), algorithm="HS256")


def verify_admin_token(token: str, *, now: datetime | None = None) -> Dict[str, Any]:
    try:
        claims = jwt.decode(
            token,
            _admin_token_secret(),
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
    except jwt.PyJWTError as exc:
        raise ValueError("invalid admin token") from exc

    if claims.get("scope") != "admin":
        raise ValueError("invalid admin token")

    exp = claims.get("exp")
    if not isinstance(exp, int):
        raise ValueError("invalid admin token")

    comparison_time = now or _utcnow()
    if comparison_time.timestamp() >= exp:
        raise ValueError("expired admin token")

    return claims

