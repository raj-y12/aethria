"""Append-only PostgreSQL repository for semantic evaluation observations.

Every call is a plain insert — there is no update path. See
`db/migrations/20260917120000_semantic_evaluations.sql`.
"""
from __future__ import annotations

import json
from typing import Any

from tenant_context import require_user_id

from semantic_evaluation.models import SemanticEvaluationRecord


class SemanticEvaluationRepository:
    def __init__(self, pool: Any):
        self.pool = pool

    async def record(self, entry: SemanticEvaluationRecord) -> None:
        uid = require_user_id(entry.user_id, context="SemanticEvaluationRepository.record")
        await self.pool.execute(
            """
            insert into public.semantic_evaluations
              (evaluation_id, user_id, pipeline_run_id, workflow_run_id, startup_id, opportunity_id,
               evaluation_type, evaluation_version, criteria_version, rollout_mode, provider, model,
               provider_model_version, status, input_digest, claim_ids, source_ids, selected_answer,
               confidence, distribution, latency_ms, tokens, estimated_cost_usd, error)
            values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24)
            """,
            entry.evaluation_id, uid, entry.pipeline_run_id, entry.workflow_run_id,
            entry.startup_id, entry.opportunity_id, entry.evaluation_type.value,
            entry.evaluation_version, entry.criteria_version, entry.rollout_mode.value,
            entry.provider, entry.model, entry.provider_model_version, entry.status.value,
            entry.input_digest, json.dumps(entry.claim_ids), json.dumps(entry.source_ids),
            entry.selected_answer, entry.confidence,
            json.dumps([item.model_dump(mode="json") for item in entry.distribution]),
            entry.latency_ms, entry.tokens, entry.estimated_cost_usd, entry.error,
        )

    async def list_for_user(
        self, *, user_id: str, evaluation_type: str | None = None, limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Read path for offline comparison/calibration tooling only — never
        for authoritative Scout/Reviewer/Partner behaviour."""
        uid = require_user_id(user_id, context="SemanticEvaluationRepository.list_for_user")
        if evaluation_type:
            rows = await self.pool.fetch(
                """
                select * from public.semantic_evaluations
                where user_id=$1 and evaluation_type=$2
                order by created_at desc limit $3
                """,
                uid, evaluation_type, limit,
            )
        else:
            rows = await self.pool.fetch(
                """
                select * from public.semantic_evaluations
                where user_id=$1
                order by created_at desc limit $2
                """,
                uid, limit,
            )
        return [dict(row) for row in rows]
