"""Live stage contracts preserve references, serialization and tenant boundaries."""
import pytest
from pydantic import ValidationError

from pipeline_contracts.models import (
    AnalysisSection, AnalysisSectionType, AssessmentValidationResult, Identity,
    Lineage, PartnerInput, PartnerOutput, ReasoningType, ReasoningUnit, References,
    ReviewerAssessment, ReviewerInput, ReviewerOutput, ReviewStatus, ScoutOutput,
    ValidatedAssessment, ValidationStatus,
)

LINEAGE = Lineage(user_id="contract-tenant", company_id="company", opportunity_id="opportunity", reviewer_run_id="review-run")


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


@pytest.mark.parametrize("status", list(ReviewStatus))
def test_section_absence_states_are_distinct_and_serializable(status):
    section = AnalysisSection(name=AnalysisSectionType.MARKET, status=status)
    assert AnalysisSection.model_validate_json(section.model_dump_json()).status == status


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
