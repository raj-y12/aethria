from tests.investment_analysis.fixtures import publish_fixture
from collections import deque
from datetime import datetime, timezone
import json
from types import SimpleNamespace

import pytest

from evaluation_v2.models import (
    CriterionRule,
    DecisionSafetyPolicy,
    EvaluationPolicy,
    EvidenceEligibilityPolicy,
)
from investment_analysis.repository import EvaluationLifecycleError, InvestmentAnalysisRepository


class _ProjectionRepository:
    def __init__(self):
        self.receipts = {}
        self.patch = None

    async def get_projection_receipt(self, *, user_id, event_id, consumer):
        return self.receipts.get((user_id, event_id, consumer))

    async def apply_legacy_projection(self, *, user_id, event_id, consumer, patch, **_kwargs):
        self.patch = patch.patch
        receipt = SimpleNamespace(receipt_id=f"receipt:{event_id}")
        self.receipts[(user_id, event_id, consumer)] = receipt
        return receipt


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
    def __init__(self, *, decision_state="active", workflow_state=None):
        self.fetch_queries = []
        self.execute_calls = []
        self._decision_state = decision_state
        self._workflow_state = workflow_state

    def transaction(self, **_kwargs):
        return _Acquire(self)

    async def fetchrow(self, _sql, *_args):
        return {
            "service_level": 1,
            "decision_state": self._decision_state,
            "workflow_state": self._workflow_state,
            "legacy_startup_id": "5fa9d11a-5f21-45c1-9ad3-d755990c3164",
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
                    "evidence_effective_at": "2026-07-01T00:00:00+00:00",
                    "evidence_expires_at": "2026-08-01T00:00:00+00:00",
                    "artifact_effective_at": "2026-07-01T00:00:00+00:00",
                    "retrieved_at": "2026-07-01T01:00:00+00:00",
                }
            ]
        raise AssertionError(f"Unexpected fetch query: {sql}")

    async def execute(self, _sql, *_args):
        self.execute_calls.append((_sql, _args))
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
                require_verified_evidence=True,
                min_support_strength=0.5,
                min_source_quality=0.4,
                blocked_trust_classes=["model", "unknown"],
            ),
            critical_risk_claim_types=["critical_risk"],
            hard_exclusion_claim_types=["mandate_exclusion"],
            claim_confidence={
                "minimum_eligible": 0.5,
                "full_confidence_at": 0.8,
                "score_cap_below_full_confidence": 7.99,
                "recommendation_confidence_cap_below_full_confidence": 0.6,
                "zero_confidence_ineligible": True,
            },
            freshness={
                "max_age_days": 180,
                "expired_action": "ineligible",
                "undated_action": "ineligible",
                "future_dated_action": "ineligible",
                "stale_action": "cap",
                "stale_score_cap": 7.99,
                "stale_confidence_cap": 0.6,
            },
            source_quality={
                "full_confidence_at": 0.8,
                "score_cap_below_full_quality": 7.99,
                "recommendation_confidence_cap_below_full_quality": 0.65,
            },
        ),
        advance_threshold=8,
        pass_threshold=6,
        advance_comparison="greater_than_or_equal",
        pass_comparison="less_than",
        minimum_scored_weight=0.5,
        hard_exclusion_claim_types=["mandate_exclusion"],
    )


