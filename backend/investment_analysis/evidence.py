"""Shared bounded factual preparation; no investment scoring or model calls."""
from datetime import datetime

from evidence.factual import retain_verified_source_statements
from evidence.planning import compute_missing_evidence
from evidence.retrieval import execute_evidence_plan, MAX_QUERIES
from evaluation_v2.models import EvaluationPolicy
from evaluation_v2.service import evaluate_claim_score_eligibility
from tenant_context import require_user_id


async def prepare_factual_evidence(*, user_id: str, company_id: str, opportunity_id: str,
                                   company_name: str, company_website: str | None,
                                   snapshot: list[dict], policy: EvaluationPolicy, evaluation_at: datetime,
                                   evidence_repository, questions: list[str] | None = None) -> dict:
    uid = require_user_id(user_id, context="prepare_factual_evidence")
    if any(claim.get("user_id") not in (None, uid) for claim in snapshot):
        raise ValueError("Evidence preparation snapshot tenant mismatch")
    # Let Reviewer first inspect usable existing evidence. Additional research
    # should answer a material question, not blindly repeat every dimension.
    if not questions and any(evaluate_claim_score_eligibility(claim, policy=policy, evaluation_at=evaluation_at).eligible
                             for claim in snapshot):
        return {"status": "reused", "claims_created": 0}
    ledger = await evidence_repository.get_ledger(user_id=uid, opportunity_id=opportunity_id)
    existing_ids = [str(item["evidence_item_id"]) for item in ledger["evidence_items"]
                    if item.get("verification_state") == "verified" and item.get("display_excerpt")]
    if existing_ids:
        retained = await retain_verified_source_statements(
            user_id=uid, company_id=company_id, opportunity_id=opportunity_id,
            evidence_item_ids=existing_ids, evidence_repository=evidence_repository,
        )
        if retained["claims_created"] and not questions:
            return {"status": "retained_existing", **retained}
    else:
        retained = {"claims_created": 0}
    dimensions, default_questions = compute_missing_evidence(policy, set())
    selected_questions = list(dict.fromkeys(question.strip() for question in (questions or default_questions) if question.strip()))[:MAX_QUERIES]
    plan = await evidence_repository.create_plan(
        user_id=uid, opportunity_id=opportunity_id, trigger_type="investment_analysis",
        missing_evidence=dimensions, search_questions=selected_questions,
    )
    retrieved = await execute_evidence_plan(
        user_id=uid, company_id=company_id, opportunity_id=opportunity_id,
        company_name=company_name, company_website=company_website,
        plan=plan, evidence_repository=evidence_repository,
    )
    result = await retain_verified_source_statements(
        user_id=uid, company_id=company_id, opportunity_id=opportunity_id,
        evidence_item_ids=[str(item["evidence_item_id"]) for item in retrieved.get("verified_items") or []],
        evidence_repository=evidence_repository,
    )
    return {"status": "retrieved", "claims_created": retained["claims_created"] + result["claims_created"]}
