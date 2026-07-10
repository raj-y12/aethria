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
    result = True

    def __init__(self, *args, **kwargs):
        type(self).active_thesis = kwargs.get("active_thesis", "missing")
        type(self).use_resource_fund_thesis_fallback = kwargs.get(
            "use_resource_fund_thesis_fallback",
            "missing",
        )

    async def run_startup(self, *args, **kwargs):
        type(self).calls += 1
        return type(self).result


class _FakePartnerEngine:
    fund_thesis = "unset"
    use_resource_fund_thesis_fallback = "unset"
    calls = 0
    result = True

    def __init__(self, *args, **kwargs):
        type(self).fund_thesis = kwargs.get("fund_thesis", "missing")
        type(self).use_resource_fund_thesis_fallback = kwargs.get(
            "use_resource_fund_thesis_fallback",
            "missing",
        )

    async def run_startup(self, *args, **kwargs):
        type(self).calls += 1
        return type(self).result


class _FakeThesis:
    """Stand-in for an active FundThesis; only as_engine_context() is exercised."""

    CONTEXT = {"version_id": "thesis-v1", "mandate": "AI infra, seed/A"}

    def as_engine_context(self):
        return dict(self.CONTEXT)


def _wire_common_engines(monkeypatch):
    _FakeScoutEngine.calls = 0
    _FakeReviewerEngine.calls = 0
    _FakeReviewerEngine.result = True
    _FakePartnerEngine.calls = 0
    _FakePartnerEngine.result = True
    monkeypatch.setenv("USE_SUPABASE_STORAGE", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("pipeline_runner.get_service_client", lambda: SimpleNamespace())
    monkeypatch.setattr(
        "pipeline_runner.SupabaseStartupsStorage",
        lambda client, user_id: SimpleNamespace(_client=client, _user_id=user_id),
    )
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


@pytest.mark.asyncio
async def test_on_demand_lookup_records_terminal_failure_when_review_exhausts_retries(monkeypatch):
    _wire_common_engines(monkeypatch)
    monkeypatch.setattr("pipeline_runner.get_active_thesis", lambda *a, **k: _FakeThesis())
    _FakeReviewerEngine.result = False
    recorded = []
    states = []

    async def _record(user_id, lookup_id, message):
        recorded.append((user_id, lookup_id, message))

    monkeypatch.setattr("pipeline_runner._record_lookup_failure", _record)
    monkeypatch.setattr("pipeline_runner.upsert_pipeline_state", lambda *a, **k: states.append(k))

    startup_id = await run_on_demand_lookup("user_123", "Perplexity AI", lookup_id="lookup-review-fail")

    assert startup_id == "startup-1"
    assert _FakeReviewerEngine.calls == 3
    assert _FakePartnerEngine.calls == 0
    assert recorded and recorded[0][:2] == ("user_123", "lookup-review-fail")
    assert "review" in recorded[0][2].lower()
    assert states[-1]["startup_id"] == "startup-1"
    assert states[-1]["status"] == "failed"


@pytest.mark.asyncio
async def test_on_demand_lookup_records_terminal_failure_when_partner_exhausts_retries(monkeypatch):
    _wire_common_engines(monkeypatch)
    monkeypatch.setattr("pipeline_runner.get_active_thesis", lambda *a, **k: _FakeThesis())
    _FakePartnerEngine.result = False
    recorded = []
    states = []

    async def _record(user_id, lookup_id, message):
        recorded.append((user_id, lookup_id, message))

    monkeypatch.setattr("pipeline_runner._record_lookup_failure", _record)
    monkeypatch.setattr("pipeline_runner.upsert_pipeline_state", lambda *a, **k: states.append(k))

    startup_id = await run_on_demand_lookup("user_123", "Perplexity AI", lookup_id="lookup-partner-fail")

    assert startup_id == "startup-1"
    assert _FakeReviewerEngine.calls == 1
    assert _FakePartnerEngine.calls == 2
    assert recorded and recorded[0][:2] == ("user_123", "lookup-partner-fail")
    assert "decision" in recorded[0][2].lower()
    assert states[-1]["startup_id"] == "startup-1"
    assert states[-1]["status"] == "failed"


@pytest.mark.asyncio
async def test_add_context_rerun_regenerates_and_persists_memo(monkeypatch):
    _wire_common_engines(monkeypatch)
    monkeypatch.setattr("pipeline_runner.get_active_thesis", lambda *a, **k: _FakeThesis())
    patches = []
    prepared = []
    startup = SimpleNamespace(startup_id="startup-1")
    storage = SimpleNamespace(
        _client=SimpleNamespace(),
        _user_id="user_123",
        prepare_rerun_startup=lambda startup_id, **kwargs: prepared.append((startup_id, kwargs)) or startup_id,
        get_startup=lambda startup_id: startup,
        update_startup_partial=lambda startup_id, patch: patches.append((startup_id, patch)) or True,
    )
    monkeypatch.setattr("pipeline_runner.SupabaseStartupsStorage", lambda client, user_id: storage)

    class _MemoGenerator:
        def generate_memo(self, current, **kwargs):
            assert current is startup
            assert kwargs["tenant_user_id"] == "user_123"
            return "# Regenerated memo\n\nNew pilot evidence incorporated."

    monkeypatch.setattr("pipeline_runner.MemoGenerator", _MemoGenerator)
    monkeypatch.setattr("pipeline_runner._build_rerun_operator_context", lambda context: context)

    startup_id = await run_on_demand_lookup(
        "user_123",
        "Acme",
        lookup_id="lookup-rerun-1",
        additional_context="https://acme.example/news",
        replace_startup_id="startup-1",
    )

    assert startup_id == "startup-1"
    assert _FakeScoutEngine.calls == 0
    assert prepared[0][0] == "startup-1"
    assert patches == [
        (
            "startup-1",
            {"investment_memo_markdown": "# Regenerated memo\n\nNew pilot evidence incorporated."},
        )
    ]
