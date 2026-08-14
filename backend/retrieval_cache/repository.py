"""Provider-neutral PostgreSQL repository for retrieval observations."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from tenant_context import require_user_id


class RetrievalCacheRepository:
    def __init__(self, pool: Any):
        self.pool = pool

    async def get_fresh(self, *, user_id: str, query_identity: str, category: str, max_results: int, ttl_seconds: int) -> dict[str, Any] | None:
        uid = require_user_id(user_id, context="RetrievalCacheRepository.get_fresh")
        if ttl_seconds <= 0:
            return None
        row = await self.pool.fetchrow(
            """
            select sources, provider, diagnostics, fetched_at
            from public.retrieval_cache_entries
            where user_id=$1 and query_identity=$2 and category=$3
              and status='success' and fetched_at >= now() - ($4::bigint * interval '1 second')
            order by fetched_at desc limit 1
            """,
            uid, query_identity, category, ttl_seconds,
        )
        if row is None:
            return None
        sources = row["sources"] if isinstance(row["sources"], list) else json.loads(row["sources"] or "[]")
        return {
            "sources": list(sources)[:max_results],
            "provider": row["provider"],
            "provider_diagnostics": row["diagnostics"] if isinstance(row["diagnostics"], list) else json.loads(row["diagnostics"] or "[]"),
            "fetched_at": row["fetched_at"],
        }

    async def persist_success(self, *, user_id: str, query_identity: str, normalized_query: str, category: str, provider: str, diagnostics: dict[str, Any], sources: list[dict[str, Any]], max_results: int, target_company_id: str | None = None, target_person_id: str | None = None) -> dict[str, int]:
        uid = require_user_id(user_id, context="RetrievalCacheRepository.persist_success")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                duplicate_count = 0
                for source in sources:
                    version = await conn.fetchrow(
                        """
                        insert into public.retrieval_cache_content_versions
                          (user_id, source_url, canonical_url, title, content, content_hash,
                           published_at, access_class, provider_metadata, retrieved_at)
                        values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                        on conflict (user_id, content_hash, access_class) do update
                          set retrieved_at = public.retrieval_cache_content_versions.retrieved_at
                        returning retrieval_cache_content_version_id, (xmax = 0) as inserted
                        """,
                        uid, source.get("url"), source.get("canonical_url"), source.get("title"),
                        source.get("snippet"), source.get("content_hash"), source.get("published_date"),
                        source.get("access_class") if source.get("access_class") in {"public", "tenant_private", "restricted"} else "tenant_private",
                        json.dumps({"provider": provider, "diagnostics": diagnostics}), datetime.now(timezone.utc),
                    )
                    if version is not None:
                        if not version["inserted"]:
                            duplicate_count += 1
                        await conn.execute(
                            """
                            insert into public.retrieval_cache_observations
                              (user_id, query_identity, content_version_id, provider, metadata)
                            values ($1,$2,$3,$4,$5)
                            """,
                            uid, query_identity, version["retrieval_cache_content_version_id"],
                            provider, json.dumps(diagnostics),
                        )
                await conn.execute(
                    """
                    insert into public.retrieval_cache_entries
                      (user_id, query_identity, normalized_query, category, target_company_id,
                       target_person_id, provider, status, sources, diagnostics, fetched_at, last_success_at)
                    values ($1,$2,$3,$4,$5,$6,$7,'success',$8,$9,$10,$10)
                    on conflict (user_id, query_identity) do update set
                      normalized_query=excluded.normalized_query, category=excluded.category,
                      provider=excluded.provider, status='success', sources=excluded.sources,
                      diagnostics=excluded.diagnostics, fetched_at=excluded.fetched_at,
                      last_success_at=excluded.last_success_at, updated_at=now()
                    """,
                    uid, query_identity, normalized_query, category, target_company_id, target_person_id, provider,
                    json.dumps(sources[:max_results]), json.dumps([diagnostics]), datetime.now(timezone.utc),
                )
        return {"duplicate_content_suppressed": duplicate_count, "sources_persisted": len(sources)}

    async def persist_failure(self, *, user_id: str, query_identity: str, category: str, provider: str, diagnostics: dict[str, Any], target_company_id: str | None = None, target_person_id: str | None = None) -> None:
        uid = require_user_id(user_id, context="RetrievalCacheRepository.persist_failure")
        await self.pool.execute(
            """
            insert into public.retrieval_cache_entries
              (user_id, query_identity, normalized_query, category, target_company_id, target_person_id,
               provider, status, diagnostics, fetched_at)
            values ($1,$2,'',$3,$4,$5,$6,'failure',$7,now())
            on conflict (user_id, query_identity) do update set
              provider=excluded.provider, status='failure', diagnostics=excluded.diagnostics,
              fetched_at=excluded.fetched_at, updated_at=now()
            where public.retrieval_cache_entries.status='failure'
            """,
            uid, query_identity, category, target_company_id, target_person_id, provider, json.dumps([diagnostics]),
        )
