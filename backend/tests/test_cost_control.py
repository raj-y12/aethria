from portfolio.cost_control import CostController


def _controller(monkeypatch, tmp_path, *, enforce_limits):
    monkeypatch.setattr("portfolio.cost_control.env_config.use_supabase_storage", lambda: False)
    monkeypatch.setattr(
        "portfolio.cost_control.load_settings",
        lambda user_id: {"cost_budget": {"enabled": enforce_limits}},
    )
    return CostController(
        budget_file=str(tmp_path / f"budgets-{enforce_limits}.json"),
        user_id="cost-user",
        enforce_limits=enforce_limits,
    )


def test_measurement_only_controller_records_usage_without_enforcing_limits(
    monkeypatch, tmp_path
):
    controller = _controller(monkeypatch, tmp_path, enforce_limits=False)
    controller.default_budgets["scout"]["calls"] = 0
    controller.default_budgets["scout"]["tokens"] = 0

    allowed, reason = controller.can_make_call(
        "scout", "market-driven", estimated_tokens=50_000
    )
    controller.record_usage("scout", "market-driven", tokens_used=2_500)

    assert allowed is True
    assert reason is None
    assert controller.snapshot_usage() == {
        "calls": 1,
        "tokens": 2_500,
        "cost_usd": 0.0025,
    }


def test_local_storage_override_disables_supabase_budget_reads(monkeypatch, tmp_path):
    monkeypatch.setattr("portfolio.cost_control.env_config.use_supabase_storage", lambda: False)
    monkeypatch.setenv("SUPABASE_URL", "https://configured.example")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "configured")
    controller = _controller(monkeypatch, tmp_path, enforce_limits=False)
    assert controller._using_supabase() is False


def test_enforcing_controller_preserves_existing_budget_gate(monkeypatch, tmp_path):
    controller = _controller(monkeypatch, tmp_path, enforce_limits=True)
    controller.default_budgets["scout"]["calls"] = 0

    allowed, reason = controller.can_make_call("scout", "market-driven")

    assert allowed is False
    assert "call budget" in (reason or "").lower()


def test_usage_delta_is_non_negative_and_ignores_prior_larger_values():
    before = {"calls": 9, "tokens": 900, "cost_usd": 0.9}
    after = {"calls": 8, "tokens": 1_100, "cost_usd": 0.7}

    assert CostController.usage_delta(before, after) == {
        "calls": 0,
        "tokens": 200,
        "cost_usd": 0.0,
    }


def test_unknown_agent_type_still_fails_closed_in_measurement_mode(monkeypatch, tmp_path):
    controller = _controller(monkeypatch, tmp_path, enforce_limits=False)

    allowed, reason = controller.can_make_call("unknown", "unknown")

    assert allowed is False
    assert "unknown agent type" in (reason or "").lower()


def test_record_usage_emits_bounded_model_provider_measurement(monkeypatch, tmp_path):
    controller = _controller(monkeypatch, tmp_path, enforce_limits=False)
    observed = []
    monkeypatch.setattr(
        "metrics.observe_model_provider_usage",
        lambda **kwargs: observed.append(kwargs),
    )

    controller.record_usage(
        "reviewer",
        "reviewer-v1",
        tokens_used=1_234,
        model="gpt-5-nano",
        provider="openai",
    )

    assert observed == [
        {
            "stage": "reviewer",
            "model": "gpt-5-nano",
            "provider": "openai",
            "tokens": 1_234,
        }
    ]
