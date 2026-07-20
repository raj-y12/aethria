import hashlib
import importlib
import json
from unittest.mock import MagicMock

import models
from models import PartnerInfo, PartnerSnapshot, ReviewInfo, ScoutInfo, SingleReview, Startup


def _startup(*, missing_prompt_versions: bool = False) -> Startup:
    scout_prompt = None if missing_prompt_versions else "scout-prompt-hash"
    skeptic_prompt = None if missing_prompt_versions else "skeptic-prompt-hash"
    partner_prompt = None if missing_prompt_versions else "partner-prompt-hash"
    return Startup(
        startup_id="startup-manifest-1",
        scout_info=ScoutInfo(
            startup_id="startup-manifest-1",
            name="Manifest Co",
            one_line="Traceable evaluations",
            sector="Infrastructure",
            problem="Evaluation metadata is incomplete",
            solution="Version every dependency",
            target_users="Investment teams",
            why_now="AI evaluation adoption",
            scout_type="market_driven",
            confidence_score=0.8,
            origin_type="on_demand_lookup",
            references=["https://manifest.example/about"],
            prompt_version=scout_prompt,
        ),
        review_info=ReviewInfo(
            market_score=8,
            product_score=7,
            technical_score=8,
            execution_score=7,
            overall_summary="Promising",
            key_risks=["Early"],
            verdict="STRONG",
            structured_scoring={
                "policy_version_id": "policy-v7",
                "policy_hash": "policy-hash-7",
                "rubric_version": "rubric-v3",
            },
            reviews=[
                SingleReview(
                    reviewer_type="DefaultReviewer",
                    market_score=8,
                    product_score=7,
                    technical_score=8,
                    execution_score=7,
                    overall_summary="Promising",
                    key_risks=["Early"],
                    verdict="STRONG",
                    prompt_version="default-prompt-hash",
                ),
                SingleReview(
                    reviewer_type="SkepticalReviewer",
                    market_score=7,
                    product_score=7,
                    technical_score=7,
                    execution_score=6,
                    overall_summary="Needs proof",
                    key_risks=["Early"],
                    verdict="MEDIUM",
                    prompt_version=skeptic_prompt,
                ),
            ],
        ),
        partner_info=PartnerInfo(
            thesis="Traceable systems win",
            why_this_matters="Institutional trust",
            snapshot=PartnerSnapshot(one_liner="Traceable evaluations"),
            market_insight="Growing need",
            product_edge="Complete manifests",
            risks=["Early"],
            recommendation="MONITOR",
            decision_rationale="Promising but early",
            confidence=0.72,
            next_action="Request customer references",
            prompt_version=partner_prompt,
        ),
    )


def _manifest_module():
    return importlib.import_module("evaluation.manifest")


def test_evaluation_manifest_model_is_the_pydantic_source_of_truth():
    manifest_model = getattr(models, "EvaluationManifest")

    assert issubclass(manifest_model, models.BaseModel)
    assert manifest_model.model_fields["manifest_version"].default == "evaluation-manifest-v1"


def test_manifest_builder_records_models_prompts_policy_and_partner_rules():
    manifest_module = _manifest_module()
    startup = _startup()

    manifest = manifest_module.build_evaluation_manifest(
        startup,
        pipeline_run_id="pipeline-run-1",
        evaluation_path="manual_lookup",
        model_metadata={
            "scout": "gpt-5-nano",
            "reviewer": "gpt-5-nano",
            "partner": "gpt-5-mini",
        },
    )

    assert manifest.pipeline_run_id == "pipeline-run-1"
    assert manifest.evaluation_path == "manual_lookup"
    assert manifest.models == {
        "scout": "gpt-5-nano",
        "reviewer": "gpt-5-nano",
        "partner": "gpt-5-mini",
    }
    assert manifest.prompt_versions == {
        "scout": "scout-prompt-hash",
        "reviewer.DefaultReviewer": "default-prompt-hash",
        "reviewer.SkepticalReviewer": "skeptic-prompt-hash",
        "reviewer.OpportunistReviewer": "unknown",
        "partner": "partner-prompt-hash",
    }
    assert manifest.policy_version_id == "policy-v7"
    assert manifest.policy_hash == "policy-hash-7"
    assert manifest.rubric_version == "rubric-v3"

    rules_path = manifest_module.get_policy_file_path("partner_rules")
    rules = json.loads(rules_path.read_text())
    assert rules["version"] == "3.0"
    assert manifest.partner_rules_version == rules["version"]
    canonical = json.dumps(rules, sort_keys=True, separators=(",", ":"))
    assert manifest.partner_rules_hash == hashlib.sha256(canonical.encode()).hexdigest()


