"""Server-side audit logging for admin dashboard access."""

from __future__ import annotations

import logging
from typing import Any, Dict

from supabase_client import get_service_client

logger = logging.getLogger(__name__)


def record_admin_audit_event(
    *,
    event: str,
    success: bool,
    client_host: str | None = None,
    detail: Dict[str, Any] | None = None,
) -> None:
    try:
        get_service_client().table("admin_audit_log").insert(
            {
                "event": event,
                "success": success,
                "client_host": client_host,
                "detail": detail or {},
            }
        ).execute()
    except Exception as exc:
        logger.warning("Unable to write admin audit event %s: %s", event, exc)

