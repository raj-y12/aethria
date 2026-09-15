"""Freeze stage provenance without changing the current Partner output."""
from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID

import pytest

from agent_trace import build_partner_trace, build_review_trace, build_scout_trace, merge_stage_trace
from models import PartnerInfo
from partner.engine import PartnerEngine


def test_new_stage_ids_are_distinct_and_existing_trace_is_preserved():
    scout = build_scout_trace({}, pipeline_run_id="pipeline-1")
    reviewer = build_review_trace({}, scout={}, pipeline_run_id="pipeline-1")
    partner = build_partner_trace({}, scout={}, review={}, pipeline_run_id="pipeline-1")
    identifiers = [scout["scout_run_id"], reviewer["reviewer_run_id"], partner["partner_run_id"]]
    assert len(set(identifiers)) == 3
    for identifier in identifiers:
        assert UUID(identifier).version == 4
        assert identifier != "pipeline-1"
    existing = {"scout": scout, "reviewer": reviewer}
    frozen = deepcopy(existing)
    merged = merge_stage_trace(existing, "partner", partner)
    assert existing == frozen
    assert merged["scout"] == scout
    assert merged["reviewer"] == reviewer
    # A later run reuses historical stages without fabricating their missing IDs.
    assert "scout_run_id" not in merge_stage_trace({"scout": {"status": "completed"}}, "partner", partner)["scout"]


def test_trace_records_only_available_prompt_score_and_model_provenance():
    review = {"market_score": 6.0, "reviews": [{"prompt_version": "prompt-a"}, {}]}
    frozen = deepcopy(review)
    trace = build_review_trace(review, scout={}, pipeline_run_id="pipeline-1")
    assert review == frozen
    assert trace["legacy_scores"]["market_score"] == 6.0
    assert trace["legacy_scores"]["product_score"] is None
    assert trace["score_origin"] == "UNKNOWN_LEGACY"
    assert trace["reviewer_prompt_versions"] == ["prompt-a", None]
    assert trace["reviewer_model"] is None
    assert trace["reviewer_prompt_version"] is None
    assert trace["policy_hash"] is None
    scout = build_scout_trace({"prompt_version": "scout-prompt"}, pipeline_run_id=None)
    assert scout["scout_prompt_version"] == "scout-prompt"
    assert scout["scout_model"] is None
    partner = build_partner_trace({"recommendation": "INVEST"}, scout={}, review={}, pipeline_run_id=None)
    assert partner["provenance"] is None
    assert partner["recommendation_origin"] == "UNKNOWN_LEGACY"


@pytest.mark.asyncio
@pytest.mark.parametrize("canonical_state,missing,expected", [("advance", False, "INVEST"), ("advance", True, "MONITOR"), ("insufficient_evidence", True, "MONITOR"), (None, True, "MONITOR")])
async def test_persisted_partner_provenance_keeps_current_decision(canonical_state, missing, expected, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    saved = []

    def save(startup_id, info, **kwargs):
        saved.append(info)
        return True

    storage = SimpleNamespace(_user_id="tenant-a", add_partner_decision=save)
    engine = PartnerEngine(storage=storage, tenant_user_id="tenant-a", use_llm_fallback=False)
    engine._supabase_client_uid = lambda: (None, "tenant-a")
    scout = {"name": "TraceCo", "one_line": "Workflow software", "sector": "SaaS", "why_now": "New workflow demand"}
    review = {"key_risks": [], "market_score": 1.0, "thesis_alignment_score": 0.9}
    criteria = [{"criterion": "market", "score": None if missing else 6.0, "evidence_sufficiency": "insufficient" if missing else "sufficient"}]
    frozen_inputs = deepcopy((scout, review, criteria))
    baseline, _ = engine.decision_engine.decide_with_execution_identity(
        scout, review, fund_thesis=engine.fund_thesis, canonical_recommendation=canonical_state,
        canonical_criteria=criteria, canonical_confidence=0.83,
    )
    success, decision = await engine._decide_and_save(
        "startup-1", scout, review, "pipeline-1", canonical_recommendation=canonical_state,
        canonical_criteria=criteria, canonical_confidence=0.83,
    )
    assert success
    assert (scout, review, criteria) == frozen_inputs
    assert decision["recommendation"] == baseline["recommendation"] == expected
    assert decision["confidence"] == baseline["confidence"]
    assert decision["company_quality"] == baseline["company_quality"] is None
    assert "provenance" not in decision  # It never enters the output/model contract.
    persisted = PartnerInfo.model_validate(saved[0].model_dump(mode="json"))
    provenance = persisted.provenance
    assert provenance.canonical_scores == {"market": None if missing else 6.0}
    assert provenance.canonical_confidence == 0.83
    assert provenance.partner_model is None
    assert provenance.partner_rules_version
    assert provenance.partner_recommendation == expected
    assert provenance.original_recommendation_origin == ("CANONICAL_EVALUATION" if canonical_state else "UNKNOWN_LEGACY")
    assert provenance.policy_changed_recommendation == (missing if canonical_state == "advance" else None)
    assert provenance.guard_changed_recommendation is False
    assert provenance.validation_changed_recommendation is False
    trace = build_partner_trace(persisted, scout=scout, review=review, pipeline_run_id="pipeline-1")
    assert trace["provenance"] == provenance.model_dump(mode="json")


def test_api_preserves_legacy_audit_values_without_restoring_analyst_scores():
    from api import _backend_to_frontend
    raw = {
        "startup_id": "startup-1", "scout_info": {"name": "TraceCo"},
        "review_info": {"market_score": 9.0, "overall_score": 9.0, "verdict": "STRONG"},
    }
    before = deepcopy(raw)
    projected = _backend_to_frontend(raw)
    assert projected["review"]["market_score"] is None
    assert projected["review"]["overall_score"] is None
    assert projected["projection_provenance"]["legacy_scores"]["market_score"] == 9.0
    assert projected["projection_provenance"]["legacy_score_origin"] == "UNKNOWN_LEGACY"
    assert projected["projection_provenance"]["canonical_evaluation_id"] is None
    assert raw == before


def test_reviewer_trace_links_only_claims_actually_supplied_in_canonical_context():
    review = {"canonical_context_snapshot": {"contexts": {
        "market": {"claims": [{"claim_id": "claim-1"}]},
        "technical": {"current_supported_claims": [{"claim_id": "claim-2"}, {"claim_id": "claim-1"}]},
    }}}
    trace = build_review_trace(review, scout={}, pipeline_run_id="run-a")
    assert trace["canonical_context_claim_ids"] == ["claim-1", "claim-2"]
