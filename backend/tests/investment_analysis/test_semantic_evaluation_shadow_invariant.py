"""Proves the one invariant semantic_evaluation exists to guarantee: while
SHADOW, nothing it produces can change the authoritative analyze() output.

Runs analyze() twice, identical in every respect except the semantic
evaluator's answer is forced to opposite extremes (probability 0.00 vs 1.00
on 'supports'). If SHADOW is honoured, the Partner decision and
recommendation must be byte-identical both times. The test also asserts two
distinct records were actually persisted with different confidence values —
so it cannot pass vacuously because the shadow call never fired.
"""
import os

import pytest

from evaluation_v2.service import snapshot_claims
from investment_analysis.models import PartnerDraft, ReviewerDraft
from investment_analysis.service import analyze
from pipeline_contracts.models import Identity, Lineage, ReasoningType, References
from semantic_evaluation.models import ChoiceProbability, SemanticEvaluationStatus
from semantic_evaluation.providers.mock import MockSemanticEvaluationProvider
from semantic_evaluation.service import wait_for_pending_shadow_evaluations
from tests.evaluation_v2.test_phase0_golden_pipeline import CLOCK, _inputs
from tests.evaluation_v2.test_phase0_provenance_e2e import _policy


class _FakeRepository:
    def __init__(self):
        self.records = []

    async def record(self, entry):
        self.records.append(entry)


def _reviewer_draft_with_claim_support_reasoning(case: str) -> ReviewerDraft:
    """A ReviewerDraft whose first assessment cites a real claim from the
    fixture snapshot, so _shadow_claim_support_input finds something to ask
    about — this is what makes the test non-vacuous."""
    return ReviewerDraft(
        overall_assessment="Strong, verified evidence across all dimensions.",
        assessments=[{
            "dimension": "MARKET",
            "conclusion": "Large, well-evidenced market.",
            "proposed_score": 8,
            "score_rationale": "Independently verified market sizing.",
            "confidence": 0.9,
            "reasoning": [{
                "type": ReasoningType.FACT,
                "text": "The verified source confirms market size and growth.",
                "references": References(claim_ids=[f"{case}-market"]),
            }],
        }],
    )


async def _run_with_provider(monkeypatch, provider: MockSemanticEvaluationProvider, repository: _FakeRepository):
    monkeypatch.setenv("SEMANTIC_EVALUATION_ENABLED", "true")
    monkeypatch.setenv("SEMANTIC_EVALUATION_ROLLOUT_MODE", "shadow")
    case = "A_strong_verified"
    claims, links, _ = _inputs(case)
    snapshot, _ = snapshot_claims(claims, links, evaluation_at=CLOCK)

    async def generate(stage, prompt, payload, schema):
        if stage == "reviewer":
            return _reviewer_draft_with_claim_support_reasoning(case)
        return PartnerDraft(action="ADVANCE", confidence=0.85,
                            investment_case="Strong verified fundamentals across every dimension.",
                            rationale=["Every scored dimension is independently verified."],
                            assessment_ids=["A1"])

    result = await analyze(
        user_id="fund-a", lineage=Lineage(user_id="fund-a"), identity=Identity(name="Acme"),
        snapshot=snapshot, policy=_policy(), context={}, generate=generate, evaluation_at=CLOCK,
        semantic_evaluation_repository=repository, semantic_evaluation_provider=provider,
    )
    await wait_for_pending_shadow_evaluations()  # make the fire-and-forget dispatch deterministic for this test
    return result


@pytest.mark.asyncio
async def test_shadow_semantic_evaluation_cannot_change_authoritative_partner_decision(monkeypatch):
    repo_low = _FakeRepository()
    provider_low = MockSemanticEvaluationProvider(
        distribution=[ChoiceProbability(label="supports", probability=0.00),
                     ChoiceProbability(label="contradicts", probability=1.00)],
        selected_answer="contradicts", confidence=0.00,
    )
    result_low = await _run_with_provider(monkeypatch, provider_low, repo_low)

    repo_high = _FakeRepository()
    provider_high = MockSemanticEvaluationProvider(
        distribution=[ChoiceProbability(label="supports", probability=1.00),
                     ChoiceProbability(label="contradicts", probability=0.00)],
        selected_answer="supports", confidence=1.00,
    )
    result_high = await _run_with_provider(monkeypatch, provider_high, repo_high)

    # The invariant: identical authoritative output regardless of the shadow
    # evaluator's answer.
    assert result_low.partner.operational_action == result_high.partner.operational_action
    assert result_low.partner.judgment.action == result_high.partner.judgment.action
    assert result_low.partner.constraints == result_high.partner.constraints
    assert result_low.evaluation.recommendation.state == result_high.evaluation.recommendation.state
    assert result_low.evaluation.recommendation.confidence == result_high.evaluation.recommendation.confidence
    assert [item.score for item in result_low.evaluation.criteria] == [item.score for item in result_high.evaluation.criteria]
    assert result_low.review_reused == result_high.review_reused

    # Non-vacuous: the shadow call genuinely ran, twice, with genuinely
    # different results persisted.
    assert len(repo_low.records) == 1
    assert len(repo_high.records) == 1
    assert repo_low.records[0].status == SemanticEvaluationStatus.SUCCESS
    assert repo_high.records[0].status == SemanticEvaluationStatus.SUCCESS
    assert repo_low.records[0].selected_answer == "contradicts"
    assert repo_high.records[0].selected_answer == "supports"
    assert repo_low.records[0].confidence == 0.00
    assert repo_high.records[0].confidence == 1.00
    assert repo_low.records[0].rollout_mode.value == "shadow"


@pytest.mark.asyncio
async def test_shadow_semantic_evaluation_disabled_is_also_a_no_op(monkeypatch):
    """The invariant must hold in the default (disabled) state too — the
    absence of the flag is not itself the safety mechanism."""
    monkeypatch.setenv("SEMANTIC_EVALUATION_ENABLED", "false")
    case = "A_strong_verified"
    claims, links, _ = _inputs(case)
    snapshot, _ = snapshot_claims(claims, links, evaluation_at=CLOCK)
    repo = _FakeRepository()

    async def generate(stage, prompt, payload, schema):
        if stage == "reviewer":
            return _reviewer_draft_with_claim_support_reasoning(case)
        return PartnerDraft(action="ADVANCE", confidence=0.85,
                            investment_case="Strong verified fundamentals.",
                            rationale=["Verified."], assessment_ids=["A1"])

    result = await analyze(
        user_id="fund-a", lineage=Lineage(user_id="fund-a"), identity=Identity(name="Acme"),
        snapshot=snapshot, policy=_policy(), context={}, generate=generate, evaluation_at=CLOCK,
        semantic_evaluation_repository=repo,
    )
    await wait_for_pending_shadow_evaluations()
    assert result.partner.operational_action is not None  # analyze() completed normally
    assert repo.records == []  # disabled: nothing persisted, exactly as documented
