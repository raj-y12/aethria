"""Current analysis publication and API provenance with frozen model outputs."""
from copy import deepcopy
import json
import re
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

from agent_trace import build_scout_trace
from evaluation_v2.provenance import PipelineBinding, evaluation_provenance
from investment_analysis.repository import InvestmentAnalysisRepository
from evaluation_v2.service import snapshot_claims
from routers.evaluations import get_current_evaluation
from tests.evaluation_v2.historical_fixtures import CLOCK, CONFIG, DIMENSIONS, _inputs
from evaluation_v2.policy import evaluation_policy_from_compiled


class _Database:
    """Record SQL and round-trip inserted JSON strings like asyncpg defaults."""
    def __init__(self):
        self.rows = {}
        self.queries = []
        self.claims, self.links, self.review = _inputs("A_strong_verified")
        for link in self.links:
            link["artifact_id"] = f"artifact-{link['claim_id']}"
            link["source_uri"] = f"https://evidence.example/{link['claim_id']}"

    def acquire(self):
        return self

    def transaction(self, **_kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def execute(self, sql, *args):
        self.queries.append((sql, args))
        match = re.search(r"insert into public\.(\w+)\s*\((.*?)\)\s*values", sql, re.S)
        if match and match[1] in {"evaluation_runs", "criterion_assessments", "recommendations"}:
            # All columns preceding generated timestamps/status have positional
            # parameters in these three current repository INSERT statements.
            names = [name.strip() for name in match[2].split(",")]
            row = dict(zip(names, args))
            self.rows.setdefault(match[1], []).append(row)

    async def fetchrow(self, sql, *args):
        self.queries.append((sql, args))
        assert "user_id" in sql and args[0] in {"tenant-a", "tenant-b"}
        if "for update of o" in sql:
            return {"service_level": 1, "decision_state": "active", "recommendation_id": None} if args[0] == "tenant-a" else None
        if "join public.evaluation_runs" in sql:
            return next((row for row in reversed(self.rows.get("evaluation_runs", [])) if row["user_id"] == args[0] and row["opportunity_id"] == args[1]), None)
        if "from public.recommendations" in sql:
            return next((row for row in reversed(self.rows.get("recommendations", [])) if row["user_id"] == args[0] and row["evaluation_id"] == args[1]), None)
        raise AssertionError(sql)

    async def fetch(self, sql, *args):
        self.queries.append((sql, args))
        assert "user_id" in sql
        if "from public.claims" in sql:
            return deepcopy(self.claims) if args == ("tenant-a", "opportunity-a") else []
        if "from public.claim_evidence_links" in sql:
            return deepcopy(self.links) if args == ("tenant-a", "opportunity-a") else []
        if "from public.criterion_assessments" in sql:
            return [row for row in self.rows.get("criterion_assessments", []) if row["user_id"] == args[0] and row["evaluation_id"] == args[1]]
        raise AssertionError(sql)


def _policy():
    return evaluation_policy_from_compiled(
        {"policy_version_id": "fixture-policy", "policy_hash": "fixture-hash", "dimensions": {key: {"weight": 20, "criteria": []} for key in DIMENSIONS}},
        partner_rules=json.loads((CONFIG / "partner_rules/v4.json").read_text()),
        rubric=json.loads((CONFIG / "evaluation_rubric/v3.json").read_text()),
    )


def _request(repository, user_id):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(evaluation_repository=repository)), state=SimpleNamespace(user_id=user_id))


