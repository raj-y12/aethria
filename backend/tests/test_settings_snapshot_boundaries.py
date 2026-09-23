"""Settings persistence must be owned by orchestration, not domain objects."""

from types import SimpleNamespace

from portfolio.cost_control import CostController
from scout.engine import ScoutEngine


def test_cost_controller_consumes_snapshot_without_loading_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "utils.settings_loader.load_settings",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("settings I/O")),
    )
    controller = CostController(
        budget_file=str(tmp_path / "budgets.json"),
        user_id="settings-boundary-user",
        settings={"cost_budget": {"enabled": True, "max_tokens_per_run": 321}},
    )
    assert controller.default_budgets["scout"]["tokens"] == 321


def test_scout_construction_consumes_snapshot_without_loading_settings(monkeypatch):
    monkeypatch.setattr(
        "utils.settings_loader.load_settings",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("settings I/O")),
    )
    engine = ScoutEngine(
        api_key="sk-test",
        storage=SimpleNamespace(_user_id="settings-boundary-user"),
        tenant_user_id="settings-boundary-user",
        settings={"agent_config": {"scout_region": "global"}},
    )
    try:
        assert all("global markets" in scout.system_prompt for scout in engine.scouts)
    finally:
        engine.close()


async def test_current_analysis_consumes_frozen_fund_context_without_loading_settings(monkeypatch):
    from tests.investment_analysis.test_authority import run_case

    def unexpected_settings_read(*args, **kwargs):
        raise AssertionError("Analysis must consume its supplied fund context")

    monkeypatch.setattr("utils.settings_loader.load_settings", unexpected_settings_read)
    context = {"fund_configuration": {"mandate": {"mandateName": "Seed infrastructure"}}}
    result, calls = await run_case(context=context)
    assert result.context_snapshot == context
    assert all(payload["fund_context"] == context for _, payload in calls)
