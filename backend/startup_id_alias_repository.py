"""Tenant-scoped asyncpg access for approved legacy startup-ID aliases."""

from __future__ import annotations

import json
from typing import Any, Mapping

from tenant_context import require_user_id


class StartupIdAliasConflict(RuntimeError):
    """A legacy identifier is already bound to another canonical startup."""


class StartupIdAliasRepository:
    def __init__(self, pool: Any):
        self.pool = pool

    async def get_alias(self, user_id: str, legacy_startup_id: str) -> dict[str, Any] | None:
        uid = require_user_id(user_id, context="StartupIdAliasRepository.get_alias")
        legacy = str(legacy_startup_id).strip()
        if not legacy:
            return None
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                """select user_id, legacy_startup_id, canonical_startup_id, source,
                          source_reference, source_observation_id, verification_state,
                          verification_evidence, created_at, updated_at
                   from public.startup_id_aliases
                   where user_id=$1 and legacy_startup_id=$2""",
                uid,
                legacy,
            )
        return dict(row) if row is not None else None

    async def resolve_legacy_id(self, user_id: str, legacy_startup_id: str) -> str | None:
        alias = await self.get_alias(user_id, legacy_startup_id)
        if alias is None or alias["verification_state"] != "approved":
            return None
        return str(alias["canonical_startup_id"])

    async def insert_approved_alias(
        self,
        user_id: str,
        legacy_startup_id: str,
        canonical_startup_id: str,
        *,
        source: str,
        evidence: Mapping[str, Any],
        source_reference: str | None = None,
        source_observation_id: str | None = None,
    ) -> dict[str, Any]:
        uid = require_user_id(user_id, context="StartupIdAliasRepository.insert_approved_alias")
        legacy = str(legacy_startup_id).strip()
        canonical = str(canonical_startup_id).strip()
        if not legacy or not canonical or not str(source).strip():
            raise ValueError("legacy ID, canonical ID, and source are required")
        rows = await self.insert_approved_aliases(
            [{
                "user_id": uid,
                "legacy_startup_id": legacy,
                "canonical_startup_id": canonical,
                "source": str(source).strip(),
                "source_reference": source_reference,
                "source_observation_id": source_observation_id,
                "evidence": dict(evidence),
            }]
        )
        return rows[0]

    async def insert_approved_aliases(self, aliases: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
        """Atomically insert an approved reconciliation batch."""
        if not aliases:
            return []
        normalized: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in aliases:
            uid = require_user_id(
                str(item.get("user_id") or ""),
                context="StartupIdAliasRepository.insert_approved_aliases",
            )
            legacy = str(item.get("legacy_startup_id") or "").strip()
            canonical = str(item.get("canonical_startup_id") or "").strip()
            source = str(item.get("source") or "").strip()
            key = (uid, legacy)
            if not legacy or not canonical or not source:
                raise ValueError("legacy ID, canonical ID, and source are required")
            if key in seen:
                raise StartupIdAliasConflict(f"duplicate startup alias in batch: {key!r}")
            seen.add(key)
            normalized.append({
                "user_id": uid,
                "legacy_startup_id": legacy,
                "canonical_startup_id": canonical,
                "source": source,
                "source_reference": item.get("source_reference"),
                "source_observation_id": item.get("source_observation_id"),
                "evidence": dict(item.get("evidence") or {}),
            })

        results: list[dict[str, Any]] = []
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                for item in normalized:
                    uid = item["user_id"]
                    legacy = item["legacy_startup_id"]
                    canonical = item["canonical_startup_id"]
                    existing = await connection.fetchrow(
                    """select * from public.startup_id_aliases
                       where user_id=$1 and legacy_startup_id=$2
                       for update""",
                    uid, legacy)
                    if existing is not None:
                        if (
                            str(existing["canonical_startup_id"]) != canonical
                            or str(existing["source"]) != item["source"]
                        ):
                            raise StartupIdAliasConflict(
                                f"startup alias conflict for tenant={uid!r} legacy={legacy!r}"
                            )
                        if existing["verification_state"] != "approved":
                            raise StartupIdAliasConflict(
                                f"startup alias is not approved for tenant={uid!r} legacy={legacy!r}"
                            )
                        results.append(dict(existing))
                        continue
                    row = await connection.fetchrow(
                    """insert into public.startup_id_aliases
                       (user_id,legacy_startup_id,canonical_startup_id,source,
                        source_reference,source_observation_id,verification_state,
                        verification_evidence)
                       values ($1,$2,$3,$4,$5,$6,'approved',$7::jsonb)
                       returning *""",
                    uid, legacy, canonical, item["source"], item["source_reference"],
                    item["source_observation_id"], json.dumps(item["evidence"]),
                    )
                    results.append(dict(row))
        return results

    async def list_aliases_for_validation(self, user_id: str) -> list[dict[str, Any]]:
        uid = require_user_id(user_id, context="StartupIdAliasRepository.list_aliases_for_validation")
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                """select * from public.startup_id_aliases
                   where user_id=$1 order by legacy_startup_id""",
                uid,
            )
        return [dict(row) for row in rows]