@pytest.mark.asyncio
async def test_current_evaluation_decodes_asyncpg_json_strings_for_api_consumers():
    repository = InvestmentAnalysisRepository(_Pool(_Connection()))

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
    clock_calls = []

    def clock():
        clock_calls.append(True)
        return datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)

    repository = InvestmentAnalysisRepository(_Pool(connection), clock=clock)

    await publish_fixture(repository,
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
    assert "ei.effective_at as evidence_effective_at" in normalized
    assert "ei.expires_at as evidence_expires_at" in normalized
    assert "ea.trust_class" in normalized
    assert "ea.untrusted_input" in normalized
    assert "ea.prompt_injection_detected" in normalized
    assert "ea.effective_at as artifact_effective_at" in normalized
    assert "ea.retrieved_at" in normalized
    assert len(clock_calls) == 1
    evaluation_insert = next(
        (sql, args)
        for sql, args in connection.execute_calls
        if "insert into public.evaluation_runs" in sql
    )
    evaluation_sql, evaluation_args = evaluation_insert
    assert "evidence_materiality_digest" in evaluation_sql
    snapshot = json.loads(evaluation_args[7])
    assert snapshot[0]["evaluation_at_snapshot"] == "2026-07-20T12:00:00+00:00"
    relationship = snapshot[0]["evidence_relationships"][0]
    assert relationship["evidence_effective_at"] == "2026-07-01T00:00:00+00:00"
    assert relationship["evidence_expires_at"] == "2026-08-01T00:00:00+00:00"
    assert relationship["artifact_effective_at"] == "2026-07-01T00:00:00+00:00"
    assert relationship["retrieved_at"] == "2026-07-01T01:00:00+00:00"
    _, outbox_args = next(
        (sql, args)
        for sql, args in connection.execute_calls
        if "insert into public.domain_outbox" in sql
    )
    outbox_payload = json.loads(outbox_args[-1])
    assert outbox_payload["legacy_startup_id"] == "5fa9d11a-5f21-45c1-9ad3-d755990c3164"
    assert outbox_payload["compatibility_reason"]


@pytest.mark.asyncio
async def test_evaluate_refuses_to_silently_reopen_an_invested_opportunity():
    """Regression (audit HIGH-H7): evaluate()'s re-entry guard only checked
    decision_state == "archived" -- a re-triggered lookup/dispatch on an
    already-INVESTED opportunity could silently overwrite
    current_recommendation_id and flip workflow_state back to
    "ruling_pending", as if the investment decision never happened."""
    connection = _EvaluationConnection(decision_state="invested")
    repository = InvestmentAnalysisRepository(_Pool(connection))

    with pytest.raises(EvaluationLifecycleError, match="Invested opportunities"):
        await publish_fixture(repository,
            user_id="user-a",
            opportunity_id="opportunity-1",
            actor_id="actor-a",
            trigger_type="manual",
            policy=_evaluation_policy(),
        )


@pytest.mark.asyncio
async def test_evaluate_refuses_to_silently_reopen_a_completed_workflow():
    """Regression (audit HIGH-H7): same as above but via workflow_state
    (a separate column from decision_state) -- "completed" and "monitoring"
    are the workflow-layer's own terminal states."""
    connection = _EvaluationConnection(workflow_state="completed")
    repository = InvestmentAnalysisRepository(_Pool(connection))

    with pytest.raises(EvaluationLifecycleError, match="completed workflow"):
        await publish_fixture(repository,
            user_id="user-a",
            opportunity_id="opportunity-1",
            actor_id="actor-a",
            trigger_type="manual",
            policy=_evaluation_policy(),
        )


@pytest.mark.asyncio
async def test_actual_evaluation_outbox_payload_projects_to_a_receipted_legacy_patch():
    from authority.projection import AuthorityProjectionConsumer

    connection = _EvaluationConnection()
    await publish_fixture(InvestmentAnalysisRepository(_Pool(connection)),
        user_id="user-a",
        opportunity_id="opportunity-1",
        actor_id="actor-a",
        trigger_type="manual",
        policy=_evaluation_policy(),
    )
    _, args = next(
        (sql, args)
        for sql, args in connection.execute_calls
        if "insert into public.domain_outbox" in sql
    )
    projection_repository = _ProjectionRepository()
    receipt = await AuthorityProjectionConsumer(projection_repository).apply(
        user_id="user-a",
        event_id=args[0],
        aggregate_type="evaluation",
        aggregate_id=args[2],
        event_type=args[3],
        payload=json.loads(args[-1]),
    )

    assert receipt.receipt_id == f"receipt:{args[0]}"
    assert projection_repository.patch["review_info"]["canonical_evaluation_id"]
    assert projection_repository.patch["partner_info"]["recommendation"] == "MONITOR"


@pytest.mark.asyncio
async def test_evaluation_projection_preserves_unscored_criterion_as_null():
    connection = _EvaluationConnection()
    repository = InvestmentAnalysisRepository(_Pool(connection))
    policy = _evaluation_policy().model_copy(deep=True)
    policy.criteria.append(
        CriterionRule(criterion="execution", claim_types=["execution"], weight=0.5)
    )
    policy.criteria[0].weight = 0.5

    result = await publish_fixture(repository,
        user_id="user-a",
        opportunity_id="opportunity-1",
        actor_id="actor-a",
        trigger_type="manual",
        policy=policy,
    )

    execution = next(
        criterion
        for criterion in result["criteria"]
        if criterion["criterion"] == "execution"
    )
    assert execution["score"] is None
    assessment_inserts = [
        args
        for sql, args in connection.execute_calls
        if "insert into public.criterion_assessments" in sql
    ]
    execution_insert = next(args for args in assessment_inserts if args[3] == "execution")
    assert execution_insert[4] is None
