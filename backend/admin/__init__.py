"""Admin domain: separate secret-based operator login, audit, and overview.

Consolidates four top-level modules into one package. External code should
import from `admin` directly (`from admin import build_admin_overview`); the
submodule split below is an internal detail.

- audit: `admin_audit_log` writes (`record_admin_audit_event`).
- auth: admin token issue/verify, separate from the Clerk end-user JWT path.
- clerk: read-only Clerk Backend API calls (session/user listing) for the
  admin overview — distinct from `auth_clerk.py`, which verifies end-user JWTs.
- service: aggregates admin overview data (uses `admin.clerk`).
"""
from __future__ import annotations

from admin.audit import record_admin_audit_event
from admin.auth import admin_token_ttl_seconds, issue_admin_token, validate_admin_secret, verify_admin_token
from admin.clerk import list_active_sessions_by_user, list_clerk_users
from admin.service import build_admin_overview, build_admin_overview_from_rows

__all__ = [
    "admin_token_ttl_seconds",
    "build_admin_overview",
    "build_admin_overview_from_rows",
    "issue_admin_token",
    "list_active_sessions_by_user",
    "list_clerk_users",
    "record_admin_audit_event",
    "validate_admin_secret",
    "verify_admin_token",
]
