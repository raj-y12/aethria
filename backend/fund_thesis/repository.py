"""Async PostgreSQL read repository for the fund-thesis subsystem."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from tenant_context import require_user_id


def _json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return default
    return value


class FundThesisRepository:
    """Tenant-scoped, read-only thesis repository over the shared asyncpg pool."""

    def __init__(self, pool: Any):
        self.pool = pool

    async def get_active(
        self,
        user_id: str,
        *,
        include_embedding: bool = True,
    ) -> dict[str, Any] | None:
        uid = require_user_id(user_id, context="FundThesisRepository.get_active")
        thesis = await self.pool.fetchrow(
            """
            select id, user_id, active_version_id, created_at, updated_at
            from public.fund_thesis
            where user_id=$1
            limit 1
            """,
            uid,
        )
        if thesis is None or thesis["active_version_id"] is None:
            return None
        version = await self.pool.fetchrow(
            """
            select id, thesis_id, user_id, version_number, raw_text,
                   parsed_json, is_active, created_at
            from public.fund_thesis_versions
            where user_id=$1 and id=$2 and thesis_id=$3
            limit 1
            """,
            uid,
            thesis["active_version_id"],
            thesis["id"],
        )
        if version is None:
            return None
        result = self._version_row(thesis, version)
        if include_embedding:
            result["embedding"] = []
            result["embedding_model"] = "none"
            embedding = await self.get_embedding(uid, str(version["id"]))
            if embedding is not None:
                result["embedding"] = _json(embedding["embedding_vector"], [])
                result["embedding_model"] = str(embedding["model"] or "none")
        return result

    async def get_version(self, user_id: str, version_id: str) -> dict[str, Any] | None:
        uid = require_user_id(user_id, context="FundThesisRepository.get_version")
        row = await self.pool.fetchrow(
            """
            select v.id, v.thesis_id, v.user_id, v.version_number, v.raw_text,
                   v.parsed_json, v.is_active, v.created_at,
                   t.active_version_id, t.updated_at as thesis_updated_at
            from public.fund_thesis_versions v
            join public.fund_thesis t on t.id=v.thesis_id and t.user_id=v.user_id
            where v.user_id=$1 and v.id=$2
            limit 1
            """,
            uid,
            version_id,
        )
        if row is None:
            return None
        return self._version_row(row, row)

    async def list_versions(
        self,
        user_id: str,
        *,
        thesis_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        uid = require_user_id(user_id, context="FundThesisRepository.list_versions")
        rows = await self.pool.fetch(
            """
            select v.id, v.thesis_id, v.user_id, v.version_number, v.raw_text,
                   v.parsed_json, v.is_active, v.created_at,
                   t.active_version_id, t.updated_at as thesis_updated_at
            from public.fund_thesis_versions v
            join public.fund_thesis t on t.id=v.thesis_id and t.user_id=v.user_id
            where v.user_id=$1 and ($2::uuid is null or v.thesis_id=$2)
            order by v.version_number desc, v.created_at desc, v.id desc
            limit $3
            """,
            uid,
            thesis_id,
            max(1, min(int(limit), 500)),
        )
        return [self._version_row(row, row) for row in rows]

    async def get_embedding(self, user_id: str, version_id: str) -> dict[str, Any] | None:
        uid = require_user_id(user_id, context="FundThesisRepository.get_embedding")
        row = await self.pool.fetchrow(
            """
            select id, user_id, version_id, embedding_vector, model, created_at
            from public.fund_thesis_embeddings
            where user_id=$1 and version_id=$2
            limit 1
            """,
            uid,
            version_id,
        )
        return dict(row) if row is not None else None

    async def list_versions_missing_embeddings(
        self,
        user_id: str,
        *,
        only_active: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        uid = require_user_id(
            user_id,
            context="FundThesisRepository.list_versions_missing_embeddings",
        )
        rows = await self.pool.fetch(
            """
            select v.id, v.thesis_id, v.user_id, v.version_number, v.raw_text,
                   v.parsed_json, v.is_active, v.created_at
            from public.fund_thesis_versions v
            join public.fund_thesis t on t.id=v.thesis_id and t.user_id=v.user_id
            left join public.fund_thesis_embeddings e
              on e.user_id=v.user_id and e.version_id=v.id
            where v.user_id=$1
              and ($2::boolean = false or t.active_version_id=v.id)
              and (e.version_id is null or e.embedding_vector='[]'::jsonb
                   or lower(coalesce(e.model,'')) in ('','none'))
            order by v.version_number desc, v.created_at desc, v.id desc
            limit $3
            """,
            uid,
            only_active,
            max(1, min(int(limit), 500)),
        )
        return [self._version_row(row, row) for row in rows]

    async def get_pipeline_links(
        self,
        user_id: str,
        *,
        version_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        uid = require_user_id(user_id, context="FundThesisRepository.get_pipeline_links")
        rows = await self.pool.fetch(
            """
            select id, user_id, thesis_version_id, pipeline_run_id,
                   affected_startups_count, created_at
            from public.fund_thesis_pipeline_link
            where user_id=$1 and ($2::uuid is null or thesis_version_id=$2)
            order by created_at desc, id desc
            limit $3
            """,
            uid,
            version_id,
            max(1, min(int(limit), 500)),
        )
        return [
            {
                "link_id": str(row["id"]),
                "user_id": row["user_id"],
                "version_id": str(row["thesis_version_id"]),
                "pipeline_run_id": str(row["pipeline_run_id"]) if row["pipeline_run_id"] else None,
                "affected_startups_count": row["affected_startups_count"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    async def ensure_thesis(self, user_id: str) -> dict[str, Any]:
        """Create or lock the tenant's thesis root inside a short transaction."""
        uid = require_user_id(user_id, context="FundThesisRepository.ensure_thesis")
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    insert into public.fund_thesis (user_id)
                    values ($1)
                    on conflict (user_id) do nothing
                    """,
                    uid,
                )
                row = await connection.fetchrow(
                    """
                    select id, user_id, active_version_id, created_at, updated_at
                    from public.fund_thesis
                    where user_id=$1
                    for update
                    """,
                    uid,
                )
        if row is None:
            raise RuntimeError("failed to ensure fund_thesis row")
        return dict(row)

    async def ensure_default(
        self,
        user_id: str,
        *,
        raw_text: str,
        parsed_json: dict[str, Any],
    ) -> dict[str, Any]:
        """Create or repair the default active version under the root lock."""
        uid = require_user_id(user_id, context="FundThesisRepository.ensure_default")
        changed = False
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "insert into public.fund_thesis (user_id) values ($1) on conflict (user_id) do nothing",
                    uid,
                )
                thesis = await connection.fetchrow(
                    "select id, active_version_id from public.fund_thesis where user_id=$1 for update",
                    uid,
                )
                active = await connection.fetchrow(
                    "select id, version_number from public.fund_thesis_versions where id=$1 and thesis_id=$2 and user_id=$3",
                    thesis["active_version_id"], thesis["id"], uid,
                ) if thesis["active_version_id"] else None
                if active is None:
                    latest = await connection.fetchrow(
                        """
                        select id, version_number from public.fund_thesis_versions
                        where thesis_id=$1 and user_id=$2
                        order by version_number desc, created_at desc, id desc
                        limit 1
                        """,
                        thesis["id"], uid,
                    )
                    if latest is not None:
                        await connection.execute(
                            "update public.fund_thesis_versions set is_active=false where thesis_id=$1",
                            thesis["id"],
                        )
                        await connection.execute(
                            "update public.fund_thesis_versions set is_active=true where id=$1",
                            latest["id"],
                        )
                        await connection.execute(
                            "update public.fund_thesis set active_version_id=$2, updated_at=timezone('utc', now()) where id=$1",
                            thesis["id"], latest["id"],
                        )
                        active = latest
                        changed = True
                    else:
                        version_id = uuid4()
                        await connection.execute(
                            """
                            insert into public.fund_thesis_versions
                              (id,user_id,thesis_id,version_number,raw_text,parsed_json,is_active)
                            values ($1,$2,$3,1,$4,$5::jsonb,true)
                            """,
                            version_id, uid, thesis["id"], raw_text.strip(), json.dumps(parsed_json),
                        )
                        await connection.execute(
                            "insert into public.fund_thesis_embeddings (user_id,version_id,embedding_vector,model) values ($1,$2,'[]'::jsonb,'none')",
                            uid, version_id,
                        )
                        await connection.execute(
                            "update public.fund_thesis set active_version_id=$2, updated_at=timezone('utc', now()) where id=$1",
                            thesis["id"], version_id,
                        )
                        await connection.execute(
                            "insert into public.fund_thesis_pipeline_link (user_id,thesis_version_id,affected_startups_count) values ($1,$2,0)",
                            uid, version_id,
                        )
                        active = {"id": version_id, "version_number": 1}
                        changed = True
        if changed:
            self._invalidate_cache(uid)
        return {
            "thesis_id": str(thesis["id"]),
            "version_id": str(active["id"]),
            "version_number": int(active["version_number"]),
            "skipped": not changed,
        }

    async def publish_version(
        self,
        user_id: str,
        *,
        raw_text: str,
        parsed_json: dict[str, Any],
        embedding: list[float] | None,
        embedding_model: str = "none",
        pipeline_run_id: str | None = None,
        affected_startups_count: int = 0,
        skip_if_unchanged: bool = False,
    ) -> dict[str, Any]:
        """Atomically publish a new active thesis version for one tenant."""
        uid = require_user_id(user_id, context="FundThesisRepository.publish_version")
        raw = (raw_text or "").strip()
        if not raw:
            raise ValueError("raw_text required")
        payload = parsed_json if isinstance(parsed_json, dict) else {}
        vector = embedding if isinstance(embedding, list) else []
        affected = max(0, int(affected_startups_count or 0))
        skipped = False
        result: dict[str, Any]
        sync_raw_text = raw
        sync_parsed_json = payload
        sync_version_number: int | None = None
        sync_version_id: str | None = None

        async with self.pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    """
                    insert into public.fund_thesis (user_id)
                    values ($1)
                    on conflict (user_id) do nothing
                    """,
                    uid,
                )
                thesis = await connection.fetchrow(
                    """
                    select id, active_version_id
                    from public.fund_thesis
                    where user_id=$1
                    for update
                    """,
                    uid,
                )
                if thesis is None:
                    raise RuntimeError("failed to lock fund_thesis row")
                active = await connection.fetchrow(
                    """
                    select raw_text, parsed_json, id, version_number
                    from public.fund_thesis_versions
                    where id=$1 and thesis_id=$2 and user_id=$3
                    """,
                    thesis["active_version_id"],
                    thesis["id"],
                    uid,
                ) if thesis["active_version_id"] else None
                if skip_if_unchanged and active is not None:
                    from utils.settings_loader import thesis_payload_fingerprint

                    if thesis_payload_fingerprint(
                        raw_text=raw,
                        parsed_json=payload,
                    ) == thesis_payload_fingerprint(
                        raw_text=active["raw_text"],
                        parsed_json=_json(active["parsed_json"], {}),
                    ):
                        skipped = True
                        result = {
                            "thesis_id": str(thesis["id"]),
                            "version_id": str(active["id"]),
                            "version_number": int(active["version_number"]),
                            "skipped": True,
                        }
                        sync_raw_text = str(active["raw_text"] or "")
                        sync_parsed_json = _json(active["parsed_json"], {})
                        sync_version_number = int(active["version_number"])
                        sync_version_id = str(active["id"])
                    else:
                        result = {}
                else:
                    result = {}
                if not skipped:
                    next_number = await connection.fetchval(
                        """
                        select coalesce(max(version_number), 0) + 1
                        from public.fund_thesis_versions
                        where thesis_id=$1 and user_id=$2
                        """,
                        thesis["id"],
                        uid,
                    )
                    version_id = uuid4()
                    await connection.execute(
                        "update public.fund_thesis_versions set is_active=false where thesis_id=$1",
                        thesis["id"],
                    )
                    await connection.execute(
                        """
                        insert into public.fund_thesis_versions
                          (id,user_id,thesis_id,version_number,raw_text,parsed_json,is_active)
                        values ($1,$2,$3,$4,$5,$6::jsonb,true)
                        """,
                        version_id,
                        uid,
                        thesis["id"],
                        int(next_number),
                        raw,
                        json.dumps(payload),
                    )
                    await connection.execute(
                        """
                        insert into public.fund_thesis_embeddings
                          (user_id,version_id,embedding_vector,model)
                        values ($1,$2,$3::jsonb,$4)
                        on conflict (version_id) do update
                        set user_id=excluded.user_id,
                            embedding_vector=excluded.embedding_vector,
                            model=excluded.model
                        """,
                        uid,
                        version_id,
                        json.dumps(vector),
                        (embedding_model or "none").strip() or "none",
                    )
                    await connection.execute(
                        """
                        update public.fund_thesis
                        set active_version_id=$2, updated_at=timezone('utc', now())
                        where id=$1 and user_id=$3
                        """,
                        thesis["id"],
                        version_id,
                        uid,
                    )
                    await connection.execute(
                        """
                        insert into public.fund_thesis_pipeline_link
                          (user_id,thesis_version_id,pipeline_run_id,affected_startups_count)
                        values ($1,$2,$3,$4)
                        """,
                        uid,
                        version_id,
                        pipeline_run_id,
                        affected,
                    )
                    result = {
                        "thesis_id": str(thesis["id"]),
                        "version_id": str(version_id),
                        "version_number": int(next_number),
                        "skipped": False,
                    }
                    sync_version_number = int(next_number)
                    sync_version_id = str(version_id)
                await self._sync_existing_settings_projection(
                    connection,
                    uid,
                    raw_text=sync_raw_text,
                    parsed_json=sync_parsed_json,
                    version_number=sync_version_number,
                    version_id=sync_version_id,
                )
        if not skipped:
            self._invalidate_cache(uid)
        return result

    async def activate_version(
        self,
        user_id: str,
        version_id: str,
        *,
        pipeline_run_id: str | None = None,
        affected_startups_count: int = 0,
    ) -> None:
        """Atomically activate a tenant-owned historical thesis version."""
        uid = require_user_id(user_id, context="FundThesisRepository.activate_version")
        vid = (version_id or "").strip()
        if not vid:
            raise ValueError("version_id required")
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                thesis = await connection.fetchrow(
                    "select id from public.fund_thesis where user_id=$1 for update",
                    uid,
                )
                if thesis is None:
                    raise ValueError("version not found")
                version = await connection.fetchrow(
                    """
                    select id, version_number, raw_text, parsed_json from public.fund_thesis_versions
                    where id=$1 and thesis_id=$2 and user_id=$3
                    """,
                    vid,
                    thesis["id"],
                    uid,
                )
                if version is None:
                    raise ValueError("version not found")
                await connection.execute(
                    "update public.fund_thesis_versions set is_active=false where thesis_id=$1",
                    thesis["id"],
                )
                await connection.execute(
                    "update public.fund_thesis_versions set is_active=true where id=$1 and user_id=$2",
                    vid,
                    uid,
                )
                await self._sync_existing_settings_projection(
                    connection,
                    uid,
                    raw_text=str(version["raw_text"] or ""),
                    parsed_json=_json(version["parsed_json"], {}),
                    version_number=int(version["version_number"]),
                    version_id=str(version["id"]),
                )
                await connection.execute(
                    """
                    update public.fund_thesis
                    set active_version_id=$2, updated_at=timezone('utc', now())
                    where id=$1 and user_id=$3
                    """,
                    thesis["id"],
                    vid,
                    uid,
                )
                await connection.execute(
                    """
                    insert into public.fund_thesis_pipeline_link
                      (user_id,thesis_version_id,pipeline_run_id,affected_startups_count)
                    values ($1,$2,$3,$4)
                    """,
                    uid,
                    vid,
                    pipeline_run_id,
                    max(0, int(affected_startups_count or 0)),
                )
        self._invalidate_cache(uid)

    async def _sync_existing_settings_projection(
        self,
        connection: Any,
        user_id: str,
        *,
        raw_text: str,
        parsed_json: dict[str, Any],
        version_number: int | None,
        version_id: str | None,
    ) -> None:
        """Keep an existing settings document aligned with canonical thesis data."""
        row = await connection.fetchrow(
            "select data from public.settings where user_id=$1 and key=$1 for update",
            user_id,
        )
        if row is None:
            return
        from utils.settings_loader import reconcile_fund_config_with_thesis

        data = row["data"]
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = {}
        if not isinstance(data, dict):
            data = {}
        updated = dict(data)
        updated["fund_config"] = reconcile_fund_config_with_thesis(
            data.get("fund_config") if isinstance(data.get("fund_config"), dict) else {},
            raw_text=raw_text,
            parsed_json=parsed_json,
            version_number=version_number,
            version_id=version_id,
        )
        await connection.execute(
            "update public.settings set data=$2::jsonb where user_id=$1 and key=$1",
            user_id,
            json.dumps(updated),
        )

    async def upsert_embedding(
        self,
        user_id: str,
        version_id: str,
        vector: list[float],
        model: str,
    ) -> None:
        """Tenant-safe, retryable embedding upsert."""
        uid = require_user_id(user_id, context="FundThesisRepository.upsert_embedding")
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                exists = await connection.fetchval(
                    """
                    select 1 from public.fund_thesis_versions
                    where id=$1 and user_id=$2
                    """,
                    version_id,
                    uid,
                )
                if not exists:
                    raise ValueError("version not found")
                await connection.execute(
                    """
                    insert into public.fund_thesis_embeddings
                      (user_id,version_id,embedding_vector,model)
                    values ($1,$2,$3::jsonb,$4)
                    on conflict (version_id) do update
                    set user_id=excluded.user_id,
                        embedding_vector=excluded.embedding_vector,
                        model=excluded.model
                    """,
                    uid,
                    version_id,
                    json.dumps(vector if isinstance(vector, list) else []),
                    (model or "none").strip() or "none",
                )
        self._invalidate_cache(uid)

    @staticmethod
    def _invalidate_cache(user_id: str) -> None:
        from fund_thesis import invalidate_thesis_cache

        invalidate_thesis_cache(user_id)

    @staticmethod
    def _version_row(thesis: Any, version: Any) -> dict[str, Any]:
        thesis_id = thesis["id"] if "id" in thesis and "active_version_id" in thesis else version["thesis_id"]
        return {
            "thesis_id": str(thesis_id),
            "version_id": str(version["id"]),
            "user_id": version["user_id"],
            "version_number": int(version["version_number"]),
            "raw_text": version["raw_text"],
            "parsed_json": _json(version["parsed_json"], {}),
            "is_active": bool(version["is_active"]),
            "active_version_id": str(thesis["active_version_id"]) if thesis.get("active_version_id") else None,
            "created_at": version["created_at"],
            "thesis_updated_at": thesis.get("thesis_updated_at") or thesis.get("updated_at"),
        }
