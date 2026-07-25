from __future__ import annotations

import json
from typing import Any, Optional

from tenant_context import require_user_id
from triage.models import TriageAssessment


class TriageRepository:
    def __init__(self, pool: Any):
        self.pool = pool

    async def create(self, assessment: TriageAssessment) -> TriageAssessment:
        uid = require_user_id(assessment.user_id, context="TriageRepository.create")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                insert into public.triage_assessments (
                  assessment_id,user_id,opportunity_id,disposition,reasons,observation_ids,
                  missing_information,thesis_version_id,policy_version_id,trigger,priority,confidence
                ) values ($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7::jsonb,$8,$9,$10,$11,$12)
                on conflict (user_id, assessment_id) do nothing returning *
                """,
                assessment.assessment_id, uid, assessment.opportunity_id,
                assessment.disposition.value, json.dumps(assessment.reasons),
                json.dumps(assessment.observation_ids), json.dumps(assessment.missing_information),
                assessment.thesis_version_id, assessment.policy_version_id, assessment.trigger,
                assessment.priority, assessment.confidence,
            )
        if row is None:
            return assessment
        return assessment

    async def get_latest(self, *, user_id: str, opportunity_id: str) -> Optional[dict[str, Any]]:
        uid = require_user_id(user_id, context="TriageRepository.get_latest")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "select * from public.triage_assessments where user_id=$1 and opportunity_id=$2 order by created_at desc limit 1",
                uid, opportunity_id,
            )
        return dict(row) if row else None
