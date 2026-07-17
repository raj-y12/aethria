from collections import deque

import pytest

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
