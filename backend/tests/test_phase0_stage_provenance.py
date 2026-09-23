"""Freeze stage provenance without changing the current Partner output."""
from copy import deepcopy
from uuid import UUID

import pytest

from agent_trace import build_partner_trace, build_review_trace, build_scout_trace, merge_stage_trace


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