def test_manifest_represents_missing_prompt_versions_explicitly():
    manifest_module = _manifest_module()

    manifest = manifest_module.build_evaluation_manifest(
        _startup(missing_prompt_versions=True),
        pipeline_run_id="pipeline-run-2",
        evaluation_path="rerun",
        model_metadata={},
    )

    assert manifest.models == {
        "scout": "unknown",
        "reviewer": "unknown",
        "partner": "unknown",
    }
    assert manifest.prompt_versions["scout"] == "unknown"
    assert manifest.prompt_versions["reviewer.SkepticalReviewer"] == "unknown"
    assert manifest.prompt_versions["reviewer.OpportunistReviewer"] == "unknown"
    assert manifest.prompt_versions["partner"] == "unknown"


def test_manifest_round_trips_without_tenant_identity():
    manifest_module = _manifest_module()
    manifest_model = getattr(models, "EvaluationManifest")
    manifest = manifest_module.build_evaluation_manifest(
        _startup(),
        pipeline_run_id="pipeline-run-3",
        evaluation_path="autonomous_discovery",
        model_metadata={"scout": "a", "reviewer": "b", "partner": "c"},
    )

    payload = manifest.model_dump(mode="json")

    assert "user_id" not in payload
    assert manifest_model.model_validate(payload) == manifest


def test_storage_merges_manifest_into_trace_without_losing_stage_data(monkeypatch):
    supabase_storage = importlib.import_module("supabase_storage")
    storage = object.__new__(supabase_storage.SupabaseStartupsStorage)
    storage._user_id = "manifest-user"
    startup = _startup()
    startup.agent_trace = {"scout": {"status": "completed"}}
    updated = []
    monkeypatch.setattr(storage, "get_startup", lambda startup_id: startup)
    monkeypatch.setattr(
        storage,
        "_update_startup_columns",
        lambda startup_id, columns: updated.append((startup_id, columns)),
    )
    manifest = _manifest_module().build_evaluation_manifest(
        startup,
        pipeline_run_id="pipeline-run-4",
        evaluation_path="manual_lookup",
        model_metadata={},
    )

    assert storage.record_evaluation_manifest("startup-manifest-1", manifest) is True
    assert len(updated) == 1
    assert updated[0][0] == "startup-manifest-1"
    trace = updated[0][1]["agent_trace"]
    assert trace["scout"] == {"status": "completed"}
    assert trace["evaluation_manifest"]["pipeline_run_id"] == "pipeline-run-4"


def test_partner_persistence_records_manifest_in_the_same_trace_update(monkeypatch):
    supabase_storage = importlib.import_module("supabase_storage")
    storage = object.__new__(supabase_storage.SupabaseStartupsStorage)
    storage._user_id = "manifest-user"
    storage._client = MagicMock()
    storage.logger = MagicMock()
    startup = _startup()
    startup.partner_info = None
    updated = []
    monkeypatch.setattr(storage, "get_startup", lambda startup_id: startup)
    monkeypatch.setattr(
        storage,
        "_update_startup_columns",
        lambda startup_id, columns: updated.append((startup_id, columns)),
    )

    assert storage.add_partner_decision(
        startup.startup_id,
        _startup().partner_info,
        pipeline_run_id="8c24745e-1d48-4ea1-b2fd-f7835f64ad73",
    ) is True

    assert len(updated) == 1
    trace = updated[0][1]["agent_trace"]
    assert trace["partner"]["status"] == "completed"
    assert trace["evaluation_manifest"]["evaluation_path"] == "manual_lookup"
    assert trace["evaluation_manifest"]["pipeline_run_id"] == (
        "8c24745e-1d48-4ea1-b2fd-f7835f64ad73"
    )
