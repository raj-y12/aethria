"""Real PostgreSQL provenance contract; all synthetic writes roll back."""
import json
import os
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

from agent_trace import build_scout_trace
from evaluation_v2.provenance import PipelineBinding
from investment_analysis.repository import InvestmentAnalysisRepository
from evidence.models import EvidenceArtifactInput, EvidenceItemInput, ClaimInput, ClaimEvidenceLinkInput
from evidence.repository import EvidenceRepository
from tests.evaluation_v2.test_phase0_provenance_e2e import CLOCK, _policy

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL required")


@pytest.mark.asyncio
async def test_postgres_roundtrip_and_tenant_isolation(repository_factory=None):
    import asyncpg
    conn = await asyncpg.connect(os.environ["TEST_DATABASE_URL"])
    transaction = conn.transaction(isolation="repeatable_read")
    await transaction.start()

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield conn

        async def fetchrow(self, sql, *args):
            return await conn.fetchrow(sql, *args)

    uid, other = f"phase0-{uuid4()}", f"phase0-{uuid4()}"
    company, observation, opportunity, startup = [str(uuid4()) for _ in range(4)]
    trace = build_scout_trace({"references": []}, pipeline_run_id="source-scout-run")
    try:
        await conn.execute("insert into companies(company_id,user_id,canonical_name) values($1,$2,'Synthetic Phase 0')", company, uid)
        await conn.execute("insert into source_observations(observation_id,user_id,channel,observed_name,company_id) values($1,$2,'manual_lookup','Synthetic Phase 0',$3)", observation, uid, company)
        await conn.execute("insert into opportunities(opportunity_id,user_id,company_id,first_observation_id,latest_observation_id,legacy_startup_id) values($1,$2,$3,$4,$4,$5)", opportunity, uid, company, observation, startup)
        await conn.execute("insert into startups(startup_id,user_id,scout_info,financials,agent_trace) values($1,$2,'{}','{}',$3::jsonb)", startup, uid, json.dumps({"scout": trace}))
        await conn.execute("update companies set canonical_domain='example.test' where user_id=$1 and company_id=$2", uid, company)
        evidence = EvidenceRepository(Pool())
        artifact, items = await evidence.ingest_artifact(
            EvidenceArtifactInput(user_id=uid, company_id=company, opportunity_id=opportunity,
                                  source_observation_id=observation, artifact_type="web_page",
                                  content_hash=str(uuid4()), source_uri="https://example.test/phase0",
                                  trust_class="independent", untrusted_input=False,
                                  effective_at=CLOCK, retrieved_at=CLOCK),
            items=[EvidenceItemInput(user_id=uid, item_type="market", display_excerpt="Verified synthetic market evidence",
                                     verification_state="verified", source_quality=0.9, extraction_confidence=0.9, effective_at=CLOCK)],
        )
        claim_input = ClaimInput(user_id=uid, company_id=company, opportunity_id=opportunity, claim_type="market",
                                normalized_value={"criterion_score": 8.0, "score_band": "high"},
                                display_text="Synthetic market evidence", assertion_class="externally_verified", confidence=0.9)
        link = ClaimEvidenceLinkInput(user_id=uid, evidence_item_id=items[0].evidence_item_id, relationship="supports", support_strength=0.9)
        claim = await evidence.create_claim(claim_input, links=[link], created_by=uid)
        if repository_factory is None:
            from types import SimpleNamespace
            from unittest.mock import AsyncMock
            async def prerequisites(user_id):
                return SimpleNamespace(require_tenant=lambda *a, **k: None, policy=_policy(),
                    thesis_version_id=None, thesis_context={}, fund_config={})
            # Obtain the same frozen model outputs used by publication unit tests.
            async def generate(stage, prompt, payload, schema):
                from investment_analysis.models import ReviewerDraft, PartnerDraft
                if stage == "reviewer":
                    market = next(row for row in payload["factual_evidence"] if row["assertion_class"] == "externally_verified")
                    return ReviewerDraft(overall_assessment="Synthetic market review", assessments=[{
                        "dimension": "MARKET", "conclusion": "Observed adoption", "proposed_score": 8,
                        "score_rationale": "Observed adoption supports demand", "confidence": 0.9,
                        "reasoning": [{"type": "INFERENCE", "text": "Observed adoption supports demand",
                                       "references": {"claim_ids": [market["claim_id"]]}}]}])
                return PartnerDraft(action="MONITOR", rationale=["Wait for execution evidence"], confidence=0.6,
                    investment_case="Observed demand", assessment_ids=[item["assessment_id"] for item in payload["review"]["assessments"]])
            repository = InvestmentAnalysisRepository(Pool(), clock=lambda: CLOCK, generate=generate,
                prerequisites_loader=prerequisites,
                evidence_preparer=AsyncMock(return_value={"status": "frozen_fixture", "claims_created": 0}))
        else:
            repository = await repository_factory(Pool(), user_id=uid, opportunity_id=opportunity, clock=lambda: CLOCK)
        result = await repository.evaluate(user_id=uid, opportunity_id=opportunity, actor_id=uid, trigger_type="rerun",
                                           policy=_policy(), pipeline_binding=PipelineBinding(user_id=uid, pipeline_run_id="rerun-a", pipeline_entry_type="rerun"))
        projected = await repository.get_current(user_id=uid, opportunity_id=opportunity)
        dependencies = await repository.inspect_dependencies(user_id=uid, opportunity_id=opportunity, record=projected)
        assert dependencies["state"] == "current"
        with pytest.raises(ValueError, match="tenant/opportunity"):
            await repository.inspect_dependencies(user_id=other, opportunity_id=opportunity, record=projected)
        assert projected["provenance"] == result["provenance"]
        assert projected["provenance"]["scout_run_id"] == trace["scout_run_id"]
        assert projected["provenance"]["source_scout_pipeline_run_id"] == "source-scout-run"
        assert projected["provenance"]["company_id"] == company
        assert projected["provenance"]["claim_ids"] == [claim["claim_id"]]
        assert projected["provenance"]["evidence_artifact_ids"] == [artifact.artifact_id]
        market = next(item for item in projected["provenance"]["criteria"] if item["criterion"] == "market")
        assert market["canonical_score"] == 8.0
        # Walk the bound canonical manual entry point too: real evidence writes,
        # current analysis, compatibility projections and authenticated DTO.
        # Identity resolution is frozen to this already-persisted opportunity.
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from identity.models import IdentityAdmission, IdentityStatus, SourceChannel, SourceObservationInput
        from opportunity_pipeline import OpportunityPipeline
        from routers.evaluations import get_current_evaluation
        pipeline = OpportunityPipeline(
            identity_service=SimpleNamespace(admit=AsyncMock(return_value=IdentityAdmission(
                user_id=uid, observation_id=observation, company_id=company,
                opportunity_id=opportunity, status=IdentityStatus.RESOLVED,
            ))),
            evidence_repository=evidence, evaluation_repository=repository,
            prerequisites_loader=AsyncMock(return_value=SimpleNamespace(policy=_policy(), thesis_version_id=None)),
        )
        walked = await pipeline.process(
            user_id=uid, observation=SourceObservationInput(user_id=uid, channel=SourceChannel.MANUAL_LOOKUP, observed_name="Synthetic Phase 0"),
            references=[{"url": "https://example.test/operator", "content": "Synthetic operator evidence"}],
            claims=[{"claim_type": "market", "display_text": "Unverified high score", "normalized_value": {"criterion_score": 9}, "confidence": 0.9}],
        )
        request = SimpleNamespace(state=SimpleNamespace(user_id=uid), app=SimpleNamespace(state=SimpleNamespace(evaluation_repository=repository)))
        api = await get_current_evaluation(request, opportunity)
        assert walked.status == "completed"
        assert api["provenance"]["pipeline_run_id"] == walked.pipeline_run_id
        assert walked.metadata["evidence_review"]["evaluation_id"] == str(api["evaluation"]["evaluation_id"])
        assert walked.metadata["partner_route"]["recommendation_id"] == str(api["recommendation"]["recommendation_id"])
        assert walked.metadata["partner_route"]["route"] == api["recommendation"]["recommended_state"]
        assert any(event["stage"] == "canonical_evaluation" and event["status"] == "DONE" for event in walked.pipeline_trace)
        assert next(item for item in api["criteria"] if item["criterion"] == "market")["score"] == 8.0
        assert set(walked.metadata["artifact_ids"]).issubset(api["provenance"]["evidence_artifact_ids"])
        assert await repository.get_current(user_id=other, opportunity_id=opportunity) is None
        with pytest.raises(LookupError):
            await repository.evaluate(user_id=other, opportunity_id=opportunity, actor_id=other, trigger_type="test", policy=_policy())
        with pytest.raises(ValueError, match="tenant mismatch"):
            await evidence.create_claim(claim_input, links=[link.model_copy(update={"user_id": other})], created_by=uid)
    finally:
        await transaction.rollback()
        await conn.close()
