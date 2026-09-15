"""Behavioral migration cases: unchanged evidence, deliberately new authority."""
from copy import deepcopy
import pytest

from evaluation_v2.service import snapshot_claims
from pipeline_contracts.models import Identity, Lineage
from investment_analysis.models import ReviewerDraft, PartnerDraft
from investment_analysis.service import analyze, factual_packet
from tests.evaluation_v2.test_phase0_golden_pipeline import _inputs, CLOCK
from tests.evaluation_v2.test_phase0_provenance_e2e import _policy
from investment_analysis.model_gateway import AnalysisBlocked


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["company_id", "opportunity_id", "user_id"])
async def test_foreign_claim_ownership_blocks_before_any_model_call(field):
    async def generate(*args):
        pytest.fail("Foreign evidence must not reach a model")
    with pytest.raises(ValueError, match="mismatch"):
        await analyze(user_id="tenant", lineage=Lineage(user_id="tenant", company_id="ads", opportunity_id="ads-opp"),
            identity=Identity(name="Glitch Ads", website="glitchads.ai"),
            snapshot=[{"claim_id": "foreign", field: "studio"}], policy=_policy(), context={},
            generate=generate, evaluation_at=CLOCK)


@pytest.mark.asyncio
async def test_both_analysts_receive_only_glitch_ads_evidence():
    from tests.investment_analysis.test_grounding import claim
    seen = []
    async def generate(stage, prompt, payload, schema):
        seen.append(stage)
        assert "Netflix" not in str(payload)
        assert "merchandise" not in str(payload)
        if stage == "reviewer":
            return ReviewerDraft(overall_assessment="Advertising startup; diligence missing.")
        assert "lineage" not in payload["review"]
        assert "policy_versions" not in payload["review"]
        return PartnerDraft(action="MORE_DILIGENCE", confidence=0.5, rationale=["Validate advertising traction"],
                            investment_case="Further diligence required")
    result = await analyze(user_id="tenant", lineage=Lineage(user_id="tenant"),
        identity=Identity(name="Glitch Ads", website="glitchads.ai"), snapshot=[
            claim("ads", text="Glitch Ads automates advertising", url="https://glitchads.ai"),
            claim("studio", text="Glitch Studios Netflix merchandise revenue", url="https://glitchstudios.co")],
        policy=_policy(), context={}, generate=generate, evaluation_at=CLOCK)
    assert seen == ["reviewer", "partner"]
    assert result.partner.operational_action == "MORE_DILIGENCE"


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_reference", ["claim", "evidence"])
async def test_downgraded_reasoning_cannot_validate_a_score(invalid_reference):
    claims, links, _ = _inputs("A_strong_verified")
    snapshot, _ = snapshot_claims(claims, links, evaluation_at=CLOCK)

    async def generate(stage, prompt, payload, schema):
        if stage == "reviewer":
            refs = {"claim_ids": [claims[0]["claim_id"]]}
            if invalid_reference == "claim":
                refs["claim_ids"].append("not-in-this-snapshot")
            else:
                refs["evidence_item_ids"] = ["not-linked-to-this-claim"]
            return ReviewerDraft(overall_assessment="Diligence is incomplete.", assessments=[{
                "dimension": "MARKET", "conclusion": "Uncertain market claim.",
                "proposed_score": 7, "confidence": 0.8, "score_rationale": "Depends on unresolved evidence.",
                "reasoning": [{"type": "INFERENCE", "text": "Unresolved reference supports this claim.",
                               "references": refs}],
            }])
        return PartnerDraft(action="MORE_DILIGENCE", rationale=["Verify evidence."], confidence=0.5,
                            investment_case="Not yet established.",
                            assessment_ids=[item["assessment_id"] for item in payload["review"]["assessments"]])

    result = await analyze(user_id="tenant", lineage=Lineage(user_id="tenant"),
                           identity=Identity(name="Synthetic"), snapshot=snapshot, policy=_policy(),
                           context={}, generate=generate, evaluation_at=CLOCK)
    assert result.reviewer.assessments[0].reasoning_units[0].type == "UNKNOWN"
    market = next(item for item in result.validation.assessments if item.dimension == "MARKET")
    assert market.validated_score is None
    assert market.support_status == "UNSUPPORTED"
    assert not market.references.claim_ids


