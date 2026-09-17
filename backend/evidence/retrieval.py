"""Bounded evidence retrieval (spec §9.4). Executes a plan's search_questions
against the same provider chain Scout already uses, and stores what's found
as canonical evidence artifacts/items -- not claims. Turning artifacts into
typed claims is Phase C's job (evidence/extraction.py, not yet built).
"""

from __future__ import annotations

import asyncio
import hashlib
import re
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
from research.retrieval_grounding import retrieve_source_pack_merged
from utils.text_sanitize import strip_markdown_links

# Fixed 2026-08-17 (audit CRITICAL-2): this used to be 3, silently capping
# plan.search_questions[:3] -- but the plan has one search question *per
# missing rubric dimension*, and the rubric has exactly 5 dimensions
# (market/product/technical/execution/defensibility). Capping below that
# guaranteed dimensions past the third got zero targeted retrieval, ever,
# regardless of how many were actually missing -- a likely direct cause of
# the low canonical-coverage numbers observed after the first backfill.
# 5 still bounds worst-case query volume (one query per dimension, never
# more, since compute_missing_evidence never emits more than 5 questions);
# it isn't an unbounded change, just wide enough to guarantee coverage.
MAX_QUERIES = 5


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


# Per-query source cap (audit HIGH-B4 fix below runs one retrieval call per
# query instead of one batched call across all of them -- this bounds each
# call's own contribution so total worst-case volume across MAX_QUERIES
# queries stays reasonable).
_MAX_SOURCES_PER_QUERY = 4


def analytical_excerpt(content: str, *, limit: int = 2000) -> str:
    """Keep analytical signal when a scrape leads with boilerplate consent text."""
    cleaned = strip_markdown_links(content)
    if len(cleaned) <= limit:
        return cleaned
    marker = re.compile(r"trusted by|customers?|case stud(?:y|ies)|testimonial|logos?|used by", re.IGNORECASE)
    windows = [cleaned[:420]]
    for match in marker.finditer(cleaned):
        windows.append(cleaned[max(0, match.start() - 100):match.end() + 320])
    windows.append(cleaned[-420:])
    result = "\n...\n".join(dict.fromkeys(windows))
    if len(result) <= limit:
        return result
    tail = cleaned[-420:]
    return result[:max(1, limit - len(tail) - 9)] + "\n...\n" + tail


