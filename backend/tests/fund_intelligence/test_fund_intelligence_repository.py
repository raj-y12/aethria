import json
from collections import deque

import pytest

from fund_intelligence.repository import FundIntelligenceRepository


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Connection:
    def __init__(self, fetchrows):
        self.fetchrows = deque(fetchrows)
        self.calls = []

    def transaction(self):
        return _Transaction()

    async def fetchrow(self, sql, *args):
        self.calls.append(("fetchrow", sql, args))
        return self.fetchrows.popleft() if self.fetchrows else None

    async def execute(self, sql, *args):
        self.calls.append(("execute", sql, args))
        return "OK"


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


def _proposal(**overrides):
    row = {
        "policy_proposal_id": "proposal-1",
        "status": "ready_for_review",
        "proposed_policy_patch": json.dumps({"target": "review_guidance"}),
    }
    row.update(overrides)
    return row


@pytest.mark.asyncio
async def test_acceptance_requires_a_current_preview_for_the_exact_policy_hash():
    connection = _Connection([_proposal(), None])
    repository = FundIntelligenceRepository(_Pool(connection))

    with pytest.raises(RuntimeError, match="exact resulting policy"):
        await repository.review_proposal(
            user_id="user-a",
            policy_proposal_id="proposal-1",
            actor_id="user-a",
            action="accept",
            rationale="Repeated attributable pattern.",
            resulting_fund_config={"scoringWeights": [{"key": "market", "weight": 30}]},
            policy_hash="hash-1",
            config_hash="config-1",
        )

    assert not any(
        "insert into public.governed_policy_versions" in sql.lower()
        for _, sql, _ in connection.calls
    )


@pytest.mark.asyncio
async def test_accepted_draft_persists_the_exact_previewed_config_and_hash():
    version = {
        "governed_policy_version_id": "version-1",
        "status": "draft",
        "policy_patch": json.dumps({"scoringWeights": [{"key": "market", "weight": 30}]}),
        "policy_hash": "hash-1",
    }
    reviewed = _proposal(status="accepted")
    connection = _Connection(
        [
            _proposal(),
            {"estimated_effect": json.dumps({"policy_hash": "hash-1", "config_hash": "config-1"})},
            version,
            reviewed,
        ]
    )
    repository = FundIntelligenceRepository(_Pool(connection))

    result = await repository.review_proposal(
        user_id="user-a",
        policy_proposal_id="proposal-1",
        actor_id="user-a",
        action="edit_and_accept",
        rationale="Repeated attributable pattern.",
        resulting_fund_config={"scoringWeights": [{"key": "market", "weight": 30}]},
        policy_hash="hash-1",
        config_hash="config-1",
    )

    assert result["policy_version"]["policy_patch"] == {
        "scoringWeights": [{"key": "market", "weight": 30}]
    }
    insert = next(
        call for call in connection.calls
        if "insert into public.governed_policy_versions" in call[1].lower()
    )
    assert json.loads(insert[2][3]) == {
        "scoringWeights": [{"key": "market", "weight": 30}]
    }
    assert insert[2][4] == "hash-1"


@pytest.mark.asyncio
async def test_settings_publication_commits_governed_authority_and_outbox_together():
    published = {
        "governed_policy_version_id": "version-settings-1",
        "user_id": "user-a",
        "policy_proposal_id": None,
        "publication_source": "settings",
        "policy_patch": json.dumps({"scoringWeights": []}),
        "policy_hash": "hash-settings",
        "status": "published",
    }
    connection = _Connection([published])
    repository = FundIntelligenceRepository(_Pool(connection))

    result = await repository.publish_settings_policy(
        user_id="user-a",
        actor_id="user-a",
        fund_config={"scoringWeights": []},
        policy_hash="hash-settings",
    )

    assert result["publication_source"] == "settings"
    sql = "\n".join(call[1].lower() for call in connection.calls)
    assert "pg_advisory_xact_lock" in sql
    assert "publication_source" in sql
    assert "governed_policy_version.published" in str(connection.calls)
