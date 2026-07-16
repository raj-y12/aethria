from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from evaluation_v2.policy import evaluation_policy_from_compiled


def _compiled_policy():
    return {
        "policy_version_id": "policy-live",
        "policy_hash": "hash-live",
        "dimensions": {
            "market": {
                "weight": 60,
                "criteria": [
                    {
                        "id": "market_quality",
                        "source_components": ["tam", "urgency"],
                    }
                ],
            },
            "execution": {
                "weight": 40,
                "criteria": [
                    {
                        "id": "founder_execution",
                        "source_components": ["traction", "operational_velocity"],
                    }
                ],
            },
        },
    }


def test_compiled_published_policy_maps_to_evidence_evaluation_contract():
    policy = evaluation_policy_from_compiled(
        _compiled_policy(),
        partner_rules={
            "version": "rules-v2",
            "score_thresholds": {"min_avg_strong_yes": 8, "min_avg_pass": 5.5},
        },
    )

    assert policy.policy_version_id == "policy-live"
    assert policy.policy_hash == "hash-live"
    assert policy.partner_rules_version == "rules-v2"
    assert policy.advance_threshold == 8
    assert policy.pass_threshold == 5.5
    assert sum(item.weight for item in policy.criteria) == pytest.approx(1)
    market = next(item for item in policy.criteria if item.criterion == "market")
    assert {"market", "market_quality", "tam", "urgency"}.issubset(market.claim_types)


@pytest.mark.asyncio
async def test_evaluate_endpoint_uses_active_thesis_and_published_policy(monkeypatch):
    import routers.evaluations as route

    thesis = SimpleNamespace(version_id="thesis-live")
    policy = evaluation_policy_from_compiled(
        _compiled_policy(), partner_rules={"version": "rules-v2"}
    )

    class Repository:
        async def evaluate(self, **kwargs):
            assert kwargs["thesis_version_id"] == "thesis-live"
            assert kwargs["policy"] == policy
            return {"evaluation_id": "evaluation-1"}

    monkeypatch.setattr(route, "get_service_client", lambda: object())
    monkeypatch.setattr(route, "get_active_thesis", lambda client, user_id: thesis)
    monkeypatch.setattr(route, "load_published_policy", lambda user_id: _compiled_policy())
    monkeypatch.setattr(route, "get_partner_rules", lambda: {"version": "rules-v2"})
    request = SimpleNamespace(
        state=SimpleNamespace(user_id="user-a"),
        app=SimpleNamespace(state=SimpleNamespace(evaluation_repository=Repository())),
    )

    result = await route.evaluate_opportunity(request, "opportunity-1")

    assert result == {"evaluation_id": "evaluation-1"}


@pytest.mark.asyncio
async def test_evaluate_endpoint_fails_closed_when_thesis_is_missing(monkeypatch):
    import routers.evaluations as route

    class Repository:
        async def evaluate(self, **kwargs):
            raise AssertionError("repository must not run without a thesis")

    monkeypatch.setattr(route, "get_service_client", lambda: object())
    monkeypatch.setattr(route, "get_active_thesis", lambda client, user_id: None)
    request = SimpleNamespace(
        state=SimpleNamespace(user_id="user-a"),
        app=SimpleNamespace(state=SimpleNamespace(evaluation_repository=Repository())),
    )

    with pytest.raises(HTTPException) as exc:
        await route.evaluate_opportunity(request, "opportunity-1")

    assert exc.value.status_code == 409
    assert exc.value.detail == "An active fund thesis is required before evaluation"
