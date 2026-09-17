"""Shared context-enrichment services consumed by Scout, Reviewer, and Partner.

These modules assemble grounded, cited context (founder identity, regulatory
posture, commercial/competitive claims, contradiction detection) for whichever
review implementation is active — the legacy persona engines
(`backend/reviewer/`, `backend/partner/`) and the current shared evidence-first
implementation (`backend/investment_analysis/`) both consume them, as does
`pipeline_runner.py` and `opportunity_pipeline.py`. That is why this lives as
its own package rather than nested inside any one agent.

External code should import from `context` directly
(`from context import build_founder_context`); the submodule split below is an
internal detail.

- assembler: `ContextAssembler` / `CanonicalContextProvider` — the shared
  contract each context provider below attaches its contribution through.
- founder: founder identity resolution + grounding guard for Reviewer.
- regulatory: regulatory-context assembly, claims, and grounding guard.
- commercial_knowledge / competition_knowledge: claim derivation feeding
  scout_claims.
- scout_claims: canonical scout-claim derivation and persistence (bridges
  Scout's factual output into the canonical evidence layer).
- contradiction_gate: cross-checks Reviewer/Partner output against evidence.
- conviction_state: conviction-patch computation for the API read path.
- scout_field_gaps / scout_post_review_enrichment: post-review backfill of
  weak Scout fields (TAM, funding stage). Lives here rather than in
  `scout/tools/` because the storage layer (`legacy_supabase/storage.py`,
  `startups/repository.py`) calls it directly when persisting a completed
  review — it is not Scout's own private reasoning.
"""
from __future__ import annotations

from context.assembler import CanonicalContextProvider, ContextAssembler, add_context_contract
from context.commercial_knowledge import derive_commercial_claims
from context.competition_knowledge import derive_competition_claims
from context.contradiction_gate import apply_contradiction_gate
from context.conviction_state import build_conviction_patch
from context.founder import apply_founder_grounding_guard, build_founder_context, resolved_founder_names
from context.scout_field_gaps import is_missing_tam, is_weak_funding_stage
from context.scout_post_review_enrichment import (
    infer_funding_stage_from_review_text_enabled,
    infer_funding_stage_from_text,
    merge_scout_info_enrichment,
)
from context.regulatory import (
    CanonicalReviewerRegulatoryContextProvider,
    apply_regulatory_grounding_guard,
    assemble_regulatory_context,
    build_reviewer_regulatory_context,
    deduplicate_references,
    derive_regulatory_claims,
)
from context.scout_claims import derive_scout_claims, persist_scout_claims

__all__ = [
    "CanonicalContextProvider",
    "CanonicalReviewerRegulatoryContextProvider",
    "ContextAssembler",
    "add_context_contract",
    "apply_contradiction_gate",
    "apply_founder_grounding_guard",
    "apply_regulatory_grounding_guard",
    "assemble_regulatory_context",
    "build_conviction_patch",
    "build_founder_context",
    "build_reviewer_regulatory_context",
    "deduplicate_references",
    "derive_commercial_claims",
    "derive_competition_claims",
    "derive_regulatory_claims",
    "derive_scout_claims",
    "infer_funding_stage_from_review_text_enabled",
    "infer_funding_stage_from_text",
    "is_missing_tam",
    "is_weak_funding_stage",
    "merge_scout_info_enrichment",
    "persist_scout_claims",
    "resolved_founder_names",
]
