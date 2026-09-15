from types import SimpleNamespace

import pytest

from canonical_scout_claims import persist_scout_claims


@pytest.mark.asyncio
async def test_persists_source_grounded_scout_claims_and_evidence_items():
    artifacts = []
    claims = []

    class Evidence:
        async def get_ledger(self, *, user_id, opportunity_id):
            assert (user_id, opportunity_id) == ("fund-a", "opp-a")
            return {"claims": [], "claim_evidence_links": []}

        async def ingest_artifact(self, artifact, *, items):
            artifacts.append((artifact, items))
            return SimpleNamespace(artifact_id=f"artifact-{len(artifacts)}"), [
                SimpleNamespace(evidence_item_id=f"item-{len(artifacts)}", display_excerpt=items[0].display_excerpt, source_locator=artifact.source_uri)
            ]

        async def create_claim(self, claim, *, links, created_by):
            claims.append((claim, links, created_by))
            return {"claim_id": f"claim-{len(claims)}"}

    result = await persist_scout_claims(
        user_id="fund-a", company_id="company-a", opportunity_id="opp-a",
        observation_id="obs-a", scout_output={
            "funding_stage": "Seed", "est_tam": "$2B",
            "traction_facts": {"revenue": "$4M ARR"},
            "solution": "Workflow product",
            "source_evidence": [{"url": "https://acme.example", "snippet": "Acme raised a Seed round and reports $4M ARR in a $2B market product."}],
        }, evidence_repository=Evidence(),
    )

    assert result == {"claims_created": 5, "artifacts_ingested": 1}
    assert len(artifacts) == 1
    assert all(item[1] for item in claims)
    assert all(claim.user_id == "fund-a" for claim, _, _ in claims)


@pytest.mark.asyncio
async def test_skips_scout_payloads_without_source_content():
    class Evidence:
        async def ingest_artifact(self, *args, **kwargs):
            raise AssertionError("no artifact should be created from a URL-only citation")

    result = await persist_scout_claims(
        user_id="fund-a", company_id="company-a", opportunity_id="opp-a",
        observation_id="obs-a", scout_output={
            "funding_stage": "Seed", "source_evidence": [{"url": "https://acme.example", "supports": "company"}],
        }, evidence_repository=Evidence(),
    )

    assert result == {"claims_created": 0, "artifacts_ingested": 0}


@pytest.mark.asyncio
async def test_persists_competition_claims_with_source_links():
    persisted = []

    class Evidence:
        async def get_ledger(self, *, user_id, opportunity_id):
            assert (user_id, opportunity_id) == ("fund-a", "opp-a")
            return {"claims": [], "claim_evidence_links": []}

        async def ingest_artifact(self, artifact, *, items):
            return SimpleNamespace(artifact_id="artifact-competition"), [
                SimpleNamespace(evidence_item_id="item-competition", display_excerpt=items[0].display_excerpt, source_locator=artifact.source_uri)
            ]

        async def create_claim(self, claim, *, links, created_by):
            persisted.append((claim, links, created_by))
            return {"claim_id": f"claim-{len(persisted)}"}

    result = await persist_scout_claims(
        user_id="fund-a", company_id="company-a", opportunity_id="opp-a",
        observation_id="obs-a", scout_output={
            "name": "TargetCo",
            "source_evidence": [{"url": "https://market.example", "snippet": "TargetCo competes with Stripe for European enterprise payments."}],
        }, evidence_repository=Evidence(),
    )

    assert result == {"claims_created": 4, "artifacts_ingested": 1}
    assert {claim.claim_type for claim, _, _ in persisted} == {
        "competitor_existence", "competitor_product_overlap", "competitor_segment_overlap", "competitor_geography_overlap",
    }
    assert all(links and links[0].user_id == "fund-a" for _, links, _ in persisted)
