import os
from uuid import uuid4

import pytest

from semantic_evaluation.models import (
    ChoiceProbability,
    SemanticEvaluationRecord,
    SemanticEvaluationRolloutMode,
    SemanticEvaluationStatus,
    SemanticEvaluationType,
)
from semantic_evaluation.repository import SemanticEvaluationRepository


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is required for semantic_evaluation PostgreSQL contracts",
)


def _record(**overrides) -> SemanticEvaluationRecord:
    defaults = dict(
        evaluation_id=str(uuid4()),
        user_id=f"semeval-user-{uuid4()}",
        pipeline_run_id="run-1",
        startup_id="startup-1",
        evaluation_type=SemanticEvaluationType.CLAIM_SUPPORT,
        evaluation_version="v1",
        criteria_version="abc12345",
        rollout_mode=SemanticEvaluationRolloutMode.SHADOW,
        provider="mock",
        model="mock-v1",
        status=SemanticEvaluationStatus.SUCCESS,
        input_digest="deadbeef",
        claim_ids=["claim-1"],
        source_ids=["source-1"],
        selected_answer="supports",
        confidence=0.91,
        distribution=[
            ChoiceProbability(label="supports", probability=0.91),
            ChoiceProbability(label="contradicts", probability=0.09),
        ],
        latency_ms=12.5,
        tokens=0,
        estimated_cost_usd=0.0,
    )
    defaults.update(overrides)
    return SemanticEvaluationRecord(**defaults)


@pytest.mark.asyncio
async def test_record_persists_full_distribution_and_is_tenant_scoped():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=2)
    repository = SemanticEvaluationRepository(pool)
    entry = _record()
    other_user_entry = _record(user_id=f"semeval-other-{uuid4()}")
    try:
        await repository.record(entry)
        await repository.record(other_user_entry)

        rows = await repository.list_for_user(user_id=entry.user_id)
        assert len(rows) == 1
        row = rows[0]
        assert row["evaluation_id"] == entry.evaluation_id
        assert row["status"] == "success"
        assert row["rollout_mode"] == "shadow"
        assert row["selected_answer"] == "supports"
        assert row["confidence"] == pytest.approx(0.91)
        import json
        distribution = row["distribution"] if isinstance(row["distribution"], list) else json.loads(row["distribution"])
        assert distribution == [{"label": "supports", "probability": 0.91}, {"label": "contradicts", "probability": 0.09}]

        other_rows = await repository.list_for_user(user_id=other_user_entry.user_id)
        assert len(other_rows) == 1
        assert other_rows[0]["evaluation_id"] == other_user_entry.evaluation_id
    finally:
        async with pool.acquire() as connection:
            await connection.execute(
                "delete from public.semantic_evaluations where user_id = any($1::text[])",
                [entry.user_id, other_user_entry.user_id],
            )
        await pool.close()


@pytest.mark.asyncio
async def test_evaluation_type_check_constraint_rejects_unknown_type():
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=1)
    try:
        async with pool.acquire() as connection:
            with pytest.raises(asyncpg.CheckViolationError):
                await connection.execute(
                    """insert into public.semantic_evaluations
                       (user_id, evaluation_type, evaluation_version, criteria_version,
                        rollout_mode, provider, status, input_digest)
                       values ($1, 'not_a_real_type', 'v1', 'abc', 'shadow', 'mock', 'success', 'd')""",
                    f"semeval-invalid-{uuid4()}",
                )
    finally:
        await pool.close()
