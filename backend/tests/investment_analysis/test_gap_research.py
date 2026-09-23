from copy import deepcopy

import pytest

from evaluation_v2.service import snapshot_claims
from investment_analysis.models import ReviewerDraft, PartnerDraft
from investment_analysis.service import analyze
from pipeline_contracts.models import Lineage, Identity
from tests.evaluation_v2.historical_fixtures import _inputs, CLOCK
from tests.evaluation_v2.test_phase0_provenance_e2e import _policy


@pytest.mark.asyncio
@pytest.mark.parametrize("new_evidence", [False, True])
async def test_targeted_research_is_bounded_and_partner_only_reads_completed_review(new_evidence):
    claims, links, _ = _inputs("A_strong_verified")
    snapshot, _ = snapshot_claims(claims, links, evaluation_at=CLOCK)
    events = []

    async def generate(stage, prompt, payload, schema):
        events.append(stage)
        if stage == "reviewer":
            return ReviewerDraft(overall_assessment="Updated evidence reviewed" if payload.get("research_attempted") else "Retention needs verification",
                                 research_questions=["What are the company's independently reported retention cohorts?"])
        assert payload["review"]["overall_assessment"] == ("Updated evidence reviewed" if new_evidence else "Retention needs verification")
        return PartnerDraft(action="MORE_DILIGENCE", confidence=0.5,
                            investment_case="Potential demand", rationale=["Verify remaining uncertainty"])

    async def research(questions):
        events.append("research")
        assert len(questions) == 1
        updated = deepcopy(snapshot)
        if new_evidence:
            updated[0]["display_text"] = "An independent source reports retention cohorts remain undisclosed."
        return updated, CLOCK

    result = await analyze(user_id="fund-a", lineage=Lineage(user_id="fund-a"), identity=Identity(name="Acme"),
                           snapshot=snapshot, policy=_policy(), context={}, generate=generate,
                           evaluation_at=CLOCK, research=research)
    assert events == (["reviewer", "research", "reviewer", "partner"] if new_evidence else ["reviewer", "research", "partner"])
    assert result.context_snapshot["targeted_research"]["new_evidence"] is new_evidence
    assert result.reviewer.diligence_priorities
