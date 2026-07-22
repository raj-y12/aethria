from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from pipeline_execution import PipelineExecutionResult


@pytest.mark.asyncio
async def test_reprocess_route_delegates_the_only_gate_to_typed_runner(monkeypatch):
    import routers.fund_thesis as route

    calls = []

    async def run(user_id, **kwargs):
        calls.append((user_id, kwargs))
        return PipelineExecutionResult.completed(
            code="reprocess_dry_run_completed",
            detail="Eligibility calculated.",
            metadata={"dry_run": True, "eligible": 3},
        )

    monkeypatch.setattr(route, "_require_supabase_for_thesis", lambda: None)
    monkeypatch.setattr(route, "reprocess_startups_missing_fund_thesis", run)
    monkeypatch.setattr(
        route,
        "get_active_thesis",
        lambda *_args, **_kwargs: pytest.fail("route must not duplicate the thesis gate"),
    )
    request = SimpleNamespace(
        state=SimpleNamespace(user_id="user-a"),
        app=SimpleNamespace(
            state=SimpleNamespace(fund_intelligence_repository="governed-repository")
        ),
    )

    response = await route.api_post_fund_thesis_reprocess_missing(
        request, dry_run=True
    )

    assert response == {"dry_run": True, "eligible": 3}
    assert calls == [
        (
            "user-a",
            {
                "dry_run": True,
                "fund_intelligence_repository": "governed-repository",
            },
        )
    ]


@pytest.mark.asyncio
async def test_reprocess_route_preserves_actionable_blocked_payload(monkeypatch):
    import routers.fund_thesis as route

    async def run(*_args, **_kwargs):
        return PipelineExecutionResult.blocked(
            code="published_policy_required",
            detail="A published policy is required.",
            recovery_action="Publish the policy in Settings.",
        )

    monkeypatch.setattr(route, "_require_supabase_for_thesis", lambda: None)
    monkeypatch.setattr(route, "reprocess_startups_missing_fund_thesis", run)
    request = SimpleNamespace(
        state=SimpleNamespace(user_id="user-a"),
        app=SimpleNamespace(state=SimpleNamespace(fund_intelligence_repository=None)),
    )

    with pytest.raises(HTTPException) as exc:
        await route.api_post_fund_thesis_reprocess_missing(request, dry_run=False)

    assert exc.value.status_code == 409
    assert exc.value.detail == {
        "code": "published_policy_required",
        "detail": "A published policy is required.",
        "recovery_action": "Publish the policy in Settings.",
    }
