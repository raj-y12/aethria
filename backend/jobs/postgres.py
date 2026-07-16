"""Direct PostgreSQL pool configuration for durable job execution."""

from __future__ import annotations

import os
from typing import Any, Awaitable, Callable, Optional


class DurableJobConfigurationError(RuntimeError):
    pass


def database_dsn() -> str:
    return (
        os.getenv("DATABASE_URL", "") or os.getenv("SUPABASE_DB_URL", "")
    ).strip()


async def create_pool(
    *,
    create_pool_fn: Optional[Callable[..., Awaitable[Any]]] = None,
):
    dsn = database_dsn()
    if not dsn:
        raise DurableJobConfigurationError(
            "Durable jobs require DATABASE_URL or SUPABASE_DB_URL"
        )
    if create_pool_fn is None:
        import asyncpg

        create_pool_fn = asyncpg.create_pool
    min_size = max(1, int(os.getenv("DURABLE_JOB_DB_POOL_MIN", "1")))
    max_size = max(min_size, int(os.getenv("DURABLE_JOB_DB_POOL_MAX", "4")))
    command_timeout = max(
        1.0, float(os.getenv("DURABLE_JOB_DB_COMMAND_TIMEOUT_SECONDS", "30"))
    )
    return await create_pool_fn(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        command_timeout=command_timeout,
    )
