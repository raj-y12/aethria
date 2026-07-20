from collections import deque

import pytest

from evaluation_v2.models import (
    CriterionRule,
    DecisionSafetyPolicy,
    EvaluationPolicy,
    EvidenceEligibilityPolicy,
)
from evaluation_v2.repository import EvaluationRepository


class _Connection:
    def __init__(self):
        self.fetchrows = deque([
            {
                "evaluation_id": "evaluation-1",
                "model_manifest": '{"model_id":"gpt-5-nano"}',
                "prompt_manifest": '{"prompt_version":"prompt-a"}',
            },
            {
                "recommendation_id": "recommendation-1",
                "decision_drivers": "[]",
                "principal_risks": '["Retention is unverified."]',
                "mandate_conflicts": "[]",
                "missing_information": '["Net retention"]',
                "change_conditions": '["Verify three-month retention."]',
            },
        ])

    async def fetchrow(self, _sql, *_args):
        return self.fetchrows.popleft()

    async def fetch(self, _sql, *_args):
        return [{"criterion": "market", "missing_evidence": '["retention"]'}]


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Pool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return _Acquire(self.connection)


class _EvaluationConnection:
    def __init__(self):
        self.fetch_queries = []

    def transaction(self, **_kwargs):
        return _Acquire(self)

    async def fetchrow(self, _sql, *_args):
        return {
            "service_level": 1,
            "decision_state": "active",
            "recommendation_id": None,
        }

    async def fetch(self, sql, *_args):
        self.fetch_queries.append(sql)
        if "from public.claims" in sql:
            return [
                {
                    "claim_id": "claim-market",
                    "claim_type": "market",
                    "normalized_value": {"criterion_score": 8.0},
                    "display_text": "A grounded market claim.",
                    "assertion_class": "externally_verified",
                    "status": "current",
                    "confidence": 0.9,
                }
            ]
        if "from public.claim_evidence_links" in sql:
            return [
                {
                    "claim_id": "claim-market",
                    "evidence_item_id": "evidence-market",
                    "relationship": "supports",
                    "support_strength": 0.9,
                    "verification_state": "verified",
                    "source_quality": 0.8,
                    "trust_class": "independent",
                    "untrusted_input": False,
                    "prompt_injection_detected": False,
                }
            ]
        raise AssertionError(f"Unexpected fetch query: {sql}")

    async def execute(self, _sql, *_args):
        return None


def _evaluation_policy():
    return EvaluationPolicy(
        policy_version_id="policy-v1",
        policy_hash="policy-hash-v1",
        rubric_version="rubric-v1",
        partner_rules_version="rules-v1",
        partner_rules_hash="rules-hash-v1",
        criteria=[CriterionRule(criterion="market", claim_types=["market"], weight=1)],
        decision_safety=DecisionSafetyPolicy(
            evidence_eligibility=EvidenceEligibilityPolicy(
                allowed_assertion_classes=["externally_verified"],
                allowed_relationships=["supports"],
            )
        ),
    )


@pytest.mark.asyncio
async def test_current_evaluation_decodes_asyncpg_json_strings_for_api_consumers():
    repository = EvaluationRepository(_Pool(_Connection()))

    result = await repository.get_current(
        user_id="user-a",
        opportunity_id="opportunity-1",
    )

    assert result["evaluation"]["model_manifest"] == {"model_id": "gpt-5-nano"}
    assert result["evaluation"]["prompt_manifest"] == {"prompt_version": "prompt-a"}
    assert result["criteria"][0]["missing_evidence"] == ["retention"]
    assert result["recommendation"]["decision_drivers"] == []
    assert result["recommendation"]["principal_risks"] == ["Retention is unverified."]
    assert result["recommendation"]["change_conditions"] == ["Verify three-month retention."]


@pytest.mark.asyncio
async def test_evaluation_link_projection_joins_grounding_metadata_tenant_safely():
    connection = _EvaluationConnection()
    repository = EvaluationRepository(_Pool(connection))

    await repository.evaluate(
        user_id="user-a",
        opportunity_id="opportunity-1",
        actor_id="actor-a",
        trigger_type="manual",
        policy=_evaluation_policy(),
    )

    link_query = next(
        query for query in connection.fetch_queries
        if "from public.claim_evidence_links" in query
    )
    normalized = " ".join(link_query.split()).lower()
    assert (
        "join public.evidence_items ei on ei.user_id=l.user_id "
        "and ei.evidence_item_id=l.evidence_item_id"
    ) in normalized
    assert (
        "join public.evidence_artifacts ea on ea.user_id=ei.user_id "
        "and ea.artifact_id=ei.artifact_id"
    ) in normalized
    assert "where l.user_id = $1 and c.opportunity_id = $2" in normalized
    assert "ei.verification_state" in normalized
    assert "ei.source_quality" in normalized
    assert "ea.trust_class" in normalized
    assert "ea.untrusted_input" in normalized
    assert "ea.prompt_injection_detected" in normalized
