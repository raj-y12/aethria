"""Frozen model outputs for testing canonical analysis publication without providers."""
from investment_analysis.models import ReviewerDraft, PartnerDraft
from investment_analysis.service import analyze
from pipeline_contracts.models import Identity, Lineage
from evaluation_v2.service import snapshot_claims


async def analysis_for_snapshot(*, snapshot, policy, user_id, opportunity_id,
                                evaluation_at, pipeline_binding=None, action="MONITOR"):
    async def generate(stage, prompt, payload, schema):
        if stage == "reviewer":
            assessments = []
            for rule in policy.criteria:
                claims = [row for row in payload["factual_evidence"]
                          if row["claim_type"] in rule.claim_types
                          and row["assertion_class"] == "externally_verified"]
                if claims:
                    assessments.append({
                        "dimension": "TECHNOLOGY" if rule.criterion == "technical" else rule.criterion.upper(),
                        "conclusion": "Verified observations support the assessment.",
                        "proposed_score": 8, "confidence": 0.9,
                        "score_rationale": "Observed evidence supports the assessment.",
                        "reasoning": [{"type": "INFERENCE", "text": "Observed evidence supports the assessment.",
                                       "references": {"claim_ids": [row["claim_id"] for row in claims]}}],
                    })
            return ReviewerDraft(overall_assessment="Synthetic evidence-based review.", assessments=assessments)
        return PartnerDraft(action=action, rationale=["Synthetic recorded judgement."], confidence=0.6,
                            investment_case="Synthetic case based on observed evidence.",
                            assessment_ids=[item["assessment_id"] for item in payload["review"]["assessments"]])

    return await analyze(user_id=user_id,
        lineage=Lineage(user_id=user_id, opportunity_id=opportunity_id,
                        company_id=pipeline_binding.company_id if pipeline_binding else None,
                        pipeline_run_id=pipeline_binding.pipeline_run_id if pipeline_binding else None),
        identity=Identity(name="Synthetic"), snapshot=snapshot, policy=policy, context={},
        generate=generate, evaluation_at=evaluation_at)


async def publish_fixture(repository, **kwargs):
    """Exercise the real publisher with a result from the current analysis service."""
    clock = repository._clock()
    async with repository.pool.acquire() as conn:
        claims = await conn.fetch("select * from public.claims where user_id=$1 and opportunity_id=$2",
                                  kwargs["user_id"], kwargs["opportunity_id"])
        from evaluation_v2.evidence_projection import enriched_claim_evidence_sql
        links = await conn.fetch(enriched_claim_evidence_sql(), kwargs["user_id"], kwargs["opportunity_id"])
    snapshot, _ = snapshot_claims(claims, links, evaluation_at=clock)
    analysis = await analysis_for_snapshot(snapshot=snapshot, policy=kwargs["policy"],
        user_id=kwargs["user_id"], opportunity_id=kwargs["opportunity_id"], evaluation_at=clock,
        pipeline_binding=kwargs.get("pipeline_binding"))
    return await repository._publish(**kwargs, prepared_analysis=analysis, analysis_at=clock)
