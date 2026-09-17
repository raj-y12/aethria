from context import derive_scout_claims


def test_source_snippets_do_not_make_scout_claims_externally_verified():
    claims = derive_scout_claims({
        "funding_stage": "Seed",
        "traction_facts": {"revenue": "$4M ARR"},
        "source_evidence": [{"url": "https://acme.example", "snippet": "Seed funding and $4M ARR."}],
    })
    assert claims
    assert all(claim["assertion_class"] == "unverified" for claim in claims)


async def test_persisted_scout_claims_and_evidence_remain_unverified():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from context import persist_scout_claims

    repository = SimpleNamespace(
        get_ledger=AsyncMock(return_value={"claims": [], "claim_evidence_links": []}),
        ingest_artifact=AsyncMock(return_value=(None, [SimpleNamespace(evidence_item_id="evidence-1")])),
        create_claim=AsyncMock(),
    )
    result = await persist_scout_claims(
        user_id="fund-a", company_id="company-a", opportunity_id="opportunity-a",
        observation_id="observation-a", evidence_repository=repository,
        scout_output={"funding_stage": "Seed", "source_evidence": [
            {"url": "https://acme.example", "snippet": "Seed funding round."},
        ]},
    )
    assert result["claims_created"] == 1
    item = repository.ingest_artifact.call_args.kwargs["items"][0]
    claim = repository.create_claim.call_args.args[0]
    assert item.verification_state.value == claim.assertion_class.value == "unverified"
    assert item.user_id == claim.user_id == "fund-a"
    assert repository.create_claim.call_args.kwargs["links"][0].evidence_item_id == "evidence-1"
    # A retry with the same source material must reuse the current claim.
    repository.get_ledger.return_value = {
        "claims": [{**claim.model_dump(mode="json"), "claim_id": "existing", "status": "current"}],
        "claim_evidence_links": [{"claim_id": "existing", "evidence_item_id": "evidence-1", "relationship": "supports"}],
    }
    repeated = await persist_scout_claims(
        user_id="fund-a", company_id="company-a", opportunity_id="opportunity-a",
        observation_id="observation-b", evidence_repository=repository,
        scout_output={"funding_stage": "Seed", "source_evidence": [
            {"url": "https://acme.example", "snippet": "Seed funding round."}]},
    )
    assert repeated["claims_created"] == 0
    repository.create_claim.assert_awaited_once()


def test_derives_only_decision_bearing_claims_with_matching_source_evidence():
    claims = derive_scout_claims(
        {
            "funding_stage": "Seed",
            "est_tam": "$2B",
            "traction_facts": {"revenue": "$4M ARR", "employees": "40"},
            "solution": "Workflow automation for finance teams",
            "source_evidence": [
                {"url": "https://acme.example/metrics", "snippet": "Acme reports $4M ARR in a $2B market."},
                {"url": "https://news.example/acme", "snippet": "Acme raised a Seed round to expand its workflow product."},
            ],
        }
    )

    assert {claim["claim_type"] for claim in claims} == {
        "traction_revenue",
        "revenue_amount",
        "market_size",
        "funding_stage",
        "product_capability",
    }
    assert all(claim["_supporting_indexes"] for claim in claims)


def test_does_not_promote_scout_prose_or_unmatched_fields_to_claims():
    claims = derive_scout_claims(
        {
            "funding_stage": "Seed",
            "est_tam": "$2B",
            "solution": "A revolutionary platform with huge market potential",
            "source_evidence": [
                {"url": "https://acme.example", "snippet": "Acme is a company."},
            ],
        }
    )

    assert claims == []


def test_claims_preserve_source_indexes_and_normalized_values():
    claims = derive_scout_claims(
        {
            "funding_stage": "Series A",
            "source_evidence": [
                {"url": "https://news.example/acme", "snippet": "The Series A funds product development."},
            ],
        }
    )

    assert claims[0]["claim_type"] == "funding_stage"
    assert claims[0]["normalized_value"] == {"stage": "Series A"}
    assert claims[0]["_supporting_indexes"] == [0]
