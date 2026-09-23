from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from investment_analysis.evidence import prepare_factual_evidence
from evaluation_v2.service import snapshot_claims
from tests.evaluation_v2.historical_fixtures import _inputs, CLOCK
from tests.evaluation_v2.test_phase0_provenance_e2e import _policy


@pytest.mark.asyncio
async def test_sufficient_canonical_evidence_does_not_repeat_retrieval():
    claims, links, _ = _inputs("A_strong_verified")
    snapshot, _ = snapshot_claims(claims, links, evaluation_at=CLOCK)
    repository = SimpleNamespace(get_ledger=AsyncMock())
    result = await prepare_factual_evidence(
        user_id="fund-a", company_id="company-a", opportunity_id="opp-a", company_name="Acme",
        company_website=None, snapshot=snapshot, policy=_policy(), evaluation_at=CLOCK,
        evidence_repository=repository,
    )
    assert result["status"] == "reused"
    repository.get_ledger.assert_not_called()


@pytest.mark.asyncio
async def test_missing_canonical_support_uses_bounded_retrieval_and_factual_retention(monkeypatch):
    repository = SimpleNamespace(get_ledger=AsyncMock(return_value={"evidence_items": []}),
                                 create_plan=AsyncMock(return_value="plan"))
    retrieval = AsyncMock(return_value={"verified_items": [{"evidence_item_id": "item-1"}]})
    retain = AsyncMock(return_value={"claims_created": 1})
    monkeypatch.setattr("investment_analysis.evidence.execute_evidence_plan", retrieval)
    monkeypatch.setattr("investment_analysis.evidence.retain_verified_source_statements", retain)
    result = await prepare_factual_evidence(
        user_id="fund-a", company_id="company-a", opportunity_id="opp-a", company_name="Acme",
        company_website="acme.example", snapshot=[], policy=_policy(), evaluation_at=CLOCK,
        evidence_repository=repository,
    )
    assert result == {"status": "retrieved", "claims_created": 1}
    assert retrieval.call_args.kwargs["user_id"] == "fund-a"
    assert retain.call_args.kwargs["evidence_item_ids"] == ["item-1"]
    assert len(repository.create_plan.call_args.kwargs["search_questions"]) <= 5
