from decisions.models import HumanRulingDecision, OverrideType, WorkflowActionType
from decisions.service import (
    build_workflow_draft,
    classify_override,
    ruling_to_opportunity_state,
)


def test_advance_never_routes_to_invested_portfolio_state():
    assert ruling_to_opportunity_state(HumanRulingDecision.ADVANCE) == "advance"
    assert ruling_to_opportunity_state(HumanRulingDecision.INVEST) == "invested"


def test_override_classification_is_explicit_not_assumed_model_failure():
    assert classify_override(
        recommendation="pass",
        ruling=HumanRulingDecision.ADVANCE,
        requested=OverrideType.MISSING_PRIVATE_EVIDENCE,
    ) is OverrideType.MISSING_PRIVATE_EVIDENCE
    assert classify_override(
        recommendation="advance",
        ruling=HumanRulingDecision.ADVANCE,
        requested=None,
    ) is None


def test_no_recommendation_cannot_be_overridden():
    assert classify_override(
        recommendation=None,
        ruling=HumanRulingDecision.INVEST,
        requested=None,
    ) is None


def test_blank_recommendation_cannot_be_overridden():
    assert classify_override(
        recommendation="   ",
        ruling=HumanRulingDecision.PASS,
        requested=OverrideType.TIMING,
    ) is None


def test_advance_to_invest_is_lifecycle_progression_not_override():
    assert classify_override(
        recommendation="advance",
        ruling=HumanRulingDecision.INVEST,
        requested=None,
    ) is None


def test_diligence_questions_and_information_request_derive_from_gaps():
    questions = build_workflow_draft(
        WorkflowActionType.PREPARE_DILIGENCE_QUESTIONS,
        ["customer retention", "founder domain history"],
    )
    request = build_workflow_draft(
        WorkflowActionType.DRAFT_INFORMATION_REQUEST,
        ["customer retention"],
    )

    assert questions["questions"] == [
        "What evidence can verify customer retention?",
        "What evidence can verify founder domain history?",
    ]
    assert "customer retention" in request["draft"]


def test_external_action_is_always_approval_gated():
    export = build_workflow_draft(WorkflowActionType.EXPORT_TO_CRM, [])
    assert export["requires_approval"] is True
    assert export["external_write_performed"] is False
