from types import SimpleNamespace

import pytest

from identity.models import IdentityAdmission, IdentityStatus, SourceChannel, SourceObservationInput
from opportunity_pipeline import OpportunityPipeline


def _observation():
    return SourceObservationInput(
        user_id="fund-a", channel=SourceChannel.MANUAL_LOOKUP,
        observed_name="Acme", observed_domain="acme.com",
    )


@pytest.mark.asyncio
async def test_scout_claim_bridge_persists_source_grounded_claims_without_replacing_scout_payload():
    captured = []

    class Identity:
        async def admit(self, _):
            return IdentityAdmission(
                user_id="fund-a", observation_id="obs", status=IdentityStatus.RESOLVED,
                company_id="co", opportunity_id="opp", confidence=1,
            )

    class Evidence:
        async def ingest_artifact(self, artifact, *, items):
            return SimpleNamespace(artifact_id="artifact-1"), [SimpleNamespace(evidence_item_id="item-1", display_excerpt="evidence", source_locator="https://acme.example")]

        async def create_claim(self, claim, *, links, created_by):
            captured.append((claim.claim_type, claim.normalized_value, len(links)))
            return {"claim_id": f"claim-{len(captured)}"}

    class Evaluation:
        async def evaluate(self, **_):
            return {"recommendation": {"state": "monitor"}}

    class Loader:
        async def __call__(self, **_):
            return SimpleNamespace(policy=SimpleNamespace(), thesis_version_id="t", require_tenant=lambda *_a, **_k: None)

    result = await OpportunityPipeline(
        identity_service=Identity(), evidence_repository=Evidence(),
        evaluation_repository=Evaluation(), prerequisites_loader=Loader(),
    ).process(
        user_id="fund-a", observation=_observation(),
        references=[{"url": "https://acme.example", "content": "Acme raised a Seed round and reports $4M ARR in a $2B market through its workflow product."}],
        scout_output={
            "funding_stage": "Seed", "est_tam": "$2B",
            "traction_facts": {"revenue": "$4M ARR"},
            "solution": "Workflow automation",
            "source_evidence": [{"url": "https://acme.example", "snippet": "Acme raised a Seed round and reports $4M ARR in a $2B market through its workflow product."}],
        },
    )

    assert result.code == "opportunity_evaluated"
    assert {item[0] for item in captured} == {"funding_stage", "market_size", "traction_revenue", "revenue_amount", "product_capability"}
