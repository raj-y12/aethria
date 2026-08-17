"""Bounded evidence retrieval (spec §9.4). Executes a plan's search_questions
against the same provider chain Scout already uses, and stores what's found
as canonical evidence artifacts/items -- not claims. Turning artifacts into
typed claims is Phase C's job (evidence/extraction.py, not yet built).
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any

from evidence.models import (
    AccessClass,
    ArtifactType,
    EvidenceArtifactInput,
    EvidenceItemInput,
    EvidencePlanRecord,
    TrustClass,
    VerificationState,
)
from evidence.service import detect_prompt_injection
from utils.retrieval_grounding import retrieve_source_pack_merged

# Bounds this to roughly the spec's ~12s interactive retrieval budget
# (§9.13) -- matches how Scout's own retrieval is already count-bounded
# rather than dollar-gated (CostController doesn't cover search spend).
MAX_QUERIES = 3


async def execute_evidence_plan(
    *,
    user_id: str,
    company_id: str,
    opportunity_id: str,
    plan: EvidencePlanRecord,
    evidence_repository: Any,
    company_name: str,
) -> dict[str, int]:
    queries = [f"{company_name} {q}".strip() for q in plan.search_questions[:MAX_QUERIES]]
    if not queries:
        return {"artifacts_ingested": 0, "queries_run": 0}

    pack = await asyncio.to_thread(
        retrieve_source_pack_merged,
        queries=queries,
        user_id=user_id,
        max_per_query=4,
        max_total_sources=plan.max_artifacts,
    )
    provider = str(pack.get("provider") or "")
    sources = pack.get("sources") or []

    ingested = 0
    for source in sources:
        content = str(source.get("snippet") or "").strip()
        if not content:
            continue
        await evidence_repository.ingest_artifact(
            EvidenceArtifactInput(
                user_id=user_id,
                company_id=company_id,
                opportunity_id=opportunity_id,
                artifact_type=ArtifactType.WEB_PAGE,
                source_uri=source.get("url"),
                title=source.get("title"),
                content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                trust_class=TrustClass.UNKNOWN,
                access_class=AccessClass.PUBLIC,
                untrusted_input=True,
                prompt_injection_detected=detect_prompt_injection(content),
                retrieval_provider=provider,
                retrieval_query=queries[0],
            ),
            items=[
                EvidenceItemInput(
                    user_id=user_id,
                    item_type="retrieval_excerpt",
                    normalized_value={},
                    display_excerpt=content[:2000],
                    source_locator=source.get("url"),
                    verification_state=VerificationState.UNVERIFIED,
                )
            ],
        )
        ingested += 1

    return {"artifacts_ingested": ingested, "queries_run": len(queries)}
