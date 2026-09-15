"""Phase 1 boundaries preserve payloads and do not invent target authority."""
from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from pipeline_contracts.adapters import (
    adapt_current_scout_to_scout_output, adapt_current_review_to_reviewer_output,
    adapt_current_evaluation_to_validation_result, adapt_current_partner_to_partner_output,
    adapt_current_evidence_review, adapt_current_partner_route, project_current_payload,
)
from pipeline_contracts.models import (
    AnalysisSection, AnalysisSectionType, AssessmentValidationResult, Identity,
    Lineage, PartnerInput, PartnerOutput, ReasoningType, ReasoningUnit, References,
    ReviewerAssessment, ReviewerInput, ReviewerOutput, ReviewStatus, ScoutOutput,
    ValidatedAssessment, ValidationStatus,
)

UID = "contract-tenant"
LINEAGE = Lineage(user_id=UID, company_id="company", opportunity_id="opportunity", reviewer_run_id="review-run")
GOLDEN = Path(__file__).parents[1] / "evaluation_v2" / "phase0_golden_pipeline.json"

ADAPTER_CASES = [
    (adapt_current_scout_to_scout_output, {"name": "Acme", "primary_thesis": "Could be compelling", "one_line": "Unverified narrative", "references": ["https://example.test"], "biggest_unknown": "Revenue", "confidence_score": 0.9}),
    (adapt_current_review_to_reviewer_output, {"market_score": 9, "overall_summary": "Promising", "team_analysis": ["Experienced"], "score_reasoning": {"market_score": "Large TAM"}, "reviews": [{"reviewer_type": "SkepticalReviewer", "market_score": 4}], "unknown_future_field": {"value": None}}),
    (adapt_current_evaluation_to_validation_result, {"snapshot_hash": "snapshot", "criteria": [{"criterion": "market", "score": 6, "reasoning": "Current boundary", "confidence": 0.9}], "recommendation": {"state": "monitor", "human_review_required": True}}),
    (adapt_current_partner_to_partner_output, {"recommendation": "INVEST", "confidence": 0, "decision_rationale": "Frozen decision", "next_action": "Discuss", "provenance": {"recommendation_origin": "PARTNER_CANONICAL_MAPPING", "canonical_recommendation": "advance"}}),
    (adapt_current_evidence_review, {"evaluation_id": "eval", "scored_criteria": 4, "evidence_coverage": "insufficient", "missing_information": ["Execution"], "decision_drivers": ["Market"]}),
    (adapt_current_partner_route, {"route": "advance", "recommendation_id": "rec", "rationale": ["Market"], "human_review_required": True}),
]


@pytest.mark.parametrize("adapter,payload", ADAPTER_CASES)
def test_lossless_deterministic_json_roundtrip_and_no_mutation(adapter, payload):
    before = deepcopy(payload)
    result = adapter(user_id=UID, payload=payload, lineage=LINEAGE)
    again = adapter(user_id=UID, payload=dict(reversed(list(payload.items()))), lineage=LINEAGE)
    assert result == again
    assert type(result).model_validate_json(result.model_dump_json()) == result
    assert project_current_payload(user_id=UID, contract=result) == before
    result.compatibility.original_payload["copy_probe"] = True
    assert payload == before


@pytest.mark.parametrize("adapter,payload", ADAPTER_CASES)
def test_tenant_checks_include_nested_payloads_and_projection(adapter, payload):
    with pytest.raises(ValueError, match="tenant"):
        adapter(user_id="other", payload=payload, lineage=LINEAGE)
    with pytest.raises(RuntimeError, match="user_id"):
        adapter(user_id="", payload=payload, lineage=LINEAGE)
    with pytest.raises(ValueError, match="tenant"):
        adapter(user_id=UID, payload={**payload, "nested": [{"user_id": "other"}]}, lineage=LINEAGE)
    with pytest.raises(ValueError, match="opportunity_id"):
        adapter(user_id=UID, payload={**payload, "opportunity_id": "foreign"}, lineage=LINEAGE)
    result = adapter(user_id=UID, payload=payload, lineage=LINEAGE)
    with pytest.raises(ValueError, match="tenant"):
        project_current_payload(user_id="other", contract=result)


def test_scout_does_not_promote_narrative_or_hypotheses_to_verified_facts():
    adapter, payload = ADAPTER_CASES[0]
    result = adapter(user_id=UID, payload=payload, lineage=LINEAGE)
    assert result.facts == []
    assert result.identity.name == "Acme"
    assert result.evidence_summary.coverage is None
    assert result.unknowns[0].type == ReasoningType.UNKNOWN
    assert result.sources[0].source_id is None
    assert result.compatibility.original_payload["primary_thesis"] == payload["primary_thesis"]
    assert result.lineage.scout_run_id is None


