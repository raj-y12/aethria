from decisions.models import HumanRulingDecision, InitialHumanRulingDecision, OverrideType, WorkflowActionType
from decisions.service import (
    build_workflow_draft,
    classify_override,
    investment_transition_is_allowed,
    ruling_to_opportunity_state,
    workflow_state_for_ruling,
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


def test_export_to_crm_draft_without_context_still_refuses_to_claim_a_write():
    export = build_workflow_draft(WorkflowActionType.EXPORT_TO_CRM, [])
    assert export["requires_approval"] is True
    assert export["external_write_performed"] is False
    assert "crm_row" not in export


def test_export_to_crm_draft_embeds_the_real_payload_when_context_is_supplied():
    export = build_workflow_draft(
        WorkflowActionType.EXPORT_TO_CRM,
        [],
        export_context={
            "company": {"canonical_name": "Acme", "canonical_domain": "acme.ai"},
            "ruling": {
                "decision": "invest",
                "rationale": "Retention held.",
                "investor_confidence": 0.72,
                "created_at": "2026-07-20T12:00:00Z",
            },
            "position": None,
            "outcomes": [],
        },
    )
    assert export["crm_row"]["dedupe_key"] == "acme.ai"
    assert export["crm_row"]["decision"] == "INVEST"
    assert export["requires_approval"] is True
    assert export["external_write_performed"] is False


def test_initial_human_ruling_vocabulary_excludes_invest():
    assert {item.value for item in InitialHumanRulingDecision} == {
        "advance", "monitor", "pass"
    }


def test_advance_enters_active_evidence_workflow():
    assert workflow_state_for_ruling("advance") == "evidence_active"
    assert workflow_state_for_ruling("monitor") == "monitoring"
    assert workflow_state_for_ruling("pass") == "completed"


def test_investment_transition_requires_advance_or_active_diligence():
    assert investment_transition_is_allowed("advance") is True
    assert investment_transition_is_allowed("monitor") is False
    assert investment_transition_is_allowed("pass") is False
    assert investment_transition_is_allowed(None) is False
