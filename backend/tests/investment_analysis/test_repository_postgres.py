"""Real persistence with mocked model judgment; existing identity/evidence stay real."""
import os
from types import SimpleNamespace

import pytest

from evaluation_v2.repository import EvaluationRepository
from investment_analysis.repository import InvestmentAnalysisRepository
from investment_analysis.models import ReviewerDraft, PartnerDraft
from tests.evaluation_v2.test_phase0_provenance_postgres import test_postgres_roundtrip_and_tenant_isolation as walk_pipeline


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL required")
@pytest.mark.asyncio
async def test_new_authority_roundtrip_on_real_pipeline(monkeypatch):
    original = EvaluationRepository.evaluate
    calls = []
    preparation_calls = []

    async def replace(self, **kwargs):
        if kwargs.get("prepared_analysis") is not None:
            analysis = kwargs["prepared_analysis"]
            assert analysis.reviewer.lineage.reviewer_run_id
            assert analysis.partner.lineage.partner_run_id
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """update startups s set investment_memo_markdown='Historical synthetic memo',
                    agent_trace=coalesce(agent_trace,'{}'::jsonb) || '{"evaluation_manifest":{"legacy":true}}'::jsonb
                    from opportunities o where o.user_id=$1 and o.opportunity_id=$2
                    and s.user_id=o.user_id and s.startup_id=o.legacy_startup_id::text""",
                    kwargs["user_id"], kwargs["opportunity_id"],
                )
            result = await original(self, **kwargs)
            assert result["judgment_audit"]["investment_analysis"]["partner"]["judgment"]["action"] == "MONITOR"
            history = result["judgment_audit"]["superseded_startup_projection"]
            assert history["investment_memo_markdown"] == "Historical synthetic memo"
            assert history["agent_trace"]["evaluation_manifest"] == {"legacy": True}
            market = next(item for item in result["criteria"] if item["criterion"] == "market")
            if len(calls) == 4:
                change = market["deterministic_adjustments"]["change_from_prior_review"]
                assert change["previous_score"] == 8
                assert change["score_changed"] is False
            else:
                assert "change_from_prior_review" not in market["deterministic_adjustments"]
            return result

        # This synthetic source belongs to the fixture company; make that
        # identity explicit rather than relying on "phase0" in its URL.
        async with self.pool.acquire() as conn:
            await conn.execute("""update companies c set canonical_domain='example.test'
                from opportunities o where o.user_id=$1 and o.opportunity_id=$2
                and c.user_id=o.user_id and c.company_id=o.company_id""",
                kwargs["user_id"], kwargs["opportunity_id"])
            # Even a malformed legacy link must not cross company boundaries
            # merely because both records belong to the same tenant.
            from uuid import uuid4
            from evaluation_v2.evidence_projection import enriched_claim_evidence_sql
            isolation = conn.transaction()
            await isolation.start()
            try:
                foreign_company = str(uuid4())
                await conn.execute("insert into companies(company_id,user_id,canonical_name) values($1,$2,'Other studio')",
                                   foreign_company, kwargs["user_id"])
                await conn.execute("update evidence_artifacts set company_id=$3 where user_id=$1 and opportunity_id=$2",
                                   kwargs["user_id"], kwargs["opportunity_id"], foreign_company)
                assert not await conn.fetch(enriched_claim_evidence_sql(), kwargs["user_id"], kwargs["opportunity_id"])
            finally:
                await isolation.rollback()

        class Pool:
            def acquire(inner):
                return self.pool.acquire()
            async def fetchrow(inner, sql, *args):
                async with self.pool.acquire() as conn:
                    return await conn.fetchrow(sql, *args)

        async def prerequisites(uid):
            return SimpleNamespace(require_tenant=lambda *a, **k: None,
                                   policy=kwargs["policy"], thesis_version_id=kwargs.get("thesis_version_id"),
                                   thesis_context={"raw_text": "Synthetic fund"}, fund_config={})

        async def generate(stage, prompt, payload, schema):
            calls.append(stage)
            if stage == "reviewer":
                assert len(preparation_calls) == (len(calls) + 1) // 2
                assert payload["fund_context"]["evidence_preparation"]["status"] == "reused"
                from evidence.factual import retain_verified_source_statements
                from evidence.repository import EvidenceRepository
                evidence_repository = EvidenceRepository(Pool())
                ledger = await evidence_repository.get_ledger(user_id=kwargs["user_id"], opportunity_id=kwargs["opportunity_id"])
                verified_ids = [str(item["evidence_item_id"]) for item in ledger["evidence_items"]
                                if item["verification_state"] == "verified"]
                factual_args = dict(user_id=kwargs["user_id"], opportunity_id=kwargs["opportunity_id"],
                                    company_id=str(ledger["artifacts"][0]["company_id"]),
                                    evidence_item_ids=verified_ids, evidence_repository=evidence_repository)
                # Verify factual persistence in a savepoint, then roll it back so
                # this mutation cannot invalidate the in-flight analysis snapshot.
                async with self.pool.acquire() as conn:
                    savepoint = conn.transaction()
                    await savepoint.start()
                    try:
                        assert (await retain_verified_source_statements(**factual_args))["claims_created"] == len(verified_ids)
                        assert (await retain_verified_source_statements(**factual_args))["claims_created"] == 0
                        with pytest.raises(ValueError, match="scope"):
                            await retain_verified_source_statements(**{**factual_args, "user_id": "other-fund"})
                    finally:
                        await savepoint.rollback()
                claim = next(item for item in payload["factual_evidence"] if item["assertion_class"] == "externally_verified")
                return ReviewerDraft(overall_assessment="Judgment on the factual market",
                    assessments=[{"dimension": "MARKET", "conclusion": "Strong demand", "proposed_score": 8,
                                  "score_rationale": "Observed market adoption supports demand", "confidence": 0.9,
                                  "reasoning": [{"type": "INFERENCE", "text": "Adoption supports demand",
                                                 "references": {"claim_ids": [claim["claim_id"]]}}]}])
            return PartnerDraft(action="MONITOR", rationale=["Wait for execution evidence"],
                                assessment_ids=[item["assessment_id"] for item in payload["review"]["assessments"]],
                                confidence=0.6, investment_case="Potential demand; execution untested")

        async def prepare(**arguments):
            from investment_analysis.evidence import prepare_factual_evidence
            result = await prepare_factual_evidence(**arguments)
            preparation_calls.append(result)
            return result

        repo = InvestmentAnalysisRepository(Pool(), generate=generate, prerequisites_loader=prerequisites,
                                            evidence_preparer=prepare, clock=self._clock)
        result = await repo.evaluate(**kwargs)
        record = await repo.get_current(user_id=kwargs["user_id"], opportunity_id=kwargs["opportunity_id"])
        status = await repo.inspect_dependencies(user_id=kwargs["user_id"], opportunity_id=kwargs["opportunity_id"], record=record)
        assert status["state"] == "current"
        with pytest.raises(ValueError, match="tenant/opportunity"):
            await repo.inspect_dependencies(user_id="another-fund", opportunity_id=kwargs["opportunity_id"], record=record)
        return result

    monkeypatch.setattr(EvaluationRepository, "evaluate", replace)
    await walk_pipeline()
    assert calls == ["reviewer", "partner", "reviewer", "partner"]
