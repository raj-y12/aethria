"""Server-side audit logging for admin dashboard access."""

from __future__ import annotations

import logging
import json
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def record_admin_audit_event(
    *,
    pool: Any,
    event: str,
    success: bool,
    client_host: str | None = None,
    detail: Dict[str, Any] | None = None,
) -> None:
    """Best-effort admin audit insert through the application's asyncpg pool."""
    try:
        if pool is None:
            raise RuntimeError("database pool unavailable")
        async with pool.acquire() as connection:
            await connection.execute(
                """
                insert into public.admin_audit_log
                    (event, success, client_host, detail)
                values ($1, $2, $3, $4::jsonb)
                """,
                event,
                success,
                client_host,
                json.dumps(detail or {}),
            )
    except Exception as exc:
        logger.warning("Unable to write admin audit event %s: %s", event, exc)