def test_legacy_review_scores_are_not_target_proposals_and_ids_are_scoped():
    adapter, payload = ADAPTER_CASES[1]
    result = adapter(user_id=UID, payload=payload, lineage=LINEAGE)
    assessment = result.assessments[0]
    assert assessment.proposed_score is None
    assert assessment.score_origin == "UNKNOWN_LEGACY"
    assert assessment.score_rationale == "Large TAM"
    assert result.analysis_sections[0].reasoning_units[0].references.claim_ids == []
    other = adapter(user_id="other", payload=payload, lineage=Lineage(user_id="other"))
    assert other.assessments[0].assessment_id != assessment.assessment_id
    changed = adapter(user_id=UID, payload={**payload, "market_score": 8}, lineage=LINEAGE)
    assert changed.assessments[0].assessment_id != assessment.assessment_id


def test_current_evaluation_preserves_score_and_links_without_fabricated_validation():
    payload = {"evaluation": {"evaluation_id": "eval", "policy_version_id": "policy", "evidence_snapshot_hash": "hash"},
               "criteria": [{"criterion": "market", "criterion_assessment_id": "criterion", "score": 6,
                             "supporting_claim_ids": ["claim"], "contradicting_claim_ids": ["contradiction"],
                             "deterministic_adjustments": {"anything": "preserved"}}],
               "provenance": {"evidence_links": [{"claim_id": "claim", "evidence_item_id": "evidence", "source_id": "source"},
                                                  {"claim_id": "different", "evidence_item_id": "unrelated"}]}}
    result = adapt_current_evaluation_to_validation_result(user_id=UID, payload=payload, lineage=LINEAGE)
    assessment = result.assessments[0]
    assert assessment.validated_score == 6
    assert assessment.proposed_score is None
    assert assessment.reviewer_assessment_id is None
    assert assessment.canonical_criterion_assessment_id == "criterion"
    assert assessment.score_status == ValidationStatus.CURRENT_EVALUATION
    assert assessment.references == References(claim_ids=["claim"], evidence_item_ids=["evidence"], source_ids=["source"])
    assert assessment.contradicting_claim_ids == ["contradiction"]
    assert assessment.policy_versions.policy_version == "policy"
    assert result.lineage.validation_run_id is None
    assert result.lineage.evaluation_run_id == "eval"
    assert project_current_payload(user_id=UID, contract=result) == payload
    with pytest.raises(ValueError, match="evaluation_run_id"):
        adapt_current_evaluation_to_validation_result(user_id=UID, payload=payload, lineage=Lineage(user_id=UID, evaluation_run_id="stale"))


def test_partner_never_maps_routes_or_defaults_unknown_decisions():
    route = adapt_current_partner_route(user_id=UID, payload={"route": "advance"}, lineage=LINEAGE)
    assert route.decision is None
    assert project_current_payload(user_id=UID, contract=route)["route"] == "advance"
    partner = adapt_current_partner_to_partner_output(user_id=UID, payload={}, lineage=LINEAGE)
    assert partner.decision is None
    assert partner.conviction is None
    with pytest.raises(ValidationError):
        adapt_current_partner_to_partner_output(user_id=UID, payload={"recommendation": "bad"}, lineage=LINEAGE)


@pytest.mark.parametrize("case", json.loads(GOLDEN.read_text()))
def test_every_phase0_golden_payload_survives_adapter_roundtrip(case):
    original = json.loads(GOLDEN.read_text())[case]
    evaluation = adapt_current_evaluation_to_validation_result(user_id=UID, payload=original["evaluation"], lineage=LINEAGE)
    partner = adapt_current_partner_to_partner_output(user_id=UID, payload=original["partner"], lineage=LINEAGE)
    review_payload = {f"{key}_score": value for key, value in original["legacy_reviewer_scores"].items()}
    review = adapt_current_review_to_reviewer_output(user_id=UID, payload=review_payload, lineage=LINEAGE)
    assert project_current_payload(user_id=UID, contract=evaluation) == original["evaluation"]
    assert project_current_payload(user_id=UID, contract=partner) == original["partner"]
    assert project_current_payload(user_id=UID, contract=review) == review_payload
    assert partner.decision == original["partner"]["recommendation"]
    if case == "F_legacy_canonical_diverge":
        assert evaluation.assessments[0].validated_score == 6
        assert review.compatibility.original_payload["market_score"] == 9
        assert review.assessments[0].proposed_score is None
        assert partner.decision == "MONITOR"


