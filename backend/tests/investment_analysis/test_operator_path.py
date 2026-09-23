"""Operator actions converge on the shared evaluator, including Partner-only work."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from routers.meta import post_startup_triage_override, TriageOverrideBody


@pytest.mark.asyncio
@pytest.mark.parametrize("stage,scope", [("review", "full"), ("decide", "partner")])
async def test_operator_override_uses_shared_analysis(monkeypatch, stage, scope):
    identity = SimpleNamespace(get_opportunity_by_legacy_projection=AsyncMock(
        return_value=SimpleNamespace(opportunity_id="opportunity")))
    request = SimpleNamespace(state=SimpleNamespace(user_id="tenant"),
                              app=SimpleNamespace(state=SimpleNamespace(identity_repository=identity)))
    monkeypatch.setattr("routers.meta.enforce_rate_limits", AsyncMock(return_value=None))
    refresh = AsyncMock(return_value={"evaluation": {"evaluation_id": "completed"}})
    monkeypatch.setattr("routers.evaluations.evaluate_opportunity", refresh)
    result = await post_startup_triage_override(request, "startup", TriageOverrideBody(stage=stage))
    identity.get_opportunity_by_legacy_projection.assert_awaited_once_with(user_id="tenant", legacy_startup_id="startup")
    refresh.assert_awaited_once_with(request, "opportunity", scope=scope)
    assert result == {"success": True, "startup_id": "startup", "stage": stage}