@pytest.mark.asyncio
async def test_partner_only_refresh_reuses_completed_review_and_revalidates_support():
    prior, _ = await run_case(proposal=7, action="MONITOR")
    claims, links, _ = _inputs("A_strong_verified")
    snapshot, _ = snapshot_claims(claims, links, evaluation_at=CLOCK)
    calls = []

    async def generate(stage, prompt, payload, schema):
        calls.append(stage)
        assert payload["review"]["overall_assessment"] == prior.reviewer.overall_assessment
        return PartnerDraft(action="PASS", rationale=["Portfolio exposure has changed"],
                            assessment_ids=[item.assessment_id for item in prior.reviewer.assessments],
                            confidence=0.8, investment_case="Existing exposure limits additional upside")

    result = await analyze(
        user_id="tenant", lineage=Lineage(user_id="tenant", opportunity_id="opportunity"),
        identity=Identity(name="Synthetic"), snapshot=snapshot, policy=_policy(), context={},
        generate=generate, evaluation_at=CLOCK, prior_review=prior.reviewer, prior_snapshot=snapshot,
    )
    assert calls == ["partner"]
    assert result.review_reused is True
    assert result.reviewer.lineage.reviewer_run_id == prior.reviewer.lineage.reviewer_run_id
    assert result.partner.lineage.partner_run_id != prior.partner.lineage.partner_run_id
    assert result.validation.lineage.validation_run_id != prior.validation.lineage.validation_run_id
    assert [item.score for item in result.evaluation.criteria] == [item.score for item in prior.evaluation.criteria]
    assert result.partner.operational_action == "PASS"


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["evidence", "thesis", "tenant"])
async def test_partner_refresh_rejects_invalidated_or_foreign_review_before_model_calls(change):
    prior, _ = await run_case()
    claims, links, _ = _inputs("A_strong_verified")
    snapshot, _ = snapshot_claims(claims, links, evaluation_at=CLOCK)
    updated = deepcopy(snapshot)
    context = {}
    review = prior.reviewer
    if change == "evidence":
        updated[0]["display_text"] = "A corrected factual claim"
    elif change == "thesis":
        context["thesis_version_id"] = "new-thesis"
    else:
        review = review.model_copy(update={"lineage": review.lineage.model_copy(update={"user_id": "another-tenant"})})

    async def generate(*args):
        pytest.fail("An invalidated review must not trigger a Partner model call")

    with pytest.raises(ValueError if change == "tenant" else AnalysisBlocked):
        await analyze(user_id="tenant", lineage=Lineage(user_id="tenant", opportunity_id="opportunity"),
                      identity=Identity(name="Synthetic"), snapshot=updated, policy=_policy(), context=context,
                      generate=generate, evaluation_at=CLOCK, prior_review=review, prior_snapshot=snapshot)


async def run_case(case="A_strong_verified", *, proposal=8, action="ADVANCE", mutate=None, conclusion="Compelling investment argument", context=None):
    claims, links, _ = _inputs(case)
    if mutate:
        mutate(claims, links)
    snapshot, _ = snapshot_claims(claims, links, evaluation_at=CLOCK)
    calls = []

    async def generate(stage, prompt, payload, schema):
        calls.append((stage, payload))
        if stage == "reviewer":
            return ReviewerDraft(overall_assessment=conclusion, assessments=[{
                "dimension": {"technical": "TECHNOLOGY"}.get(claim["claim_type"], claim["claim_type"].upper()),
                "conclusion": conclusion, "proposed_score": proposal, "confidence": 0.9,
                "score_rationale": "Judgment based on material factual evidence, not its stored legacy score.",
                "reasoning": [{"type": "INFERENCE", "text": "The observed adoption supports a repeatable distribution advantage.",
                               "references": {"claim_ids": [claim["claim_id"]]}}],
                "limitations": ["Retention cohorts remain unavailable."],
            } for claim in claims])
        return PartnerDraft(action=action, rationale=[payload["review"]["overall_assessment"]],
                            assessment_ids=[item["assessment_id"] for item in payload["review"]["assessments"]],
                            confidence=0.8, investment_case="Distribution may compound", next_steps=["Verify retention cohorts."])
    result = await analyze(user_id="tenant", lineage=Lineage(user_id="tenant", opportunity_id="opportunity"),
                           identity=Identity(name="Synthetic"), snapshot=snapshot, policy=_policy(),
                           context=context or {"fund_thesis": "B2B infrastructure"}, generate=generate, evaluation_at=CLOCK)
    return result, calls


