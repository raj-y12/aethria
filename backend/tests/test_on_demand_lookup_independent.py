from types import SimpleNamespace

import pytest

from pipeline_runner import run_on_demand_lookup


class _FakeScoutEngine:
    active_thesis = "unset"
    calls = 0

    def __init__(self, *args, **kwargs):
        type(self).active_thesis = kwargs.get("active_thesis", "missing")

    async def run_named_lookup(self, **kwargs):
        type(self).calls += 1
        return "startup-1"


class _FakeReviewerEngine:
    active_thesis = "unset"
    use_resource_fund_thesis_fallback = "unset"
    calls = 0

    def __init__(self, *args, **kwargs):
        type(self).active_thesis = kwargs.get("active_thesis", "missing")
        type(self).use_resource_fund_thesis_fallback = kwargs.get(
            "use_resource_fund_thesis_fallback",
            "missing",
        )

    async def run_startup(self, *args, **kwargs):
        type(self).calls += 1
        return True


class _FakePartnerEngine:
    fund_thesis = "unset"
    use_resource_fund_thesis_fallback = "unset"
    calls = 0

    def __init__(self, *args, **kwargs):
        type(self).fund_thesis = kwargs.get("fund_thesis", "missing")
        type(self).use_resource_fund_thesis_fallback = kwargs.get(
            "use_resource_fund_thesis_fallback",
            "missing",
        )

    async def run_startup(self, *args, **kwargs):
        type(self).calls += 1
        return True


class _FakeThesis:
    """Stand-in for an active FundThesis; only as_engine_context() is exercised."""

    CONTEXT = {"version_id": "thesis-v1", "mandate": "AI infra, seed/A"}

    def as_engine_context(self):
        return dict(self.CONTEXT)


def _wire_common_engines(monkeypatch):
    _FakeScoutEngine.calls = 0
    _FakeReviewerEngine.calls = 0
    _FakePartnerEngine.calls = 0
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("pipeline_runner.get_service_client", lambda: SimpleNamespace())
    monkeypatch.setattr("pipeline_runner.SupabaseStartupsStorage", lambda client, user_id: SimpleNamespace())
    monkeypatch.setattr("pipeline_runner.load_settings", lambda user_id: {"cost_budget": {"enabled": False}})
    monkeypatch.setattr("pipeline_runner.DealMemory", lambda user_id: SimpleNamespace())
    monkeypatch.setattr("pipeline_runner.ScoutEngine", _FakeScoutEngine)
    monkeypatch.setattr("pipeline_runner.ReviewerEngine", _FakeReviewerEngine)
    monkeypatch.setattr("pipeline_runner.PartnerEngine", _FakePartnerEngine)
    monkeypatch.setattr("pipeline_runner.PortfolioStore", lambda *args, **kwargs: SimpleNamespace())


@pytest.mark.asyncio
async def test_on_demand_lookup_evaluates_against_active_thesis(monkeypatch):
    """Lookup is open, but evaluation must be mandate-aware: when a thesis exists,
    its engine context flows into scout / reviewer / partner so alignment is scored."""
    _wire_common_engines(monkeypatch)
    monkeypatch.setattr("pipeline_runner.get_active_thesis", lambda *a, **k: _FakeThesis())
    monkeypatch.setattr(
        "pipeline_runner._bootstrap_default_thesis_or_raise",
        lambda *a, **k: pytest.fail("should not bootstrap when an active thesis already exists"),
    )

    startup_id = await run_on_demand_lookup("user_123", "Perplexity AI", lookup_id="lookup-123")

    assert startup_id == "startup-1"
    assert _FakeScoutEngine.active_thesis == _FakeThesis.CONTEXT
    assert _FakeReviewerEngine.active_thesis == _FakeThesis.CONTEXT
    assert _FakePartnerEngine.fund_thesis == _FakeThesis.CONTEXT


@pytest.mark.asyncio
async def test_on_demand_lookup_runs_thesis_blind_when_no_mandate(monkeypatch):
    """Lookup permission is open: a missing/un-bootstrappable thesis must NOT block
    the search. Engines simply receive None and run thesis-blind."""
    _wire_common_engines(monkeypatch)
    monkeypatch.setattr("pipeline_runner.get_active_thesis", lambda *a, **k: None)

    def _failing_bootstrap(*a, **k):
        raise RuntimeError("no default thesis available")

    monkeypatch.setattr("pipeline_runner._bootstrap_default_thesis_or_raise", _failing_bootstrap)

    startup_id = await run_on_demand_lookup("user_123", "Perplexity AI", lookup_id="lookup-123")

    assert startup_id == "startup-1"
    assert _FakeScoutEngine.active_thesis is None
    assert _FakeReviewerEngine.active_thesis is None
    assert _FakePartnerEngine.fund_thesis is None


@pytest.mark.asyncio
async def test_on_demand_lookup_cancelled_before_scout_does_not_start(monkeypatch):
    _wire_common_engines(monkeypatch)
    monkeypatch.setattr("pipeline_runner.get_active_thesis", lambda *a, **k: _FakeThesis())

    startup_id = await run_on_demand_lookup(
        "user_123",
        "Perplexity AI",
        lookup_id="lookup-123",
        is_cancelled=lambda: True,
    )

    assert startup_id is None
    assert _FakeScoutEngine.calls == 0
    assert _FakeReviewerEngine.calls == 0
    assert _FakePartnerEngine.calls == 0


@pytest.mark.asyncio
async def test_on_demand_lookup_cancelled_after_scout_stops_before_review(monkeypatch):
    _wire_common_engines(monkeypatch)
    monkeypatch.setattr("pipeline_runner.get_active_thesis", lambda *a, **k: _FakeThesis())
    checks = iter([False, False, True])

    startup_id = await run_on_demand_lookup(
        "user_123",
        "Perplexity AI",
        lookup_id="lookup-123",
        is_cancelled=lambda: next(checks, True),
    )

    assert startup_id == "startup-1"
    assert _FakeScoutEngine.calls == 1
    assert _FakeReviewerEngine.calls == 0
    assert _FakePartnerEngine.calls == 0
