"""Provider payload serialization and accounting use real persistence value types."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from investment_analysis.model_gateway import ModelGateway
from investment_analysis.service import reviewer_dimension_name
from investment_analysis.models import ReviewerDraft


def test_reviewer_dimension_name_uses_current_contract_enum():
    assert reviewer_dimension_name("technical") == "TECHNOLOGY"
    assert reviewer_dimension_name("market") == "MARKET"


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