@pytest.mark.asyncio
async def test_retired_decision_bands_are_audited_but_cannot_anchor_live_models():
    context = {"fund_configuration": {"thresholds": {"invest": 80}, "scoreBands": [{"label": "INVEST"}],
                                      "mandate": {"mandateName": "Seed fund"}},
               "prior_decision": {"state": "pass"}}
    original = deepcopy(context)
    result, calls = await run_case(context=context)
    for _, payload in calls:
        assert "thresholds" not in payload["fund_context"]["fund_configuration"]
        assert "scoreBands" not in payload["fund_context"]["fund_configuration"]
        assert payload["fund_context"]["fund_configuration"]["mandate"] == original["fund_configuration"]["mandate"]
    assert "prior_decision" not in calls[0][1]["fund_context"]
    assert calls[1][1]["fund_context"]["prior_decision"] == original["prior_decision"]
    assert result.context_snapshot == original
    assert context == original


@pytest.mark.asyncio
async def test_reviewer_owns_score_partner_owns_action_and_lineage():
    result, calls = await run_case(proposal=7, action="PASS")
    assert [stage for stage, _ in calls] == ["reviewer", "partner"]
    assert all(item.score == 7 for item in result.evaluation.criteria)
    assert result.evaluation.recommendation.state == "pass"
    assert result.partner.judgment.action == "PASS"
    assert result.partner.operational_action == "PASS"
    assert result.partner.judgment.assessment_ids == [item.assessment_id for item in result.reviewer.assessments]
    assert result.validation.lineage.reviewer_run_id == result.reviewer.lineage.reviewer_run_id
    assert result.partner.lineage.validation_run_id == result.validation.lineage.validation_run_id
    assert all(item.reviewer_assessment_id for item in result.validation.assessments)
    assert "recommendation" not in calls[1][1]
    assert "criterion_score" not in str(calls[0][1]["factual_evidence"])
    assert result.model_validate_json(result.model_dump_json()) == result
    assert [(event["stage"], event["status"]) for event in result.trace] == [
        ("reviewer", "STARTED"), ("reviewer", "DONE"),
        ("validation", "STARTED"), ("validation", "DONE"),
        ("partner", "STARTED"), ("partner", "DONE"),
    ]


@pytest.mark.asyncio
async def test_model_failure_records_the_actual_failed_stage(caplog):
    caplog.set_level("INFO")

    async def failed(*args):
        raise RuntimeError("synthetic provider failure")

    with pytest.raises(RuntimeError, match="synthetic provider"):
        await analyze(user_id="tenant", lineage=Lineage(user_id="tenant", opportunity_id="opportunity"),
                      identity=Identity(name="Synthetic"), snapshot=[], policy=_policy(), context={},
                      generate=failed, evaluation_at=CLOCK)
    assert "stage=reviewer status=FAILED" in caplog.text
    assert "stage=partner status=STARTED" not in caplog.text


@pytest.mark.asyncio
async def test_same_scores_support_different_partner_judgments():
    passed, _ = await run_case(action="PASS", conclusion="Upside is capped by market structure")
    advanced, _ = await run_case(action="ADVANCE", conclusion="Distribution supports venture-scale upside")
    assert [item.score for item in passed.evaluation.criteria] == [item.score for item in advanced.evaluation.criteria]
    assert passed.evaluation.recommendation.state == "pass"
    assert advanced.evaluation.recommendation.state == "advance"
    assert passed.evaluation.recommendation.decision_drivers != advanced.evaluation.recommendation.decision_drivers


@pytest.mark.asyncio
async def test_compatibility_provenance_preserves_more_diligence_action():
    from investment_analysis.projection import legacy_stage_projection

    result, _ = await run_case(action="MORE_DILIGENCE")
    _, partner, _ = legacy_stage_projection(user_id="tenant", analysis=result)
    assert partner["provenance"]["canonical_recommendation"] == "insufficient_evidence"


