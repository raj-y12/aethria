import pytest
from types import SimpleNamespace

from api import _list_projection_to_frontend
from startups import StartupRepository, _queue_reasons_for_startup


class _Connection:
    def __init__(self):
        self.sql = ""

    async def fetch(self, sql, *args):
        self.sql = sql
        return [
            {
                "startup_id": "startup-1",
                "human_resolution": '{"decision":"NO","resolved_at":"2026-08-12T10:00:00+00:00"}',
            }
        ]


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
async def test_list_projection_preserves_human_resolution_for_portfolio_history():
    connection = _Connection()

    rows = await StartupRepository(_Pool(connection)).list_projection("user-a")

    assert "human_resolution" in connection.sql
    assert rows[0]["human_resolution"] == {
        "decision": "NO",
        "resolved_at": "2026-08-12T10:00:00+00:00",
    }


def test_list_projection_maps_institutional_monitor_to_legacy_maybe():
    projected = _list_projection_to_frontend(
        {
            "startup_id": "startup-monitor",
            "human_resolution": {
                "decision": "MONITOR",
                "notes": "Keep watching.",
            },
        }
    )

    assert projected["human_resolution"] == {
        "decision": "MAYBE",
        "notes": "Keep watching.",
    }


def test_list_projection_never_exposes_legacy_reviewer_score_as_priority():
    projected = _list_projection_to_frontend(
        {
            "startup_id": "startup-legacy-score",
            "display_name": "Legacy Score Co",
            "list_verdict": "STRONG",
            "list_score": 9.0,
            "short_summary": "Historical reviewer output.",
        }
    )

    assert projected["review"].get("overall_score") is None
    assert projected["review"].get("aggregate_score") is None
    assert projected["priority_reason"].startswith("Priority pending")


def test_list_projection_rebuilds_stored_legacy_numeric_priority():
    projected = _list_projection_to_frontend(
        {
            "startup_id": "startup-stale-priority",
            "display_name": "Stale Priority Co",
            "list_verdict": "STRONG",
            "priority_reason": "Priority 90 · Reviewed · B2B SaaS",
            "list_sector": "B2B SaaS",
        }
    )

    assert projected["priority_reason"] == "Priority pending · Reviewer output ready for partner judgement · B2B SaaS"


def test_postgres_queue_reason_never_reconstructs_legacy_reviewer_score():
    startup = SimpleNamespace(
        scout_info=SimpleNamespace(sector="B2B SaaS"),
        review_info=SimpleNamespace(
            market_score=9.0,
            product_score=9.0,
            technical_score=9.0,
            execution_score=9.0,
        ),
        partner_info=None,
        human_resolution=None,
    )

    _, priority_reason = _queue_reasons_for_startup(startup)

    assert priority_reason == "Priority pending · Reviewed · B2B SaaS"


@pytest.mark.parametrize('mapper', [pytest.param(_list_projection_to_frontend, id='list'), pytest.param(__import__('api')._backend_to_frontend, id='detail')])
def test_current_analysis_preserves_judgment_and_operational_action(mapper):
    row = {
        'startup_id': 'current',
        'partner_info': {'recommendation': 'INVEST', 'decision_rationale': 'Stale projection'},
        'queue_reason': 'Partner recommends invest.',
        'current_analysis': {
            'evaluation_id': 'evaluation-current', 'opportunity_id': 'opportunity-current',
            'reviewer_summary': 'Current evidence assessment',
            'partner': {
                'judgment': {'action': 'ADVANCE', 'rationale': ['Grounded upside'], 'confidence': .8,
                             'investment_case': 'Case', 'principal_risks': ['Risk'], 'next_steps': ['Check retention']},
                'operational_action': 'MORE_DILIGENCE', 'constraints': ['Evidence missing'],
                'human_review_required': True,
            },
        },
    }
    result = mapper(row)
    assert result['partner']['judgment_action'] == 'ADVANCE'
    assert result['partner']['operational_action'] == 'MORE_DILIGENCE'
    assert result['partner']['recommendation'] == 'MONITOR'  # unchanged compatibility enum
    assert result['partner']['decision_rationale'] == 'Grounded upside\nEvidence missing'
    assert result['review']['overall_summary'] == 'Current evidence assessment'
    assert result['current_analysis']['evaluation_id'] == 'evaluation-current'
    assert result['queue_reason'] == 'Human ruling required.'


@pytest.mark.asyncio
async def test_current_analysis_list_join_is_tenant_scoped_and_paginated():
    connection = _Connection()
    await StartupRepository(_Pool(connection)).list_projection('user-a', limit=2, offset=10)
    assert 'o.user_id=startups.user_id' in connection.sql
    assert 'e.user_id=o.user_id' in connection.sql
    assert 'e.evaluation_id=o.current_evaluation_id' in connection.sql
    assert 'e.opportunity_id=o.opportunity_id' in connection.sql
    assert 'limit $2 offset $3' in connection.sql
    assert 'when count(*) = 1' in connection.sql
    assert "startups.agent_trace #>> '{reviewer,evaluation_run_id}'" in connection.sql
    assert "startups.agent_trace #>> '{partner,provenance,evaluation_run_id}'" in connection.sql
    assert "'{investment_analysis,validation}'" in connection.sql


@pytest.mark.asyncio
async def test_published_analysis_reads_and_shadow_mismatch_on_postgres(monkeypatch):
    import os
    if not os.getenv('TEST_DATABASE_URL'):
        pytest.skip('TEST_DATABASE_URL required')
    from investment_analysis.repository import InvestmentAnalysisRepository
    from tests.evaluation_v2.test_phase0_provenance_postgres import test_postgres_roundtrip_and_tenant_isolation as walk_pipeline
    original = InvestmentAnalysisRepository._publish
    seen = []

    async def publish(repository, **kwargs):
        result = await original(repository, **kwargs)
        uid = kwargs['user_id']
        async with repository.pool.acquire() as connection:
            row = await connection.fetchrow('select legacy_startup_id from opportunities where user_id=$1 and opportunity_id=$2', uid, kwargs['opportunity_id'])
            startup_id = str(row['legacy_startup_id'])
            startups = StartupRepository(repository.pool)
            detail = await startups.get_startup(uid, startup_id)
            page = await startups.list_projection(uid, limit=1)
            memo = await startups.get_memo_projection(uid, startup_id)
            analysis = detail['current_analysis']
            assert analysis['evaluation_id'] == str(result['evaluation_id'])
            assert page[0]['current_analysis'] == analysis == memo['current_analysis']
            assert await startups.get_startup('foreign-tenant', startup_id) is None
            trace = await connection.fetchval('select agent_trace from startups where user_id=$1 and startup_id=$2', uid, startup_id)
            # A SHADOW or otherwise unpublished run must not replace the visible
            # judgement merely because it became the current evaluation.
            await connection.execute("update startups set agent_trace=jsonb_set(agent_trace, '{reviewer,evaluation_run_id}', '\"different-run\"') where user_id=$1 and startup_id=$2", uid, startup_id)
            assert (await startups.get_startup(uid, startup_id))['current_analysis'] is None
            assert (await startups.list_projection(uid, limit=1))[0]['current_analysis'] is None
            await connection.execute('update startups set agent_trace=$3::jsonb where user_id=$1 and startup_id=$2', uid, startup_id, trace)
            seen.append(analysis)
        return result

    monkeypatch.setattr(InvestmentAnalysisRepository, '_publish', publish)
    await walk_pipeline()
    assert seen
