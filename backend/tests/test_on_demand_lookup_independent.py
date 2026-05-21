from types import SimpleNamespace

import pytest

from pipeline_runner import run_on_demand_lookup


class _FakeScoutEngine:
    active_thesis = "unset"

    def __init__(self, *args, **kwargs):
        type(self).active_thesis = kwargs.get("active_thesis", "missing")

    async def run_named_lookup(self, **kwargs):
        return "startup-1"


class _FakeReviewerEngine:
    active_thesis = "unset"
    use_resource_fund_thesis_fallback = "unset"

    def __init__(self, *args, **kwargs):
        type(self).active_thesis = kwargs.get("active_thesis", "missing")
        type(self).use_resource_fund_thesis_fallback = kwargs.get(
            "use_resource_fund_thesis_fallback",
            "missing",
        )

    async def run_startup(self, *args, **kwargs):
        return True


class _FakePartnerEngine:
    fund_thesis = "unset"
    use_resource_fund_thesis_fallback = "unset"

    def __init__(self, *args, **kwargs):
        type(self).fund_thesis = kwargs.get("fund_thesis", "missing")
        type(self).use_resource_fund_thesis_fallback = kwargs.get(
            "use_resource_fund_thesis_fallback",
            "missing",
        )

    async def run_startup(self, *args, **kwargs):
        return True


@pytest.mark.asyncio
async def test_on_demand_lookup_does_not_read_or_bootstrap_fund_thesis(monkeypatch):
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    monkeypatch.setattr("pipeline_runner.get_service_client", lambda: SimpleNamespace())
    monkeypatch.setattr("pipeline_runner.SupabaseStartupsStorage", lambda client, user_id: SimpleNamespace())
    monkeypatch.setattr(
        "pipeline_runner.get_active_thesis",
        lambda *args, **kwargs: pytest.fail("on-demand lookup must not read fund thesis"),
    )
    monkeypatch.setattr(
        "pipeline_runner._bootstrap_default_thesis_or_raise",
        lambda *args, **kwargs: pytest.fail("on-demand lookup must not bootstrap fund thesis"),
    )
    monkeypatch.setattr("pipeline_runner.load_settings", lambda user_id: {"cost_budget": {"enabled": False}})
    monkeypatch.setattr("pipeline_runner.DealMemory", lambda user_id: SimpleNamespace())
    monkeypatch.setattr("pipeline_runner.ScoutEngine", _FakeScoutEngine)
    monkeypatch.setattr("pipeline_runner.ReviewerEngine", _FakeReviewerEngine)
    monkeypatch.setattr("pipeline_runner.PartnerEngine", _FakePartnerEngine)
    monkeypatch.setattr("pipeline_runner.PortfolioStore", lambda *args, **kwargs: SimpleNamespace())

    startup_id = await run_on_demand_lookup(
        "user_123",
        "Perplexity AI",
        lookup_id="lookup-123",
    )

    assert startup_id == "startup-1"
    assert _FakeScoutEngine.active_thesis is None
    assert _FakeReviewerEngine.active_thesis is None
    assert _FakeReviewerEngine.use_resource_fund_thesis_fallback is False
    assert _FakePartnerEngine.fund_thesis is None
    assert _FakePartnerEngine.use_resource_fund_thesis_fallback is False
