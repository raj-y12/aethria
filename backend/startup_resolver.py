"""Canonical startup lookup with explicit legacy-ID alias resolution."""

from __future__ import annotations

from typing import Any

from startup_id_alias_repository import StartupIdAliasRepository
from startup_repository import StartupRepository


class CanonicalStartupResolver:
    def __init__(self, pool: Any):
        self.startups = StartupRepository(pool)
        self.aliases = StartupIdAliasRepository(pool)

    async def resolve_startup_id(self, user_id: str, startup_id: str) -> str | None:
        direct = await self.startups.exists(user_id, startup_id)
        if direct:
            return str(startup_id)
        return await self.aliases.resolve_legacy_id(user_id, startup_id)

    async def get_startup(self, user_id: str, startup_id: str) -> dict[str, Any] | None:
        canonical_id = await self.resolve_startup_id(user_id, startup_id)
        if canonical_id is None:
            return None
        return await self.startups.get_startup(user_id, canonical_id)