def test_target_contract_composition_serialization_and_lineage():
    unit = ReasoningUnit(reasoning_unit_id="reasoning", type="INFERENCE", text="Inference",
                         references=References(claim_ids=["claim"], evidence_item_ids=["evidence"], source_ids=["source"]))
    scout = ScoutOutput(lineage=LINEAGE, identity=Identity(name="Acme"))
    review = ReviewerOutput(lineage=LINEAGE, identity=scout.identity,
        assessments=[ReviewerAssessment(assessment_id="assessment", dimension="MARKET", proposed_score=6,
                                        reasoning_units=[unit])],
        analysis_sections=[AnalysisSection(name="TEAM", status="NOT_APPLICABLE")])
    validated = AssessmentValidationResult(lineage=LINEAGE,
        assessments=[ValidatedAssessment(reviewer_assessment_id="assessment", dimension="MARKET", proposed_score=6,
                                         validated_score=6, references=unit.references)])
    decision = PartnerOutput(lineage=LINEAGE, decision="MONITOR", assessment_ids=["assessment"])
    for contract in (scout, review, validated, decision,
                     ReviewerInput(lineage=LINEAGE, scout=scout, prior_review=review),
                     PartnerInput(lineage=LINEAGE, identity=scout.identity, reviewer=review, validation=validated, prior_decision=decision)):
        assert type(contract).model_validate_json(contract.model_dump_json()) == contract
    assert decision.assessment_ids[0] == validated.assessments[0].reviewer_assessment_id == review.assessments[0].assessment_id
    assert review.assessments[0].reasoning_units[0].references == unit.references
    foreign = scout.model_copy(update={"lineage": Lineage(user_id="other")})
    with pytest.raises(ValidationError, match="user_id mismatch"):
        ReviewerInput(lineage=LINEAGE, scout=foreign)
    with pytest.raises(ValueError, match="no current payload"):
        project_current_payload(user_id=UID, contract=scout)


@pytest.mark.parametrize("status", list(ReviewStatus))
def test_section_absence_states_are_distinct_and_serializable(status):
    section = AnalysisSection(name=AnalysisSectionType.MARKET, status=status)
    assert AnalysisSection.model_validate_json(section.model_dump_json()).status == status


def test_projection_is_snapshot_replay_not_target_authority():
    result = adapt_current_partner_to_partner_output(user_id=UID, payload={"recommendation": "PASS"}, lineage=LINEAGE)
    result.decision = "INVEST"
    assert project_current_payload(user_id=UID, contract=result) == {"recommendation": "PASS"}


def test_repository_uuid_values_are_json_compatible():
    evaluation_id = uuid4()
    result = adapt_current_evaluation_to_validation_result(user_id=UID,
        payload={"evaluation": {"evaluation_id": evaluation_id}, "criteria": []}, lineage=LINEAGE)
    assert result.lineage.evaluation_run_id == str(evaluation_id)


def test_persisted_models_are_accepted_without_new_defaults_or_timestamps():
    from models import ScoutInfo, ReviewInfo, PartnerInfo, PartnerSnapshot
    scout = ScoutInfo(name="Acme", one_line="Description", sector="SaaS", problem="Problem", solution="Solution",
                      target_users="Teams", why_now="Timing", scout_type="market_driven", confidence_score=0.7)
    review = ReviewInfo(overall_summary="Summary", key_risks=[], verdict="MEDIUM", market_score=9)
    partner = PartnerInfo(thesis="Thesis", why_this_matters="Why", snapshot=PartnerSnapshot(one_liner="Snapshot"),
                          market_insight="Market", product_edge="Edge", risks=[], recommendation="MONITOR",
                          decision_rationale="Reason", confidence=0.0, next_action="Diligence")
    for adapter, payload in ((adapt_current_scout_to_scout_output, scout),
                             (adapt_current_review_to_reviewer_output, review),
                             (adapt_current_partner_to_partner_output, partner)):
        result = adapter(user_id=UID, payload=payload, lineage=LINEAGE)
        assert project_current_payload(user_id=UID, contract=result) == payload.model_dump(mode="json")


def test_unknown_criterion_and_exact_caps_are_retained_not_reinterpreted():
    payload = {"criteria": [{"criterion": "new_criterion", "score": 4}],
               "provenance": {"criteria": [{"criterion": "new_criterion", "validation": {
                   "supporting_claims": {"claim": {"score_cap": 6, "reason_codes": ["stale"]}}}}]}}
    result = adapt_current_evaluation_to_validation_result(user_id=UID, payload=payload, lineage=LINEAGE)
    assert result.assessments == []
    assert project_current_payload(user_id=UID, contract=result) == payload


def test_target_rejects_invalid_scores_unknown_fields_and_dangling_assessments():
    with pytest.raises(ValidationError):
        Lineage(user_id="   ")
    with pytest.raises(ValidationError):
        ReviewerAssessment(assessment_id="a", dimension="MARKET", proposed_score=11)
    with pytest.raises(ValidationError):
        ReviewerAssessment(assessment_id="a", dimension="MARKET", proposed_score=float("nan"))
    with pytest.raises(ValidationError):
        ScoutOutput(lineage=LINEAGE, identity=Identity(), investment_thesis="not core")
    with pytest.raises(ValidationError, match="absent Reviewer assessment"):
        PartnerInput(lineage=LINEAGE, identity=Identity(),
                     reviewer=ReviewerOutput(lineage=LINEAGE, identity=Identity()),
                     validation=AssessmentValidationResult(lineage=LINEAGE, assessments=[
                         ValidatedAssessment(dimension="MARKET", reviewer_assessment_id="missing")]))
