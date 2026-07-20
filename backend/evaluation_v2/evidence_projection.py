"""Shared enriched evidence projection used by evaluation and monitoring."""

from __future__ import annotations


def enriched_claim_evidence_sql() -> str:
    """Return the single tenant-safe SQL projection for decision-bearing links."""
    return """
        select l.*, ei.verification_state, ei.source_quality,
               ei.effective_at as evidence_effective_at,
               ei.expires_at as evidence_expires_at,
               ea.trust_class, ea.untrusted_input,
               ea.prompt_injection_detected,
               ea.effective_at as artifact_effective_at,
               ea.retrieved_at
        from public.claim_evidence_links l
        join public.claims c
          on c.user_id=l.user_id and c.claim_id=l.claim_id
        join public.evidence_items ei
          on ei.user_id=l.user_id and ei.evidence_item_id=l.evidence_item_id
        join public.evidence_artifacts ea
          on ea.user_id=ei.user_id and ea.artifact_id=ei.artifact_id
        where l.user_id = $1 and c.opportunity_id = $2
        order by l.claim_id, l.evidence_item_id
    """
