from copy import deepcopy
from datetime import timedelta

import pytest

from investment_analysis.dependencies import inspect_analysis_dependencies
from tests.investment_analysis.test_authority import run_case
from tests.evaluation_v2.historical_fixtures import _inputs, CLOCK
from tests.evaluation_v2.test_phase0_provenance_e2e import _policy
from evaluation_v2.service import snapshot_claims


@pytest.mark.asyncio
@pytest.mark.parametrize("change,reason", [(None, None), ("evidence", "evidence_changed"),
    ("thesis", "thesis_changed"), ("policy", "policy_changed"), ("age", "evidence_support_changed")])
async def test_dependency_inspection_marks_history_stale_without_rewriting_it(change, reason):
    analysis, _ = await run_case()
    before = analysis.model_dump(mode="json")
    claims, links, _ = _inputs("A_strong_verified")
    snapshot, _ = snapshot_claims(claims, links, evaluation_at=CLOCK)
    prior_snapshot = deepcopy(snapshot)
    policy, thesis, clock = _policy(), None, CLOCK
    if change == "evidence":
        snapshot[0]["display_text"] = "Corrected factual statement"
    if change == "thesis":
        thesis = "new-thesis"
    if change == "policy":
        policy = policy.model_copy(update={"policy_hash": "new-policy"})
    if change == "age":
        clock += timedelta(days=1000)
    status = inspect_analysis_dependencies(user_id="tenant", opportunity_id="opportunity",
        analysis=analysis, snapshot=snapshot, prior_snapshot=prior_snapshot, policy=policy, thesis_version_id=thesis, evaluation_at=clock)
    assert status.state == ("current" if reason is None else "stale")
    assert (reason in status.reasons) if reason else not status.reasons
    assert analysis.model_dump(mode="json") == before


@pytest.mark.asyncio
async def test_dependency_inspection_rejects_foreign_lineage():
    analysis, _ = await run_case()
    with pytest.raises(ValueError, match="tenant/opportunity"):
        inspect_analysis_dependencies(user_id="another-fund", opportunity_id="opportunity",
            analysis=analysis, snapshot=[], prior_snapshot=[], policy=_policy(), thesis_version_id=None, evaluation_at=CLOCK)
