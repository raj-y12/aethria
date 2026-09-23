"""Prompt previews use frozen evidence and the current validated Reviewer contract.

Retires persona verdict/temporary SYSTEM_PROMPT tests: the preview no longer
constructs a legacy engine or mutates any live prompt.
"""
from copy import deepcopy
from unittest.mock import AsyncMock, Mock

import pytest

from meta.evaluator import evaluation_passes, run_prompt_evaluation
from investment_analysis.models import ReviewerDraft
from investment_analysis.model_gateway import AnalysisBlocked
from fastapi import HTTPException
from routers.meta import _promote_prompt_sync
from evaluation_v2.service import snapshot_claims
from tests.evaluation_v2.historical_fixtures import _inputs, CLOCK
from tests.evaluation_v2.test_phase0_provenance_e2e import _policy
from tests.investment_analysis.fixtures import analysis_for_snapshot


def test_evaluation_passes():
    assert evaluation_passes(regression_count=0, mean_abs_delta=1, n_compared=3) == (True, "ok")
    assert evaluation_passes(regression_count=1, mean_abs_delta=0, n_compared=3) == (False, "support_regression")
    assert evaluation_passes(regression_count=0, mean_abs_delta=0, n_compared=0) == (False, "no_comparisons")
    assert evaluation_passes(regression_count=0, mean_abs_delta=9, n_compared=3) == (False, "mean_delta_exceeded")


def test_legacy_reviewer_promotion_fails_before_prompt_state_is_read(monkeypatch):
    import routers.meta as routes
    read = Mock(side_effect=AssertionError("legacy prompt state must not change"))
    monkeypatch.setattr(routes, "load_prompt_library", read)
    with pytest.raises(HTTPException) as error:
        _promote_prompt_sync("tenant", "DefaultReviewer", "DefaultReviewer:abc")
    assert error.value.status_code == 409
    read.assert_not_called()


async def baseline():
    claims, links, _ = _inputs("A_strong_verified")
    snapshot, _ = snapshot_claims(claims, links, evaluation_at=CLOCK)
    analysis = await analysis_for_snapshot(snapshot=snapshot, policy=_policy(), user_id="tenant",
        opportunity_id="opportunity", evaluation_at=CLOCK)
    return {"evaluation": {"judgment_audit": {"investment_analysis": analysis.model_dump(mode="json")},
        "claim_snapshot": snapshot, "created_at": CLOCK, "evaluation_id": "frozen-evaluation"}}


@pytest.fixture
def library(monkeypatch):
    import meta.evaluator as module
    monkeypatch.setattr(module, "load_prompt_library", lambda uid: {"DefaultReviewer:abc": {"prompt": "candidate"}})
    save = Mock()
    monkeypatch.setattr(module, "save_last_eval_for_library_key", save)
    return save


def candidate(score=8, supported=True):
    async def generate(stage, prompt, payload, schema):
        assert stage == "reviewer"  # A preview never invokes Partner or publishes.
        assert prompt == "candidate"
        assert schema is ReviewerDraft
        assert "prior_decision" not in payload["fund_context"]
        assert "criterion_score" not in str(payload["factual_evidence"])
        return ReviewerDraft(overall_assessment="Candidate analysis", assessments=[{
            "dimension": rule["dimension"], "conclusion": "Supported case", "proposed_score": score,
            "score_rationale": "Evidence supports this", "confidence": .9,
            "reasoning": [{"type": "INFERENCE", "text": "Supported evidence", "references": {
                "claim_ids": [claim["claim_id"] for claim in payload["factual_evidence"]
                              if claim["claim_type"] == ({"TECHNOLOGY": "technical"}.get(rule["dimension"], rule["dimension"].lower()))] if supported else []}}],
        } for rule in payload["rubric"]["criteria"]])
    return generate


async def run(record, generate, **kwargs):
    return await run_prompt_evaluation(user_id="tenant", agent_target="DefaultReviewer",
        library_key="DefaultReviewer:abc", load_baseline=AsyncMock(return_value=record),
        policy=_policy(), generate=generate, startup_ids=["startup"], **kwargs)


@pytest.mark.asyncio
async def test_preview_frozen_baseline_support_and_score_comparison(library):
    record = await baseline()
    before = deepcopy(record)
    result = await run(record, candidate())
    assert result["rows"][0]["baseline_evaluation_id"] == "frozen-evaluation"
    assert record == before
    assert result["summary"]["passed"]
    assert result["rows"][0]["mean_abs_delta"] == 0
    library.assert_called_once()


@pytest.mark.asyncio
async def test_lost_evidence_support_fails_even_without_score_pairs(library):
    result = await run(await baseline(), candidate(supported=False))
    assert not result["summary"]["passed"]
    assert result["summary"]["regression_count"] == 1
    assert result["rows"][0]["lost_support_dimensions"]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["foreign", "changed_policy", "historical", "missing", "budget"])
async def test_ineligible_or_failed_rows_cannot_pass(library, kind):
    record = await baseline()
    generate = AsyncMock(side_effect=AnalysisBlocked("analysis_budget_blocked", "Budget"))
    if kind == "foreign":
        record["evaluation"]["judgment_audit"]["investment_analysis"]["reviewer"]["lineage"]["user_id"] = "other"
    elif kind == "changed_policy":
        record["evaluation"]["judgment_audit"]["investment_analysis"]["reviewer"]["policy_versions"]["policy_hash"] = "old"
    elif kind == "historical":
        record["evaluation"]["judgment_audit"] = {}
    elif kind == "missing":
        record = None
    result = await run(record, generate)
    assert not result["summary"]["passed"]
    if kind != "budget":
        generate.assert_not_called()
    assert library.call_args.kwargs["passed"] is False


@pytest.mark.asyncio
async def test_library_target_binding_rejected_before_model_or_read(library):
    read, generate = AsyncMock(), AsyncMock()
    result = await run_prompt_evaluation(user_id="tenant", agent_target="SkepticalReviewer",
        library_key="DefaultReviewer:abc", load_baseline=read, generate=generate, policy=_policy(), startup_ids=["startup"])
    assert not result["ok"]
    read.assert_not_called()
    generate.assert_not_called()
    library.assert_not_called()
