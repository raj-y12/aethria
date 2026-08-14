"""Direct PostgreSQL persistence for tenant settings documents."""

from __future__ import annotations

import json
from typing import Any, Optional

from tenant_context import require_user_id


class SettingsRepository:
    """Persist one settings JSONB document per explicit tenant and key."""

    def __init__(self, pool: Any):
        self.pool = pool

    async def get(self, user_id: str, *, key: Optional[str] = None) -> Any | None:
        uid = require_user_id(user_id, context="SettingsRepository.get")
        document_key = key or uid
        row = await self.pool.fetchrow(
            """
            select data
              from public.settings
             where user_id = $1
               and key = $2
             limit 1
            """,
            uid,
            document_key,
        )
        if row is None:
            return None
        value = row["data"]
        return json.loads(value) if isinstance(value, str) else value

    async def upsert(
        self,
        user_id: str,
        data: dict[str, Any],
        *,
        key: Optional[str] = None,
    ) -> None:
        uid = require_user_id(user_id, context="SettingsRepository.upsert")
        document_key = key or uid
        encoded = json.dumps(data, ensure_ascii=False)
        await self.pool.execute(
            """
            insert into public.settings (user_id, key, data)
            values ($1, $2, $3::jsonb)
            on conflict (user_id, key)
            do update set data = excluded.data
            """,
            uid,
            document_key,
            encoded,
        )

    async def list_all(self) -> list[dict[str, Any]]:
        rows = await self.pool.fetch(
            "select user_id, key, data from public.settings order by user_id, key"
        )
        result: list[dict[str, Any]] = []
        for row in rows:
            value = row["data"]
            result.append(
                {
                    "user_id": row["user_id"],
                    "key": row["key"],
                    "data": json.loads(value) if isinstance(value, str) else value,
                }
            )
        return result

    async def get_active_thesis_for_settings(self, user_id: str) -> dict[str, Any] | None:
        """Read the tenant's canonical active thesis for settings projection."""
        uid = require_user_id(user_id, context="SettingsRepository.get_active_thesis_for_settings")
        row = await self.pool.fetchrow(
            """
            select v.id as version_id,
                   v.version_number,
                   v.raw_text,
                   v.parsed_json
              from public.fund_thesis t
              join public.fund_thesis_versions v
                on v.id = t.active_version_id
               and v.thesis_id = t.id
               and v.user_id = t.user_id
             where t.user_id = $1
             limit 1
            """,
            uid,
        )
        if row is None:
            return None
        parsed = row["parsed_json"]
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except json.JSONDecodeError:
                parsed = {}
        return {
            "version_id": str(row["version_id"]),
            "version_number": row["version_number"],
            "raw_text": row["raw_text"] or "",
            "parsed_json": parsed if isinstance(parsed, dict) else {},
        }