@pytest.mark.asyncio
async def test_partner_short_assessment_handles_bind_to_review_ids():
    async def generate(stage, prompt, payload, schema):
        if stage == "reviewer":
            return ReviewerDraft(overall_assessment="Not enough evidence.", assessments=[{
                "dimension": "MARKET", "conclusion": "Unknown", "score_rationale": "No evidence"}])
        assert payload["review"]["assessments"][0]["assessment_id"] == "A1"
        assert payload["validated_assessments"]["assessments"][0]["reviewer_assessment_id"] == "A1"
        return PartnerDraft(action="MORE_DILIGENCE", rationale=["Establish market evidence"],
                            confidence=0.4, investment_case="Unverified", assessment_ids=["A1"])

    result = await analyze(user_id="tenant", lineage=Lineage(user_id="tenant"),
                           identity=Identity(name="Synthetic"), snapshot=[], policy=_policy(),
                           context={}, generate=generate, evaluation_at=CLOCK)
    assert result.partner.judgment.assessment_ids == [result.reviewer.assessments[0].assessment_id]


@pytest.mark.asyncio
async def test_acquisition_conflict_cannot_silently_advance_on_historical_traction():
    def acquired(claims, links):
        claims[0]["display_text"] = "Synthetic was acquired by Parent in 2024."

    result, _ = await run_case(action="ADVANCE", mutate=acquired)
    assert result.partner.judgment.action == "ADVANCE"
    assert result.partner.operational_action == "MORE_DILIGENCE"
    assert result.partner.human_review_required
    assert any("ownership" in item.lower() for item in result.partner.constraints)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["B_strong_looking_unverified", "D_missing_dimension", "G_insufficient_evidence"])
async def test_missing_or_unverified_support_cannot_advance(case):
    result, _ = await run_case(case)
    assert any(item.score is None for item in result.evaluation.criteria)
    assert result.partner.judgment.action == "ADVANCE"
    assert result.partner.operational_action == "MORE_DILIGENCE"
    assert result.partner.constraints
    assert result.partner.human_review_required


@pytest.mark.asyncio
async def test_contradictions_keep_judgment_distinct_from_operational_safety():
    result, _ = await run_case("C_contradictory")
    market = next(item for item in result.validation.assessments if item.dimension == "MARKET")
    assert market.contradiction_status == "PRESENT"
    assert result.partner.operational_action == "MORE_DILIGENCE"


@pytest.mark.asyncio
async def test_quality_and_freshness_constrain_proposal_with_explicit_reason():
    def weak(claims, links):
        for link in links:
            link["source_quality"] = 0.6
    result, _ = await run_case(proposal=9, mutate=weak)
    for item in result.validation.assessments:
        assert item.proposed_score == 9
        assert item.validated_score < 9
        assert item.cap_reason
        assert item.score_status == "CAPPED"
    def stale(claims, links):
        for link in links:
            link["evidence_effective_at"] = "2020-01-01T00:00:00+00:00"
    result, _ = await run_case(proposal=9, mutate=stale)
    assert all("evidence_stale" in item.policy_flags for item in result.validation.assessments)


def test_factual_packet_does_not_inherit_scout_investment_opinions_or_mutate_storage():
    raw = [{"claim_id": "c", "normalized_value": {"criterion_score": 9, "revenue": 100}, "primary_thesis": "Buy"}]
    before = deepcopy(raw)
    assert factual_packet(raw) == [{"claim_id": "c", "normalized_value": {"revenue": 100}}]
    assert raw == before


@pytest.mark.asyncio
async def test_reviewer_cannot_cite_cross_snapshot_claims():
    async def generate(stage, prompt, payload, schema):
        return ReviewerDraft(overall_assessment="Test", risks=[{"type": "FACT", "text": "Foreign", "references": {"claim_ids": ["foreign"]}}])
    with pytest.raises(ValueError, match="outside the tenant snapshot"):
        await analyze(user_id="tenant", lineage=Lineage(user_id="tenant"), identity=Identity(),
                      snapshot=[], policy=_policy(), context={}, generate=generate, evaluation_at=CLOCK)