@pytest.mark.asyncio
async def test_evidence_to_analysis_and_api_provenance(monkeypatch):
    from unittest.mock import AsyncMock
    from tests.investment_analysis.fixtures import publish_fixture

    database = _Database()
    repository = InvestmentAnalysisRepository(database, clock=lambda: CLOCK)
    monkeypatch.setattr(repository, "inspect_dependencies", AsyncMock(return_value={"state": "current"}))
    scout_trace = build_scout_trace({"references": []}, pipeline_run_id="pipeline-a")
    binding = PipelineBinding(user_id="tenant-a", pipeline_run_id="pipeline-a", pipeline_entry_type="manual_lookup",
        company_id="company-a", scout_run_id=scout_trace["scout_run_id"], evidence_plan_id="evidence-plan-a")
    _, baseline_hash = snapshot_claims(database.claims, database.links, evaluation_at=CLOCK)
    evaluated = await publish_fixture(repository, user_id="tenant-a", opportunity_id="opportunity-a",
        actor_id="tenant-a", trigger_type="manual_lookup", policy=_policy(), pipeline_binding=binding)
    projected = await get_current_evaluation(_request(repository, "tenant-a"), "opportunity-a")
    projected = json.loads(json.dumps(projected))
    provenance = projected["provenance"]
    assert provenance == evaluated["provenance"]
    assert provenance["pipeline_run_id"] == scout_trace["pipeline_run_id"]
    assert provenance["evaluation_run_id"] == evaluated["evaluation_id"]
    assert provenance["scout_run_id"] == scout_trace["scout_run_id"]
    assert provenance["evidence_snapshot_hash"] == baseline_hash
    analysis = evaluated["judgment_audit"]["investment_analysis"]
    assert analysis["reviewer"]["lineage"]["reviewer_run_id"] != analysis["partner"]["lineage"]["partner_run_id"]
    market = next(item for item in provenance["criteria"] if item["criterion"] == "market")
    assert market["score_origin"] == "VALIDATED_REVIEWER_ASSESSMENT"
    assert market["canonical_score"] == 8.0
    claim_id = market["supporting_claim_ids"][0]
    evidence = next(link for link in provenance["evidence_links"] if link["claim_id"] == claim_id)
    assert evidence["source_uri"] == f"https://evidence.example/{claim_id}"
    assert evidence["artifact_id"] in provenance["evidence_artifact_ids"]
    assert claim_id in provenance["claim_ids"]
    assert projected["recommendation"]["recommended_state"] == "monitor"
    assert projected["recommendation"]["confidence"] == analysis["partner"]["judgment"]["confidence"]
    assert await repository.get_current(user_id="tenant-b", opportunity_id="opportunity-a") is None
    with pytest.raises(HTTPException) as denied:
        await get_current_evaluation(_request(repository, "tenant-b"), "opportunity-a")
    assert denied.value.status_code == 404
    evidence_sql = next(sql for sql, _ in database.queries if "from public.claim_evidence_links" in sql)
    for condition in ("c.user_id=l.user_id", "ei.user_id=l.user_id", "ea.user_id=ei.user_id", "l.user_id = $1"):
        assert condition in evidence_sql
    for sql, args in database.queries:
        if "from public.criterion_assessments" in sql or "from public.recommendations" in sql:
            assert "user_id=$1 and evaluation_id=$2" in sql
            assert args == ("tenant-a", evaluated["evaluation_id"])


@pytest.mark.asyncio
async def test_cross_tenant_binding_is_rejected_before_any_storage_access():
    database = _Database()
    with pytest.raises(ValueError, match="tenant mismatch"):
        await InvestmentAnalysisRepository(database).evaluate(user_id="tenant-a", opportunity_id="opportunity-a", actor_id="tenant-a", trigger_type="manual_lookup", policy=_policy(), pipeline_binding=PipelineBinding(user_id="tenant-b"))
    assert database.queries == []


@pytest.mark.parametrize("foreign", ["evaluation", "binding", "criterion", "recommendation"])
def test_cross_tenant_provenance_is_rejected(foreign):
    evaluation = {"user_id": "tenant-a", "model_manifest": {"pipeline_provenance": {"binding": {"user_id": "tenant-a"}}}}
    criterion = {"user_id": "tenant-a", "criterion": "market"}
    recommendation = {"user_id": "tenant-a"}
    targets = {"evaluation": evaluation, "binding": evaluation["model_manifest"]["pipeline_provenance"]["binding"], "criterion": criterion, "recommendation": recommendation}
    targets[foreign]["user_id"] = "tenant-b"
    with pytest.raises(ValueError, match="tenant mismatch"):
        evaluation_provenance(user_id="tenant-a", evaluation=evaluation, criteria=[criterion], recommendation=recommendation)


@pytest.mark.asyncio
async def test_provenance_api_requires_authenticated_user():
    database = _Database()
    with pytest.raises(HTTPException) as denied:
        await get_current_evaluation(_request(InvestmentAnalysisRepository(database), ""), "opportunity-a")
    assert denied.value.status_code == 401
    assert database.queries == []
