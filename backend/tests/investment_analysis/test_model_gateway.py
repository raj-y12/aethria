"""Provider payload serialization and accounting use real persistence value types."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from investment_analysis.model_gateway import ModelGateway, normalize_reviewer_payload
from investment_analysis.service import reviewer_dimension_name
from investment_analysis.models import ReviewerDraft


def test_normalize_reviewer_payload_maps_legacy_dimension_and_reference_shapes():
    payload = {
        "overall_assessment": "Evidence-based analysis",
        "assessments": [{
            "dimension": "TECHNICAL",
            "conclusion": "The product appears feasible.",
            "score_rationale": "The evidence is early.",
            "limititations": ["Scalability is not yet verified."],
            "References": {"claim_ids": ["claim-1"]},
        }],
        "analysis_sections": [{
            "name": "TECHNICAL",
            "status": "PRESENT",
            "limitations": ["Not enough engineering detail."],
            "References": {"claim_ids": ["claim-1"]},
        }],
        "portfolio_scope": "input context",
        "research_attempted": False,
        "rubric": {"version": "4.0"},
    }

    normalized = normalize_reviewer_payload(payload)

    assert normalized["assessments"][0]["dimension"] == "TECHNOLOGY"
    assert normalized["assessments"][0]["limitations"] == ["Scalability is not yet verified."]
    assert "References" not in normalized["assessments"][0]
    assert normalized["analysis_sections"] == [{"name": "TECHNOLOGY", "status": "PRESENT"}]
    assert "portfolio_scope" not in normalized
    assert "research_attempted" not in normalized
    assert "rubric" not in normalized


def test_reviewer_dimension_name_uses_current_contract_enum():
    assert reviewer_dimension_name("technical") == "TECHNOLOGY"
    assert reviewer_dimension_name("market") == "MARKET"


def test_normalize_reviewer_payload_maps_legacy_reasoning_categories_and_nested_fields():
    normalized = normalize_reviewer_payload({
        "overall_assessment": "Mixed evidence",
        "risks": [{
            "type": "EXECUTION_RISK",
            "text": "Delivery risk remains material.",
            "reasoning": [{"type": "FACT", "text": "The team is small."}],
            "limitations": ["Hiring plan is unverified."],
            "unknowns": ["Future hiring pace."],
        }],
        "diligence_priorities": [{"type": "RESEARCH", "text": "Verify retention."}],
    })

    assert normalized["risks"] == [{"type": "INFERENCE", "text": "Delivery risk remains material."}]
    assert normalized["diligence_priorities"] == [{"type": "UNKNOWN", "text": "Verify retention."}]


def test_normalize_reviewer_payload_merges_reference_lists():
    normalized = normalize_reviewer_payload({
        "overall_assessment": "Evidence-based analysis",
        "risks": [{"type": "INFERENCE", "text": "Risk", "references": [
            {"claim_ids": ["claim-1"]}, {"evidence_item_ids": ["evidence-1"]},
        ]}],
    })
    assert normalized["risks"][0]["references"] == {
        "claim_ids": ["claim-1"], "evidence_item_ids": ["evidence-1"], "source_ids": [],
    }


@pytest.mark.asyncio
async def test_persisted_context_uuid_and_timestamp_serialize_and_usage_is_recorded(monkeypatch):
    completion = Mock(return_value=SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(parsed=ReviewerDraft(overall_assessment="Evidence-based analysis"), refusal=None))],
        usage=SimpleNamespace(total_tokens=123),
    ))
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=completion)), close=Mock())
    monkeypatch.setattr("investment_analysis.model_gateway.build_openai_client", lambda key: client)
    budget = SimpleNamespace(user_id="tenant", can_make_call=Mock(return_value=(True, None)), record_call=Mock())
    gateway = ModelGateway(user_id="tenant", api_key="synthetic", reviewer_model="test-model",
                           partner_model="test-model", cost_controller=budget, max_completion_tokens=1000)
    record_id = uuid4()
    result = await gateway("reviewer", "Return analysis", {
        "prior_decision": {"recommendation_id": record_id, "created_at": datetime(2026, 9, 1, tzinfo=timezone.utc)},
    }, ReviewerDraft)
    assert result.overall_assessment == "Evidence-based analysis"
    user_message = completion.call_args.kwargs["messages"][1]["content"]
    assert str(record_id) in user_message
    assert "2026-09-01T00:00:00Z" in user_message
    budget.record_call.assert_called_once_with("reviewer", "investment-reviewer", tokens_used=123)
    gateway.close()
    client.close.assert_called_once()
@pytest.mark.asyncio
async def test_unconfigured_analysis_does_not_spend_on_factual_retrieval(monkeypatch):
    from unittest.mock import AsyncMock
    from investment_analysis.repository import InvestmentAnalysisRepository
    from investment_analysis.model_gateway import AnalysisBlocked
    from tests.evaluation_v2.test_phase0_provenance_e2e import _policy

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prepare = AsyncMock()
    repository = InvestmentAnalysisRepository(object(), evidence_preparer=prepare)
    with pytest.raises(AnalysisBlocked) as error:
        await repository.evaluate(user_id="fund-a", opportunity_id="opp-a", actor_id="fund-a",
                                  trigger_type="manual", policy=_policy())
    assert error.value.code == "analysis_model_unconfigured"
    prepare.assert_not_called()
