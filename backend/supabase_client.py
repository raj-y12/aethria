"""
Supabase client factory: user-scoped (anon + JWT) and service-role (admin).

Uses env: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY.
"""
import os
from functools import lru_cache

# Use the installed supabase package (pip install supabase)
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL") or os.environ.get("VITE_SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


@lru_cache(maxsize=1)
def get_service_client() -> Client:
    """
    Service-role Supabase client. Bypasses RLS; use only in trusted backend (e.g. agents).
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


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
