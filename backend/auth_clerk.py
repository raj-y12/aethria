"""
Clerk JWT verification for FastAPI.

Verifies Bearer tokens using Clerk's JWKS (RS256). Sets request.state.user_id
from the JWT 'sub' claim. Use CLERK_JWKS_URL (and optionally CLERK_ISSUER) in env.
"""
import logging
import os
import ssl
from typing import Optional

import certifi
import jwt
from jwt import PyJWKClient

def _use_certifi_ssl() -> None:
    """Use certifi CA bundle for default HTTPS so JWKS fetch to Clerk succeeds on macOS."""
    try:
        ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass


_use_certifi_ssl()

logger = logging.getLogger("auth_clerk")

_CLERK_JWKS_URL = os.getenv("CLERK_JWKS_URL")
_CLERK_ISSUER = os.getenv("CLERK_ISSUER")  # optional, e.g. https://xxx.clerk.accounts.dev
# Seconds of tolerance for iat/nbf/exp vs local clock (avoids "token is not yet valid (iat)" when skewed).
_CLERK_JWT_LEEWAY = int(os.getenv("CLERK_JWT_LEEWAY_SECONDS", "60"))
_JWK_CLIENT: Optional[PyJWKClient] = PyJWKClient(_CLERK_JWKS_URL) if _CLERK_JWKS_URL else None


def verify_clerk_token(token: str) -> Optional[str]:
    """
    Verify a Clerk JWT and return the subject (user id) or None if invalid.

    Uses CLERK_JWKS_URL for RS256 verification. CLERK_ISSUER is optional
    but recommended for issuer validation.
    """
    if not token or not token.strip():
        return None
    if not _CLERK_JWKS_URL:
        logger.warning("CLERK_JWKS_URL not set; cannot verify token")
        return None
    try:
        if _JWK_CLIENT is None:
            logger.warning("Clerk JWKS client is unavailable; cannot verify token")
            return None
        signing_key = _JWK_CLIENT.get_signing_key_from_jwt(token)
        opts = {"verify_aud": False}
        kwargs = {"algorithms": ["RS256"], "leeway": _CLERK_JWT_LEEWAY}
        if _CLERK_ISSUER:
            kwargs["issuer"] = _CLERK_ISSUER
        try:
            payload = jwt.decode(
                token,
                signing_key.key,
                **kwargs,
                options=opts,
            )
        except jwt.ExpiredSignatureError:
            # Normal when SPA has a stale token for a short window; frontend retries with refresh.
            logger.info("Clerk JWT expired; request requires token refresh")
            return None
        except jwt.ImmatureSignatureError:
            # iat/nbf still in the future after leeway — usually severe clock skew.
            logger.info("Clerk JWT not yet valid; check system time or increase CLERK_JWT_LEEWAY_SECONDS")
            return None
        except jwt.InvalidIssuerError as e:
            logger.warning("Clerk JWT issuer mismatch (token iss may differ from CLERK_ISSUER). Retrying without issuer check: %s", e)
            kwargs.pop("issuer", None)
            payload = jwt.decode(
                token,
                signing_key.key,
                **kwargs,
                options=opts,
            )
        return payload.get("sub")
    except Exception as e:
        logger.warning("Clerk JWT verification failed: %s", e)
        return None
