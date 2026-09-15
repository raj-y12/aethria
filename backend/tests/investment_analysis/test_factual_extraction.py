from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from evidence.factual import retain_verified_source_statements


def ledger():
    return {
        "artifacts": [{"artifact_id": "a1", "user_id": "fund-a", "company_id": "company-a",
                       "opportunity_id": "opp-a", "prompt_injection_detected": False}],
        "evidence_items": [{"evidence_item_id": "e1", "artifact_id": "a1", "user_id": "fund-a",
                            "verification_state": "verified", "source_quality": 0.6,
                            "display_excerpt": "The source reports $4M ARR; retention is not disclosed."}],
        "claims": [], "claim_evidence_links": [],
    }


@pytest.mark.asyncio
async def test_factual_extraction_copies_scoped_source_without_model_scores_or_inferred_values():
    source = ledger()
    before = deepcopy(source)
    repository = SimpleNamespace(get_ledger=AsyncMock(return_value=source), create_claim=AsyncMock())
    result = await retain_verified_source_statements(
        user_id="fund-a", company_id="company-a", opportunity_id="opp-a",
        evidence_item_ids=["e1", "e1"], evidence_repository=repository,
    )
    assert result == {"claims_created": 1}
    claim = repository.create_claim.call_args.args[0]
    assert claim.display_text == source["evidence_items"][0]["display_excerpt"]
    assert claim.claim_type == "source_statement"
    assert claim.normalized_value == {"statement_kind": "attributed_source_excerpt"}
    assert repository.create_claim.call_args.kwargs["links"][0].support_strength == 0.6
    assert before == source
    repository.get_ledger.assert_awaited_once_with(user_id="fund-a", opportunity_id="opp-a")


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["foreign_id", "foreign_tenant", "foreign_company", "unverified", "injection", "already_linked"])
async def test_extraction_rejects_foreign_sources_and_reuses_current_claims(change):
    source = ledger()
    ids = ["e1"]
    if change == "foreign_id":
        ids.append("foreign")
    elif change == "foreign_tenant":
        source["evidence_items"][0]["user_id"] = "fund-b"
    elif change == "foreign_company":
        source["artifacts"][0]["company_id"] = "company-b"
    elif change == "unverified":
        source["evidence_items"][0]["verification_state"] = "unverified"
    elif change == "injection":
        source["artifacts"][0]["prompt_injection_detected"] = True
    elif change == "already_linked":
        source["claims"] = [{"claim_id": "c1", "claim_type": "source_statement", "status": "current"}]
        source["claim_evidence_links"] = [{"claim_id": "c1", "evidence_item_id": "e1"}]
    repository = SimpleNamespace(get_ledger=AsyncMock(return_value=source), create_claim=AsyncMock())
    args = dict(user_id="fund-a", company_id="company-a", opportunity_id="opp-a",
                evidence_item_ids=ids, evidence_repository=repository)
    if change.startswith("foreign"):
        with pytest.raises(ValueError, match="scope"):
            await retain_verified_source_statements(**args)
    else:
        assert await retain_verified_source_statements(**args) == {"claims_created": 0}
    repository.create_claim.assert_not_called()
