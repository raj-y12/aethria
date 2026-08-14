"""Provider-neutral external identity mappings.

Mappings are metadata about interoperability, never replacements for Aethria
identity. A remap is rejected; callers must explicitly retire the old mapping.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from tenant_context import require_user_id
from utils.timeutil import utcnow


class MappingConflict(ValueError):
    pass


class ExternalEntityMapping(BaseModel):
    mapping_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    provider: str
    entity_type: str
    aethria_entity_id: str
    external_entity_id: str
    workspace_id: str = "default"
    sync_status: str = "unmapped"
    last_synced_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    def model_post_init(self, __context: object) -> None:
        require_user_id(self.user_id, context="ExternalEntityMapping")


class MappingRegistry:
    """Small deterministic seam used by unit code and future adapters."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str, str, str, str], ExternalEntityMapping] = {}

    def upsert(self, mapping: ExternalEntityMapping) -> ExternalEntityMapping:
        uid = require_user_id(mapping.user_id, context="MappingRegistry.upsert")
        key = (uid, mapping.provider, mapping.workspace_id, mapping.entity_type, mapping.aethria_entity_id)
        external_key = (uid, mapping.provider, mapping.workspace_id, mapping.entity_type, mapping.external_entity_id)
        existing = self._rows.get(key)
        if existing and existing.external_entity_id != mapping.external_entity_id:
            raise MappingConflict("Aethria entity already has a different external mapping")
        for row in self._rows.values():
            row_key = (row.user_id, row.provider, row.workspace_id, row.entity_type, row.external_entity_id)
            if row_key == external_key and row.aethria_entity_id != mapping.aethria_entity_id:
                raise MappingConflict("External object already maps to another Aethria entity")
        self._rows[key] = existing or mapping
        return self._rows[key]

    def list_for_user(self, user_id: str) -> list[ExternalEntityMapping]:
        uid = require_user_id(user_id, context="MappingRegistry.list_for_user")
        return [row for row in self._rows.values() if row.user_id == uid]


class ExternalMappingRepository:
    def __init__(self, pool: Any):
        self.pool = pool

    async def upsert(self, mapping: ExternalEntityMapping) -> ExternalEntityMapping:
        uid = require_user_id(mapping.user_id, context="ExternalMappingRepository.upsert")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """insert into public.external_entity_mappings
                (mapping_id,user_id,provider,entity_type,aethria_entity_id,external_entity_id,workspace_id,sync_status,last_synced_at,created_at,updated_at)
                values ($1,$2,$3,$4,$5,$6,$7,$8,$9,now(),now())
                on conflict (user_id,provider,workspace_id,entity_type,aethria_entity_id)
                do update set sync_status=excluded.sync_status,last_synced_at=excluded.last_synced_at,updated_at=now()
                returning *""",
                mapping.mapping_id, uid, mapping.provider, mapping.entity_type,
                mapping.aethria_entity_id, mapping.external_entity_id, mapping.workspace_id,
                mapping.sync_status, mapping.last_synced_at,
            )
        if row is None:
            raise MappingConflict("External mapping was rejected")
        return ExternalEntityMapping.model_validate(dict(row))
