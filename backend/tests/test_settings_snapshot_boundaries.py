"""Settings persistence must be owned by orchestration, not domain objects."""

from types import SimpleNamespace

from portfolio.cost_control import CostController
from partner.decision import PartnerDecisionEngine
from scout.engine import ScoutEngine
from reviewer.engine import ReviewerEngine


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


def test_partner_decision_consumes_snapshot_without_loading_settings(monkeypatch):
    monkeypatch.setattr(
        "utils.settings_loader.load_settings",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("settings I/O")),
    )
    settings = {
        "fund_config": {
            "scoreBands": [{"min": 0, "max": 100, "label": "Strong Proceed"}],
            "thresholds": {"partnerReview": 50, "escalation": 70},
        }
    }
    engine = PartnerDecisionEngine(
        use_llm_fallback=False,
        api_key=None,
        tenant_user_id="settings-boundary-user",
        settings=settings,
    )
    assert engine._fund_config == settings["fund_config"]


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


def test_reviewer_construction_consumes_snapshot_without_loading_settings(monkeypatch):
    monkeypatch.setattr(
        "utils.settings_loader.load_settings",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("settings I/O")),
    )
    monkeypatch.setattr("reviewer.engine.load_active_policy", lambda *args, **kwargs: {})
    reviewer = ReviewerEngine(
        api_key="sk-test",
        storage=SimpleNamespace(_user_id="settings-boundary-user"),
        tenant_user_id="settings-boundary-user",
        settings={"fund_config": {"scoringWeights": []}},
    )
    assert reviewer.settings["fund_config"] == {"scoringWeights": []}
