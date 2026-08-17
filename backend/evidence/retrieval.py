"""Bounded evidence retrieval (spec §9.4). Executes a plan's search_questions
against the same provider chain Scout already uses, and stores what's found
as canonical evidence artifacts/items -- not claims. Turning artifacts into
typed claims is Phase C's job (evidence/extraction.py, not yet built).
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any, Optional
from urllib.parse import urlparse

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


def _domain(url: Optional[str]) -> str:
    if not url:
        return ""
    text = url.strip()
    # A bare "stripe.com" (no scheme -- how ScoutInfo.lookup_website is
    # stored) parses as an empty netloc, not a host: urlparse("stripe.com")
    # treats it as a relative path. A retrieved source URL always has a
    # scheme already, so this only ever adds one where it was missing.
    if "://" not in text:
        text = f"https://{text}"
    netloc = urlparse(text).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


async def execute_evidence_plan(
    *,
    user_id: str,
    company_id: str,
    opportunity_id: str,
    plan: EvidencePlanRecord,
    evidence_repository: Any,
    company_name: str,
    company_website: Optional[str] = None,
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

    # Deterministic trust/verification (spec §9.6 is otherwise entirely
    # unbuilt -- nothing else in the codebase ever marks retrieved evidence
    # VERIFIED). The active policy blocks trust_class="unknown" outright and
    # requires verification_state="verified" for a claim to ever score
    # (decision_safety.evidence_eligibility, resources/config/partner_rules).
    # Two auditable rules, no model judgment involved:
    #   - the company's own domain is TrustClass.OFFICIAL and verified
    #     unconditionally (first-party statements about itself);
    #   - anything else is TrustClass.INDEPENDENT (retrieved, third-party,
    #     never "unknown" -- it has a real URL/domain); verified only when
    #     corroborated by >=2 distinct non-official domains in this same
    #     retrieval pass. A single uncorroborated source stays unverified --
    #     correctly conservative, not a claim-blocking regression.
    official_domain = _domain(company_website)
    domains = [_domain(s.get("url")) for s in sources]
    independent_domains = {d for d in domains if d and d != official_domain}
    corroborated = len(independent_domains) >= 2

    ingested = 0
    for source, domain in zip(sources, domains):
        content = str(source.get("snippet") or "").strip()
        if not content:
            continue
        is_official = bool(domain) and domain == official_domain
        trust_class = TrustClass.OFFICIAL if is_official else TrustClass.INDEPENDENT
        verification_state = (
            VerificationState.VERIFIED
            if is_official or corroborated
            else VerificationState.UNVERIFIED
        )
        await evidence_repository.ingest_artifact(
            EvidenceArtifactInput(
                user_id=user_id,
                company_id=company_id,
                opportunity_id=opportunity_id,
                artifact_type=ArtifactType.WEB_PAGE,
                source_uri=source.get("url"),
                title=source.get("title"),
                content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                trust_class=trust_class,
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
                    verification_state=verification_state,
                )
            ],
        )
        ingested += 1

    return {"artifacts_ingested": ingested, "queries_run": len(queries)}
