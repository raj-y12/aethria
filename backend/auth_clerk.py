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
        client = PyJWKClient(_CLERK_JWKS_URL)
        signing_key = client.get_signing_key_from_jwt(token)
        opts = {"verify_aud": False}
        kwargs = {"algorithms": ["RS256"]}
        if _CLERK_ISSUER:
            kwargs["issuer"] = _CLERK_ISSUER
        try:
            payload = jwt.decode(
                token,
                signing_key.key,
                **kwargs,
                options=opts,
            )
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
