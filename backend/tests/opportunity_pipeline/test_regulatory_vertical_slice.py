from types import SimpleNamespace

import pytest

from identity.models import IdentityAdmission, IdentityStatus, SourceChannel, SourceObservationInput
from opportunity_pipeline import OpportunityPipeline
from regulatory_context import (
    assemble_regulatory_context,
    derive_regulatory_claims,
    deduplicate_references,
)


def _observation(user_id="fund-a"):
    return SourceObservationInput(
        user_id=user_id,
        channel=SourceChannel.MANUAL_LOOKUP,
        observed_name="Manna Air Delivery",
        observed_domain="manna.aero",
        external_event_key="lookup:manna-1",
    )


def test_regulatory_derivation_distinguishes_current_operation_from_expansion_risk():
    references = [
        {
            "url": "https://manna.aero/operations",
            "title": "Operations",
            "content": "Manna operates commercially in Ireland and currently serves customers.",
            "verified": True,
            "official": True,
            "source_quality": 0.95,
        },
        {
            "url": "https://example.com/regulatory-analysis",
            "title": "Regulatory analysis",
            "content": "Expansion into additional jurisdictions requires regulatory approval.",
            "verified": True,
            "source_quality": 0.8,
        },
    ]

    claims = derive_regulatory_claims(references)

    assert {claim["claim_type"] for claim in claims} == {
        "operational_feasibility",
        "regulatory_expansion_risk",
    }
    operation = next(item for item in claims if item["claim_type"] == "operational_feasibility")
    assert operation["normalized_value"] == {"value": True, "jurisdiction": "Ireland"}
    assert "currently serves customers" in operation["display_text"]
    assert operation["assertion_class"] == "externally_verified"


def test_regulatory_context_is_bounded_and_keeps_provenance_and_conflicts():
    context = assemble_regulatory_context(
        claims=[
            {
                "claim_id": "claim-operation",
                "claim_type": "operational_feasibility",
                "display_text": "The company operates commercially in Ireland.",
                "status": "current",
                "confidence": 0.95,
            },
            {
                "claim_id": "claim-blocker",
                "claim_type": "regulatory_blocker",
                "display_text": "A regulator prohibits the current operating model.",
                "status": "current",
                "confidence": 0.8,
            },
        ],
        evidence=[
            {"evidence_item_id": "item-operation", "claim_id": "claim-operation", "relationship": "supports", "display_excerpt": "Official operations page", "source_locator": "https://manna.aero/operations"},
            {"evidence_item_id": "item-blocker", "claim_id": "claim-operation", "relationship": "contradicts", "display_excerpt": "Regulatory analysis", "source_locator": "https://example.com/regulatory-analysis"},
        ],
        max_chars=500,
    )

    assert len(context) <= 500
    assert "operational_feasibility" in context
    assert "contradicts" in context
    assert "https://manna.aero/operations" in context


def test_regulatory_blocker_preserves_contradiction_against_current_operation():
    claims = derive_regulatory_claims(
        [
            {"url": "https://manna.aero/operations", "content": "Manna operates commercially in Ireland."},
            {"url": "https://example.com/ban", "content": "The current operating model is prohibited in Ireland."},
        ]
    )

    operation = next(item for item in claims if item["claim_type"] == "operational_feasibility")
    blocker = next(item for item in claims if item["claim_type"] == "regulatory_blocker")
    assert operation["_contradicting_indexes"] == [1]
    assert blocker["_contradicting_indexes"] == [0]


def test_repeated_retrieval_references_are_deduplicated_by_content_and_access():
    references = [
        {"url": "https://manna.aero/operations", "content": "Manna operates commercially in Ireland.", "access_class": "public"},
        {"url": "https://manna.aero/operations?utm_source=test", "content": "Manna operates commercially in Ireland.", "access_class": "public"},
        {"url": "https://manna.aero/private-note", "content": "Manna operates commercially in Ireland.", "access_class": "tenant_confidential"},
    ]

    deduped = deduplicate_references(references)

    assert len(deduped) == 2
    assert {item["access_class"] for item in deduped} == {"public", "tenant_confidential"}


@pytest.mark.asyncio
async def test_regulatory_bridge_rejects_cross_tenant_observations_before_storage():
    class Identity:
        async def admit(self, _):
            raise AssertionError("identity admission must not receive a cross-tenant observation")

    pipeline = OpportunityPipeline(
        identity_service=Identity(), evidence_repository=None,
        evaluation_repository=None, prerequisites_loader=None,
    )

    with pytest.raises(ValueError, match="observation tenant"):
        await pipeline.process(user_id="fund-a", observation=_observation("fund-b"))


@pytest.mark.asyncio
async def test_opportunity_pipeline_bridges_references_into_regulatory_claims_and_context():
    calls = []

    class Identity:
        async def admit(self, _):
            return IdentityAdmission(
                user_id="fund-a", observation_id="obs", status=IdentityStatus.RESOLVED,
                company_id="co", opportunity_id="opp", confidence=1,
            )

    class Evidence:
        async def ingest_artifact(self, artifact, *, items):
            calls.append(("evidence", artifact, items))
            stored = [
                SimpleNamespace(
                    evidence_item_id=f"item-{len(calls)}",
                    display_excerpt=item.display_excerpt,
                    source_locator=item.source_locator,
                )
                for item in items
            ]
            return SimpleNamespace(artifact_id=f"artifact-{len(calls)}"), stored

        async def create_claim(self, claim, *, links, created_by):
            calls.append(("claim", claim, links, created_by))
            return {"claim_id": f"claim-{len(calls)}", **claim.model_dump(mode="json")}

    class Evaluation:
        async def evaluate(self, **kwargs):
            calls.append(("evaluation", kwargs))
            return {"recommendation": {"state": "monitor"}}

    class Loader:
        async def __call__(self, **_):
            return SimpleNamespace(
                policy=SimpleNamespace(), thesis_version_id="thesis-1",
                require_tenant=lambda *_args, **_kwargs: None,
            )

    pipeline = OpportunityPipeline(
        identity_service=Identity(), evidence_repository=Evidence(),
        evaluation_repository=Evaluation(), prerequisites_loader=Loader(),
    )
    result = await pipeline.process(
        user_id="fund-a",
        observation=_observation(),
        references=[
            {
                "url": "https://manna.aero/operations",
                "content": "Manna operates commercially in Ireland and currently serves customers.",
                "verified": True,
                "official": True,
                "source_quality": 0.95,
            },
            {
                "url": "https://example.com/regulatory-analysis",
                "content": "Expansion into additional jurisdictions requires regulatory approval.",
                "verified": True,
                "source_quality": 0.8,
            },
        ],
    )

    claim_calls = [entry for entry in calls if entry[0] == "claim"]
    assert {entry[1].claim_type for entry in claim_calls} == {
        "operational_feasibility",
        "regulatory_expansion_risk",
    }
    assert result.code == "opportunity_evaluated"
    assert result.metadata["regulatory_context"]
    assert result.metadata["legacy_compatibility"] is True
