"""Retain verified source quotations without asking an extractor to score them.

The claim establishes what a source says. Reviewer must assess the reliability
and investment meaning of that statement. Original items/artifacts remain the
authority for content and verification; callers supply IDs only.
"""
from evidence.models import AssertionClass, ClaimInput, ClaimEvidenceLinkInput, EvidenceRelationship
from evidence.service import EvidenceStandardError, validate_claim_standard
from tenant_context import require_user_id


async def retain_verified_source_statements(*, user_id: str, company_id: str, opportunity_id: str,
                                            evidence_item_ids: list[str], evidence_repository) -> dict[str, int]:
    uid = require_user_id(user_id, context="retain_verified_source_statements")
    if not evidence_item_ids:
        return {"claims_created": 0}
    ledger = await evidence_repository.get_ledger(user_id=uid, opportunity_id=opportunity_id)
    items = {str(item["evidence_item_id"]): item for item in ledger["evidence_items"]}
    artifacts = {str(item["artifact_id"]): item for item in ledger["artifacts"]}
    selected = []
    # Validate the entire supplied set before any writes.
    for item_id in sorted(set(evidence_item_ids)):
        item = items.get(item_id)
        artifact = artifacts.get(str((item or {}).get("artifact_id")))
        if (item is None or artifact is None or item.get("user_id") != uid
                or artifact.get("user_id") != uid or str(artifact.get("company_id")) != company_id
                or str(artifact.get("opportunity_id")) != opportunity_id):
            raise ValueError("Source evidence is outside the requested tenant/company/opportunity scope")
        selected.append((item_id, item, artifact))
    # A withdrawn source statement remains in history and must never be
    # recreated from the same item during a later re-review.
    recorded_statements = {str(claim["claim_id"]) for claim in ledger["claims"]
                           if claim.get("claim_type") == "source_statement"}
    linked = {str(link["evidence_item_id"]) for link in ledger["claim_evidence_links"]
              if str(link["claim_id"]) in recorded_statements}
    created = 0
    for item_id, item, artifact in selected:
        text = str(item.get("display_excerpt") or "").strip()
        if (item_id in linked or not text or item.get("verification_state") != "verified"
                or artifact.get("prompt_injection_detected")):
            continue
        claim = ClaimInput(
            user_id=uid, company_id=company_id, opportunity_id=opportunity_id,
            claim_type="source_statement", normalized_value={"statement_kind": "attributed_source_excerpt"},
            display_text=text, assertion_class=AssertionClass.EXTERNALLY_VERIFIED,
            # Exact copying is certain; source reliability remains independent
            # in the item/link and is constrained by evidence validation.
            confidence=1.0, material=True,
        )
        try:
            validate_claim_standard(claim, evidence_link_count=1)
        except EvidenceStandardError:
            # Keep the original artifact available without promoting prohibited
            # subjective founder labels into material factual claims.
            continue
        await evidence_repository.create_claim(claim, links=[ClaimEvidenceLinkInput(
            user_id=uid, evidence_item_id=item_id, relationship=EvidenceRelationship.SUPPORTS,
            support_strength=float(item.get("source_quality") or 0),
            rationale="The linked source contains this exact attributed statement; investment interpretation belongs to Reviewer.",
        )], created_by=uid)
        created += 1
    return {"claims_created": created}
