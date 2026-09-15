"""Exercise the actual SDK boundary; mock only the provider's HTTP response."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
from openai import OpenAI
import pytest

from investment_analysis.model_gateway import ModelGateway, AnalysisBlocked
from investment_analysis.models import ReviewerDraft, PartnerDraft


@pytest.mark.asyncio
@pytest.mark.parametrize("stage,schema,body", [
    ("reviewer", ReviewerDraft, {"overall_assessment": "Clinical evidence requires further diligence."}),
    ("partner", PartnerDraft, {"action": "MORE_DILIGENCE", "rationale": ["Verify clinical outcomes."],
                              "confidence": 0.5, "investment_case": "Clinical upside remains unverified."}),
])
async def test_gateway_requires_schema_at_provider_boundary(monkeypatch, stage, schema, body):
    requests = []

    def provider(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "synthetic", "object": "chat.completion", "created": 1,
            "model": "gpt-5-nano", "choices": [{"index": 0, "finish_reason": "stop", "message": {
                "role": "assistant", "content": json.dumps(body), "refusal": None}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}})

    client = OpenAI(api_key="synthetic", http_client=httpx.Client(transport=httpx.MockTransport(provider)))
    monkeypatch.setattr("investment_analysis.model_gateway.build_openai_client", lambda key: client)
    budget = SimpleNamespace(user_id="tenant", can_make_call=lambda *a, **k: (True, None), record_call=Mock())
    gateway = ModelGateway(user_id="tenant", api_key="synthetic", reviewer_model="gpt-5-nano",
                           partner_model="gpt-5-nano", cost_controller=budget, max_completion_tokens=1000)
    try:
        result = await gateway(stage, "Return the investment analysis.", {}, schema)
    finally:
        gateway.close()
    assert isinstance(result, schema)
    response_format = requests[0]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    contract = response_format["json_schema"]["schema"]
    assert contract["additionalProperties"] is False
    assert set(contract["required"]) == set(contract["properties"])
    if stage == "reviewer":
        assert contract["$defs"]["ReasoningDraft"]["properties"]["references"] == {"$ref": "#/$defs/References"}
        assert contract["$defs"]["References"]["type"] == "object"
    budget.record_call.assert_called_once_with(stage, f"investment-{stage}", tokens_used=150)


@pytest.mark.asyncio
@pytest.mark.parametrize("finish_reason,refusal,code", [
    ("stop", "Cannot provide this analysis.", "analysis_model_refused"),
    ("length", None, "analysis_model_truncated"),
])
async def test_gateway_names_provider_failure_and_accounts_usage(monkeypatch, finish_reason, refusal, code):
    def provider(request):
        return httpx.Response(200, json={"id": "synthetic", "object": "chat.completion", "created": 1,
            "model": "gpt-5-nano", "choices": [{"index": 0, "finish_reason": finish_reason, "message": {
                "role": "assistant", "content": None, "refusal": refusal}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}})

    client = OpenAI(api_key="synthetic", http_client=httpx.Client(transport=httpx.MockTransport(provider)))
    monkeypatch.setattr("investment_analysis.model_gateway.build_openai_client", lambda key: client)
    budget = SimpleNamespace(user_id="tenant", can_make_call=lambda *a, **k: (True, None), record_call=Mock())
    gateway = ModelGateway(user_id="tenant", api_key="synthetic", reviewer_model="gpt-5-nano",
                           partner_model="gpt-5-nano", cost_controller=budget, max_completion_tokens=1000)
    try:
        with pytest.raises(AnalysisBlocked) as failure:
            await gateway("reviewer", "Return the investment analysis.", {}, ReviewerDraft)
    finally:
        gateway.close()
    assert failure.value.code == code
    budget.record_call.assert_called_once_with("reviewer", "investment-reviewer", tokens_used=150)