async def execute_evidence_plan(
    *,
    user_id: str,
    company_id: str,
    opportunity_id: str,
    plan: EvidencePlanRecord,
    evidence_repository: Any,
    company_name: str,
    company_website: Optional[str] = None,
) -> dict[str, Any]:
    queries = [f"{company_name} {q}".strip() for q in plan.search_questions[:MAX_QUERIES]]
    if not queries:
        return {"artifacts_ingested": 0, "queries_run": 0, "verified_items": []}

    # Fixed 2026-08-17 (audit HIGH-B4): corroboration used to be computed once
    # across every source from every query pooled into a single batched
    # retrieval call -- so two sources on completely unrelated facts (a
    # funding page from the market query, an unrelated blog from the
    # execution query) could satisfy ">= 2 distinct domains" and mark
    # *everything* in the pass verified, including a single-source claim
    # about a different fact nothing actually corroborates. Each query now
    # runs as its own retrieval call, and corroboration is scored only
    # within that query's own results -- sources that actually responded to
    # the same question, not whatever else happened to come back this pass.
    # Real cost tradeoff, not hidden: this is now up to len(queries) separate
    # provider calls instead of one merged call; run concurrently to bound
    # wall-clock time, not sequentially.
    packs = await asyncio.gather(
        *[
            asyncio.to_thread(
                retrieve_source_pack_merged,
                queries=[query],
                user_id=user_id,
                max_per_query=_MAX_SOURCES_PER_QUERY,
                max_total_sources=_MAX_SOURCES_PER_QUERY,
            )
            for query in queries
        ]
    )

    official_domain = _domain(company_website)
    provider = ""
    ingested = 0
    seen_urls: set[str] = set()
    # Only verified items can ever support a scored claim (the same
    # eligibility gate evaluate_claim_score_eligibility enforces later) --
    # no point spending extraction tokens on evidence that can't help.
    verified_items: list[dict[str, Any]] = []
    for query, pack in zip(queries, packs):
        provider = str(pack.get("provider") or "") or provider
        sources = pack.get("sources") or []
        if plan.trigger_type == "investment_analysis":
            from investment_analysis.grounding import relevant_source
            # Research for the live analytical core must establish company
            # relevance before unrelated domains can count as corroboration.
            sources = [source for source in sources if relevant_source(
                source, company_name=company_name, company_website=company_website)]
        # Deterministic trust/verification (spec §9.6 is otherwise entirely
        # unbuilt -- nothing else in the codebase ever marks retrieved
        # evidence VERIFIED). Two auditable rules, no model judgment
        # involved:
        #   - the company's own domain is TrustClass.OFFICIAL and verified
        #     unconditionally (first-party statements about itself);
        #   - anything else is TrustClass.INDEPENDENT; verified only when
        #     corroborated by >=2 distinct non-official domains that
        #     answered THIS query. A single uncorroborated source stays
        #     unverified -- correctly conservative, not a regression.
        domains = [_domain(s.get("url")) for s in sources]
        independent_domains = {d for d in domains if d and d != official_domain}
        corroborated = len(independent_domains) >= 2

        for source, domain in zip(sources, domains):
            url = str(source.get("url") or "")
            if url and url in seen_urls:
                continue
            content = str(source.get("snippet") or "").strip()
            if not content:
                continue
            if ingested >= plan.max_artifacts:
                # Fixed 2026-08-17 (audit HIGH-A5/B4 self-audit): the per-query
                # rewrite dropped the caller's overall max_artifacts budget --
                # it used to bound the single merged retrieval call, but
                # nothing capped the sum across the now-separate per-query
                # calls. A caller-configured budget (routers/evidence.py,
                # jobs/handlers.py) was silently exceeded (up to
                # len(queries) * _MAX_SOURCES_PER_QUERY instead). This just
                # stops ingesting once the plan's own budget is spent.
                break
            if url:
                seen_urls.add(url)
            is_official = bool(domain) and domain == official_domain
            trust_class = TrustClass.OFFICIAL if is_official else TrustClass.INDEPENDENT
            verification_state = (
                VerificationState.VERIFIED
                if is_official or corroborated
                else VerificationState.UNVERIFIED
            )
            # decision_safety.evidence_eligibility.min_source_quality gates
            # claim eligibility on this same source_quality value
            # (service.py); it defaults to 0.0 on EvidenceItemInput and was
            # never being set here, so every retrieved item was silently
            # permanently ineligible. First-party is full quality;
            # corroborated third-party sits above the eligibility floor but
            # below full_confidence_at (0.8), which correctly caps
            # confidence rather than granting it outright.
            source_quality = 1.0 if is_official else (0.6 if corroborated else 0.0)
            _artifact, items = await evidence_repository.ingest_artifact(
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
                    # Fixed alongside B4: this used to always be queries[0]
                    # regardless of which query actually found the source --
                    # now correctly attributed since each source is now
                    # processed within the one query that returned it.
                    retrieval_query=query,
                ),
                items=[
                    EvidenceItemInput(
                        user_id=user_id,
                        item_type="retrieval_excerpt",
                        normalized_value={},
                        display_excerpt=analytical_excerpt(content),
                        source_locator=source.get("url"),
                        verification_state=verification_state,
                        source_quality=source_quality,
                    )
                ],
            )
            ingested += 1
            if verification_state == VerificationState.VERIFIED and items:
                verified_items.append(
                    {
                        "evidence_item_id": str(items[0].evidence_item_id),
                        "display_excerpt": items[0].display_excerpt,
                        # Threaded through so extraction can derive a claim-evidence
                        # link's support_strength from this deterministic signal
                        # instead of reusing the model's own claim confidence
                        # (audit CRITICAL-4 -- one number was gating both).
                        "source_quality": source_quality,
                    }
                )

    return {"artifacts_ingested": ingested, "queries_run": len(queries), "verified_items": verified_items}
