from types import SimpleNamespace

import pytest

from identity.models import IdentityAdmission, IdentityStatus, SourceChannel, SourceObservationInput
from opportunity_pipeline import OpportunityPipeline


def observation(user_id="fund-a"):
    return SourceObservationInput(
        user_id=user_id,
        channel=SourceChannel.MANUAL_LOOKUP,
        observed_name="Acme",
        observed_domain="acme.com",
        external_event_key="lookup:1",
    )


@pytest.mark.asyncio
async def test_manual_lookup_is_identity_gated_before_prerequisites():
    class Identity:
        async def admit(self, _):
            return IdentityAdmission(
                user_id="fund-a", observation_id="obs", status=IdentityStatus.AMBIGUOUS,
                identity_case_id="case", blocks_evaluation=True,
            )

    class Loader:
        async def __call__(self, **_):
            raise AssertionError("thesis must not load for unresolved identity")

    pipeline = OpportunityPipeline(
        identity_service=Identity(), evidence_repository=None,
        evaluation_repository=None, prerequisites_loader=Loader(),
    )
    result = await pipeline.process(user_id="fund-a", observation=observation())
    assert result.code == "identity_review_required"
    assert result.status == "blocked"


@pytest.mark.asyncio
async def test_manual_lookup_ingests_evidence_then_evaluates():
    calls = []

    class Identity:
        async def admit(self, _):
            return IdentityAdmission(
                user_id="fund-a", observation_id="obs", status=IdentityStatus.RESOLVED,
                company_id="co", opportunity_id="opp", confidence=1,
            )

    class Evidence:
        async def ingest_artifact(self, artifact, *, items):
            calls.append("evidence")
            return SimpleNamespace(artifact_id="artifact-1"), items

        async def create_claim(self, claim, *, links, created_by):
            calls.append("claim")
            return {"claim_id": "claim-1"}

    class Evaluation:
        async def evaluate(self, **kwargs):
            assert calls == ["evidence", "claim"]
            calls.append("evaluation")
            return {"recommendation": {"state": "advance"}}

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
        user_id="fund-a", observation=observation(),
        references=[{"url": "https://acme.com", "content": "Acme builds software", "verified": True, "source_quality": 0.9}],
        claims=[{"claim_type": "market", "display_text": "Acme builds software", "confidence": 0.9, "evidence_item_ids": ["item-1"], "support_strength": 0.9}],
    )
    assert result.code == "opportunity_evaluated"
    assert calls == ["evidence", "claim", "evaluation"]


@pytest.mark.asyncio
async def test_pipeline_persists_triage_and_stops_light_monitor_before_evaluation():
    class Identity:
        async def admit(self, _):
            return IdentityAdmission(
                user_id="fund-a", observation_id="obs", status=IdentityStatus.RESOLVED,
                company_id="co", opportunity_id="opp", confidence=1,
            )

    class Triage:
        def assess(self, **kwargs):
            from triage.models import TriageAssessment, TriageDisposition
            return TriageAssessment(
                assessment_id="triage-1", user_id="fund-a", opportunity_id="opp",
                disposition=TriageDisposition.LIGHT_MONITOR, reasons=["missing"],
                thesis_version_id="t", policy_version_id="p", trigger="manual_lookup",
                priority=20, confidence=0.5,
            )

    class TriageRepo:
        async def create(self, assessment):
            self.assessment = assessment

    class Loader:
        async def __call__(self, **_):
            return SimpleNamespace(policy=SimpleNamespace(), thesis_version_id="t", thesis_context={}, require_tenant=lambda *_args, **_kwargs: None)

    class Evaluation:
        async def evaluate(self, **_):
            raise AssertionError("light monitor must not evaluate")

    triage_repo = TriageRepo()
    pipeline = OpportunityPipeline(
        identity_service=Identity(), evidence_repository=None, evaluation_repository=Evaluation(),
        prerequisites_loader=Loader(), triage_service=Triage(), triage_repository=triage_repo,
    )
    result = await pipeline.process(user_id="fund-a", observation=observation())
    assert result.code == "triage_light_monitor"
    assert triage_repo.assessment.assessment_id == "triage-1"
