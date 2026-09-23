from types import SimpleNamespace

import metrics
import pipeline_runner


def test_pipeline_engine_bundle_always_has_usage_controller(monkeypatch):
    created = []

    class Controller:
        def __init__(self, *, user_id, enforce_limits, settings=None):
            created.append((user_id, enforce_limits))

    class Engine:
        def __init__(self, *args, **kwargs):
            self.model = kwargs.get("model")
            self.cost_controller = kwargs.get("cost_controller")

    monkeypatch.setattr(pipeline_runner, "CostController", Controller)
    monkeypatch.setattr(pipeline_runner, "DealMemory", lambda user_id: SimpleNamespace())
    monkeypatch.setattr(pipeline_runner, "ScoutEngine", Engine)
    monkeypatch.setattr(pipeline_runner, "PortfolioStore", Engine)

    engines = pipeline_runner._build_pipeline_engines(
        user_id="cost-user",
        storage=SimpleNamespace(),
        api_key="key",
        settings={"cost_budget": {"enabled": False}},
        thesis_ctx={"version_id": "thesis-v1"},
    )

    assert created == [("cost-user", False)]
    assert engines.cost_controller is engines.scout_engine.cost_controller
    assert engines.model_metadata == {
        "scout": "gpt-5-nano",
        "reviewer": "gpt-5-nano",
        "partner": "gpt-5-nano",
    }


def test_pipeline_captures_models_and_context_without_claiming_persona_execution(
    monkeypatch,
):
    class Controller:
        def __init__(self, **_kwargs):
            pass

    class ScoutEngine:
        def __init__(self, **kwargs):
            self.model = kwargs["model"]
            self.cost_controller = kwargs["cost_controller"]
            self.scouts = [
                SimpleNamespace(scout_type=kind, system_prompt=f"{kind} prompt")
                for kind in (
                    "market_driven",
                    "builder_technical",
                    "pain_point",
                    "contrarian",
                )
            ]

    dependency_identity = {
        "user_id": "manifest-user",
        "thesis_id": "thesis-1",
        "thesis_version_id": "thesis-v1",
        "thesis_hash": "thesis-hash",
        "policy_id": "policy-1",
        "policy_version_id": "policy-v1",
        "policy_hash": "policy-hash",
        "rubric_version": "rubric-v1",
        "partner_rules_id": "partner-rules",
        "partner_rules_version": "3.0",
        "partner_rules_hash": "rules-hash",
        "scoring_runtime_version": "1.1.0",
        "scoring_runtime_hash": "runtime-hash",
    }
    prerequisites = SimpleNamespace(
        thesis_context={"thesis_id": "thesis-1", "version_id": "thesis-v1"},
        dependency_identity=dependency_identity,
        require_tenant=lambda user_id, **_kwargs: user_id,
    )
    monkeypatch.setenv("SCOUT_MODEL", "scout-model-captured")
    monkeypatch.setenv("REVIEWER_MODEL", "reviewer-model-captured")
    monkeypatch.setenv("PARTNER_MODEL", "partner-model-captured")
    monkeypatch.setenv("PARTNER_LLM_INCLUDE_DEAL_CONTEXT_DIGEST", "true")
    monkeypatch.setattr(pipeline_runner, "CostController", Controller)
    monkeypatch.setattr(
        pipeline_runner, "DealMemory", lambda user_id: SimpleNamespace()
    )
    monkeypatch.setattr(pipeline_runner, "ScoutEngine", ScoutEngine)
    monkeypatch.setattr(
        pipeline_runner,
        "PortfolioStore",
        lambda **_kwargs: SimpleNamespace(),
    )

    engines = pipeline_runner._build_pipeline_engines(
        user_id="manifest-user",
        storage=SimpleNamespace(),
        api_key="key",
        settings={"cost_budget": {"enabled": False}},
        thesis_ctx=prerequisites.thesis_context,
        evaluation_prerequisites=prerequisites,
    )
    # The shared core records execution identities with the completed analysis,
    # not a construction-time manifest claiming three persona invocations.
    assert engines.reviewer_engine.analysis_contract_version == "investment-analysis-v1"
    assert engines.partner_engine.analysis_contract_version == "investment-analysis-v1"
    captured = dict(engines.model_metadata)
    assert captured == {"scout": "scout-model-captured", "reviewer": "reviewer-model-captured", "partner": "partner-model-captured"}
    monkeypatch.setenv("SCOUT_MODEL", "mutated")
    monkeypatch.setenv("REVIEWER_MODEL", "mutated")
    monkeypatch.setenv("PARTNER_MODEL", "mutated")
    assert engines.model_metadata == captured
    assert engines.reviewer_engine.model == captured["reviewer"]
    assert engines.partner_engine.model == captured["partner"]
    assert engines.reviewer_engine.active_thesis == prerequisites.thesis_context
    prerequisites.thesis_context["version_id"] = "changed"
    assert engines.reviewer_engine.active_thesis["version_id"] == "thesis-v1"


def test_decision_ready_metrics_use_bounded_non_tenant_labels():
    metrics.observe_decision_ready_usage(
        cohort="manual_lookup", cost_usd=0.012, tokens=4_200
    )
    metrics.observe_model_provider_usage(
        stage="reviewer", model="gpt-5-nano", provider="openai", tokens=4_000
    )
    metrics.inc_evaluation_manifest(path="manual_lookup", outcome="success")

    body = metrics.render().decode()

    assert "aethria_decision_ready_cost_usd" in body
    assert 'cohort="manual_lookup"' in body
    assert "aethria_decision_ready_tokens" in body
    assert 'stage="reviewer"' in body
    assert 'model="gpt-5-nano"' in body
    assert 'provider="openai"' in body
    assert 'path="manual_lookup"' in body
    assert "user_id" not in body
    assert "startup_id" not in body
    assert "job_id" not in body


def test_unknown_metric_dimensions_collapse_to_bounded_unknown_label():
    metrics.observe_decision_ready_usage(
        cohort="tenant-controlled-value", cost_usd=0.0, tokens=0
    )
    metrics.inc_evaluation_manifest(path="tenant-controlled-value", outcome="success")

    body = metrics.render().decode()

    assert 'cohort="unknown"' in body
    assert 'path="unknown"' in body
    assert "tenant-controlled-value" not in body


def test_pipeline_observer_records_per_decision_delta(monkeypatch):
    observed = []

    class Controller:
        @staticmethod
        def snapshot_usage():
            return {"calls": 5, "tokens": 9_000, "cost_usd": 0.09}

        @staticmethod
        def usage_delta(before, after):
            return {"calls": 4, "tokens": 8_000, "cost_usd": 0.08}

    monkeypatch.setattr(
        pipeline_runner.metrics,
        "observe_decision_ready_usage",
        lambda **kwargs: observed.append(kwargs),
    )

    pipeline_runner._observe_decision_ready_usage(
        Controller(),
        before={"calls": 1, "tokens": 1_000, "cost_usd": 0.01},
        cohort="autonomous_discovery",
        decision_count=4,
    )

    assert observed == [
        {"cohort": "autonomous_discovery", "cost_usd": 0.02, "tokens": 2_000}
    ]
