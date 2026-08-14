from types import SimpleNamespace

import metrics
import pipeline_runner
from models import EvaluationManifestIdentity


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
    monkeypatch.setattr(pipeline_runner, "ReviewerEngine", Engine)
    monkeypatch.setattr(pipeline_runner, "PartnerEngine", Engine)
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


def test_governed_pipeline_captures_manifest_identity_once_from_constructed_engines(
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

    class ReviewerEngine:
        def __init__(self, **kwargs):
            self.model = kwargs["model"]
            self.use_structured_scoring = True
            self.reviewer = SimpleNamespace(SYSTEM_PROMPT="default prompt")
            self.skeptical_reviewer = SimpleNamespace(
                SYSTEM_PROMPT="skeptical prompt"
            )
            self.opportunist_reviewer = SimpleNamespace(
                SYSTEM_PROMPT="opportunist prompt"
            )

    class PartnerEngine:
        def __init__(self, **kwargs):
            self.received = kwargs
            self.decision_engine = SimpleNamespace(
                provider_id="openai",
                model=kwargs["model"],
                prompt_template_version="partner-template-hash",
            )
            self.bound_identity = None

        def set_evaluation_manifest_identity(self, identity):
            self.bound_identity = identity

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
    monkeypatch.setattr(pipeline_runner, "ReviewerEngine", ReviewerEngine)
    monkeypatch.setattr(pipeline_runner, "PartnerEngine", PartnerEngine)
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
    captured = engines.evaluation_manifest_identity
    assert isinstance(captured, EvaluationManifestIdentity)
    assert engines.partner_engine.bound_identity is captured
    assert engines.partner_engine.received["model"] == "partner-model-captured"
    assert engines.partner_engine.received["include_deal_context_digest"] is True

    monkeypatch.setenv("SCOUT_MODEL", "mutated")
    monkeypatch.setenv("REVIEWER_MODEL", "mutated")
    monkeypatch.setenv("PARTNER_MODEL", "mutated")
    monkeypatch.setenv("PARTNER_LLM_INCLUDE_DEAL_CONTEXT_DIGEST", "false")

    assert captured.model_identities["scout"].model_id == "scout-model-captured"
    assert captured.model_identities["reviewer"].model_id == (
        "reviewer-model-captured"
    )
    assert captured.model_identities["partner"].model_id == (
        "partner-model-captured"
    )
    assert captured.dependency_identity.model_dump(mode="python") == (
        dependency_identity
    )


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
