"""
Supabase client factory: user-scoped (anon + JWT) and service-role (admin).

Uses env: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY.
"""
import logging
import os
from functools import lru_cache

import httpx

# Use the installed supabase package (pip install supabase)
from supabase import create_client, Client

logger = logging.getLogger("supabase_client")

SUPABASE_URL = os.environ.get("SUPABASE_URL") or os.environ.get("VITE_SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# The service client is process-wide (lru_cache) and its single httpx pool is shared
# across the FastAPI request threadpool AND the pipeline. Default httpx keepalive
# expiry is 5s, so the steady ~1/s frontend polling churns connections (open/close ->
# fd + TIME_WAIT pressure -> intermittent client-side EAGAIN, errno 11/35). Keeping
# connections warm longer maximises reuse and cuts that churn. Tunable via env.
_POOL_MAX_CONNECTIONS = max(1, int(os.getenv("SUPABASE_POOL_MAX_CONNECTIONS", "40")))
_POOL_MAX_KEEPALIVE = max(1, int(os.getenv("SUPABASE_POOL_MAX_KEEPALIVE", "20")))
_POOL_KEEPALIVE_EXPIRY = float(os.getenv("SUPABASE_POOL_KEEPALIVE_EXPIRY", "60"))


def _tune_postgrest_pool(client: Client) -> None:
    """Swap PostgREST's httpx session for one with a warm, bounded connection pool.

    Best-effort: preserves the auth headers/base_url supabase already configured and
    is a no-op if the internal shape changes. Never raises into client construction.
    """
    try:
        pg = getattr(client, "postgrest", None)
        old = getattr(pg, "session", None)
        if not isinstance(old, httpx.Client):
            return
        limits = httpx.Limits(
            max_connections=_POOL_MAX_CONNECTIONS,
            max_keepalive_connections=_POOL_MAX_KEEPALIVE,
            keepalive_expiry=_POOL_KEEPALIVE_EXPIRY,
        )
        tuned = httpx.Client(
            base_url=old.base_url,
            headers=old.headers,
            params=old.params,
            cookies=old.cookies,
            auth=old.auth,
            timeout=old.timeout,
            event_hooks=old.event_hooks,
            follow_redirects=getattr(old, "follow_redirects", False),
            limits=limits,
        )
        pg.session = tuned
        try:
            old.close()
        except Exception:
            pass
        logger.info(
            "PostgREST pool tuned: max_connections=%d max_keepalive=%d keepalive_expiry=%.0fs",
            _POOL_MAX_CONNECTIONS,
            _POOL_MAX_KEEPALIVE,
            _POOL_KEEPALIVE_EXPIRY,
        )
    except Exception as exc:  # pragma: no cover - defensive; lib internals may change
        logger.warning("Could not tune PostgREST pool (using library default): %s", exc)


@lru_cache(maxsize=1)
def get_service_client() -> Client:
    """
    Service-role Supabase client. Bypasses RLS; use only in trusted backend (e.g. agents).
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    _tune_postgrest_pool(client)
    return client


def get_user_client(user_jwt: str) -> Client:
    """
    User-scoped client: anon key + user JWT so RLS uses auth.jwt() ->> 'sub'.
    Sets the session so PostgREST sends the Clerk JWT on requests.
    """
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set")
    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    try:
        client.auth.set_session(access_token=user_jwt, refresh_token="")
    except TypeError:
        client.auth.set_session(user_jwt, "")
    return client
