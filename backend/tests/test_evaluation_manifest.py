import importlib
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

import models
from models import (
    PartnerInfo,
    PartnerSnapshot,
    ReviewInfo,
    ScoutInfo,
    SingleReview,
    Startup,
)


def _startup() -> Startup:
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
            prompt_version="scout-prompt-hash",
        ),
        review_info=ReviewInfo(
            market_score=8,
            product_score=7,
            technical_score=8,
            execution_score=7,
            overall_summary="Promising",
            key_risks=["Early"],
            verdict="STRONG",
            fund_thesis_version_id="thesis-version-7",
            structured_scoring={
                "policy_version_id": "policy-v7",
                "policy_hash": "policy-hash-7",
                "rubric_version": "rubric-v3",
                "scoring_runtime_version": "1.1.0",
                "scoring_runtime_hash": "runtime-hash-1",
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
                    prompt_version="skeptic-prompt-hash",
                ),
                SingleReview(
                    reviewer_type="OpportunistReviewer",
                    market_score=9,
                    product_score=8,
                    technical_score=8,
                    execution_score=8,
                    overall_summary="Compelling upside",
                    key_risks=["Early"],
                    verdict="STRONG",
                    prompt_version="opportunist-prompt-hash",
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
            llm_fallback_reason="grey_zone",
            prompt_version="partner-prompt-hash",
        ),
    )


def _manifest_module():
    return importlib.import_module("evaluation.manifest")


def _dependency_identity():
    return {
        "user_id": "manifest-user",
        "thesis_id": "thesis-1",
        "thesis_version_id": "thesis-version-7",
        "thesis_hash": "thesis-hash-7",
        "policy_id": "policy-1",
        "policy_version_id": "policy-v7",
        "policy_hash": "policy-hash-7",
        "rubric_version": "rubric-v3",
        "partner_rules_id": "partner-rules",
        "partner_rules_version": "3.0",
        "partner_rules_hash": "partner-rules-hash-v3",
        "scoring_runtime_version": "1.1.0",
        "scoring_runtime_hash": "runtime-hash-1",
    }


def _model_identity(model_id: str, configuration_hash: str):
    return {
        "provider_id": "openai",
        "model_id": model_id,
        "configuration_id": "openai.chat.completions.v1",
        "configuration_hash": configuration_hash,
    }


def _manifest_identity():
    return {
        "dependency_identity": _dependency_identity(),
        "model_identities": {
            "scout": _model_identity("gpt-5-nano", "scout-config-hash"),
            "reviewer": _model_identity("gpt-5-nano", "reviewer-config-hash"),
            "partner": _model_identity("gpt-5-mini", "partner-config-hash"),
        },
        "construction_prompt_versions": {
            "scout.market_driven": "scout-prompt-hash",
            "scout.builder_technical": "builder-prompt-hash",
            "scout.pain_point": "pain-prompt-hash",
            "scout.contrarian": "contrarian-prompt-hash",
            "reviewer.DefaultReviewer": "default-prompt-hash",
            "reviewer.SkepticalReviewer": "skeptic-prompt-hash",
            "reviewer.OpportunistReviewer": "opportunist-prompt-hash",
            "partner.template": "partner-template-hash",
        },
    }


def _build_manifest(*, startup=None, identity=None, run_id="pipeline-run-1"):
    candidate = startup or _startup()
    trace = dict(candidate.agent_trace) if isinstance(candidate.agent_trace, dict) else {}
    for stage in ("scout", "reviewer", "partner"):
        trace[stage] = {"status": "completed", "pipeline_run_id": run_id}
    candidate.agent_trace = trace
    partner_prompt = (
        candidate.partner_info.prompt_version if candidate.partner_info else None
    )
    return _manifest_module().build_evaluation_manifest(
        candidate,
        pipeline_run_id=run_id,
        evaluation_path="manual_lookup",
        manifest_identity=identity or _manifest_identity(),
        partner_execution_prompt_version=partner_prompt,
    )


def test_evaluation_manifest_models_are_strict_frozen_sources_of_truth():
    assert models.EvaluationManifest.model_fields["manifest_version"].default == (
        "evaluation-manifest-v3"
    )
    assert models.EvaluationManifestIdentity.model_config["extra"] == "forbid"
    assert models.EvaluationManifestIdentity.model_config["frozen"] is True

    identity = models.EvaluationManifestIdentity.model_validate(_manifest_identity())
    with pytest.raises(ValidationError, match="frozen"):
        identity.dependency_identity = identity.dependency_identity
    with pytest.raises(TypeError, match="immutable"):
        identity.construction_prompt_versions["partner.template"] = "mutated"
    manifest = _build_manifest()
    with pytest.raises(TypeError, match="immutable"):
        manifest.stage_identities["scout"] = manifest.stage_identities["scout"]
    with pytest.raises(TypeError, match="immutable"):
        manifest.stage_identities["reviewer"].prompt_identities[
            "DefaultReviewer"
        ] = manifest.stage_identities["reviewer"].prompt_identities[
            "DefaultReviewer"
        ]


def test_manifest_records_complete_consumed_dependency_and_execution_identity():
    manifest = _build_manifest()

    assert manifest.user_id == "manifest-user"
    assert manifest.thesis_id == "thesis-1"
    assert manifest.thesis_version_id == "thesis-version-7"
    assert manifest.thesis_hash == "thesis-hash-7"
    assert manifest.policy_id == "policy-1"
    assert manifest.policy_version_id == "policy-v7"
    assert manifest.policy_hash == "policy-hash-7"
    assert manifest.rubric_version == "rubric-v3"
    assert manifest.partner_rules_id == "partner-rules"
    assert manifest.partner_rules_version == "3.0"
    assert manifest.partner_rules_hash == "partner-rules-hash-v3"
    assert manifest.scoring_runtime_version == "1.1.0"
    assert manifest.scoring_runtime_hash == "runtime-hash-1"
    assert set(manifest.stage_identities) == {"scout", "reviewer", "partner"}
    assert {
        stage: stage_identity.execution_state
        for stage, stage_identity in manifest.stage_identities.items()
    } == {"scout": "executed", "reviewer": "executed", "partner": "executed"}
    assert manifest.stage_identities["partner"].model_identity.provider_id == "openai"
    assert (
        manifest.stage_identities["reviewer"].model_identity.configuration_hash
        == "reviewer-config-hash"
    )
    assert {
        key: prompt.execution_prompt_version
        for key, prompt in manifest.stage_identities[
            "reviewer"
        ].prompt_identities.items()
    } == {
        "DefaultReviewer": "default-prompt-hash",
        "SkepticalReviewer": "skeptic-prompt-hash",
        "OpportunistReviewer": "opportunist-prompt-hash",
    }
    assert (
        manifest.stage_identities["partner"]
        .prompt_identities["decision"]
        .execution_prompt_version
        == "partner-prompt-hash"
    )


def test_manifest_identity_rejects_every_missing_governed_identity_component():
    for field in _dependency_identity():
        payload = deepcopy(_manifest_identity())
        del payload["dependency_identity"][field]
        with pytest.raises(ValidationError):
            models.EvaluationManifestIdentity.model_validate(payload)

    for field in ("model_identities", "construction_prompt_versions"):
        payload = deepcopy(_manifest_identity())
        del payload[field]
        with pytest.raises(ValidationError):
            models.EvaluationManifestIdentity.model_validate(payload)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda startup: setattr(
                startup.review_info, "fund_thesis_version_id", "thesis-version-other"
            ),
            "thesis",
        ),
        (
            lambda startup: startup.review_info.structured_scoring.update(
                {"policy_hash": "policy-hash-other"}
            ),
            "policy",
        ),
        (
            lambda startup: startup.review_info.structured_scoring.update(
                {"scoring_runtime_hash": "runtime-hash-other"}
            ),
            "runtime",
        ),
        (
            lambda startup: setattr(
                startup.scout_info, "prompt_version", "scout-prompt-other"
            ),
            "prompt",
        ),
        (
            lambda startup: setattr(
                startup.review_info.reviews[1],
                "prompt_version",
                "skeptic-prompt-other",
            ),
            "prompt",
        ),
    ],
)
def test_manifest_rejects_persisted_thesis_policy_and_prompt_mismatches(
    mutate, message
):
    startup = _startup()
    mutate(startup)

    with pytest.raises(ValueError, match=message):
        _build_manifest(startup=startup)


def test_rule_based_partner_records_explicit_no_prompt_execution():
    startup = _startup()
    startup.partner_info.prompt_version = None
    startup.partner_info.llm_fallback_reason = None

    manifest = _build_manifest(startup=startup)

    partner_stage = manifest.stage_identities["partner"]
    assert partner_stage.prompt_identities["decision"].execution_state == "not_run"
    assert partner_stage.model_identity is None


def test_manifest_uses_only_captured_identity_after_environment_and_global_reload(
    monkeypatch,
):
    identity = models.EvaluationManifestIdentity.model_validate(_manifest_identity())
    before = _build_manifest(identity=identity, run_id="pipeline-before")
    monkeypatch.setenv("SCOUT_MODEL", "mutated-scout")
    monkeypatch.setenv("REVIEWER_MODEL", "mutated-reviewer")
    monkeypatch.setenv("PARTNER_MODEL", "mutated-partner")
    monkeypatch.setenv("PARTNER_LLM_INCLUDE_DEAL_CONTEXT_DIGEST", "true")
    policy_resolver = importlib.import_module("core.policy_resolver")
    monkeypatch.setattr(
        policy_resolver,
        "get_partner_rules",
        lambda: (_ for _ in ()).throw(
            AssertionError("manifest must not reload global Partner rules")
        ),
    )

    after = _build_manifest(identity=identity, run_id="pipeline-after")

    ignored = {"pipeline_run_id", "created_at"}
    before_payload = before.model_dump(exclude=ignored)
    after_payload = after.model_dump(exclude=ignored)
    for payload in (before_payload, after_payload):
        for stage in payload["stage_identities"].values():
            stage.pop("source_pipeline_run_id")
    assert before_payload == after_payload


def test_concurrent_environment_and_global_mutation_cannot_change_manifest_identity(
    monkeypatch,
):
    identity = models.EvaluationManifestIdentity.model_validate(_manifest_identity())
    stop = threading.Event()
    policy_resolver = importlib.import_module("core.policy_resolver")
    original_rules_getter = policy_resolver.get_partner_rules
    monkeypatch.setenv("REVIEWER_MODEL", "baseline-reviewer")
    monkeypatch.setenv("PARTNER_MODEL", "baseline-partner")

    def mutate_environment():
        while not stop.is_set():
            os.environ["REVIEWER_MODEL"] = "mutated-a"
            os.environ["PARTNER_MODEL"] = "mutated-b"
            os.environ["REVIEWER_MODEL"] = "mutated-c"
            os.environ["PARTNER_MODEL"] = "mutated-d"
            policy_resolver.get_partner_rules = lambda: ("mutated-a", {})
            policy_resolver.get_partner_rules = lambda: ("mutated-b", {})

    thread = threading.Thread(target=mutate_environment)
    thread.start()
    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            manifests = list(
                executor.map(
                    lambda index: _build_manifest(
                        identity=identity, run_id=f"pipeline-{index}"
                    ),
                    range(64),
                )
            )
    finally:
        stop.set()
        thread.join(timeout=2)
        os.environ["REVIEWER_MODEL"] = "baseline-reviewer"
        os.environ["PARTNER_MODEL"] = "baseline-partner"
        policy_resolver.get_partner_rules = original_rules_getter

    assert {
        manifest.stage_identities["reviewer"].model_identity.model_id
        for manifest in manifests
    } == {
        "gpt-5-nano"
    }
    assert {
        manifest.stage_identities["partner"].model_identity.model_id
        for manifest in manifests
    } == {
        "gpt-5-mini"
    }
    assert {
        manifest.stage_identities["reviewer"]
        .prompt_identities["DefaultReviewer"]
        .construction_prompt_version
        for manifest in manifests
    } == {"default-prompt-hash"}
    assert {manifest.partner_rules_hash for manifest in manifests} == {
        "partner-rules-hash-v3"
    }


def test_manifest_serialization_round_trip_preserves_exact_identity():
    manifest = _build_manifest(run_id="pipeline-round-trip")

    payload = manifest.model_dump(mode="json")

    assert payload["stage_identities"]["scout"]["execution_state"] == "executed"
    assert (
        payload["stage_identities"]["partner"]["prompt_identities"]["decision"]
        ["execution_state"]
        == "executed"
    )
    assert models.EvaluationManifest.model_validate(payload) == manifest


def _storage(monkeypatch, startup=None):
    supabase_storage = importlib.import_module("legacy_supabase.storage")
    storage = object.__new__(supabase_storage.SupabaseStartupsStorage)
    storage._user_id = "manifest-user"
    storage._client = MagicMock()
    storage.logger = MagicMock()
    startup = startup or _startup()
    updated = []
    monkeypatch.setattr(storage, "get_startup", lambda startup_id: startup)
    monkeypatch.setattr(
        storage,
        "_update_startup_columns",
        lambda startup_id, columns: updated.append((startup_id, columns)),
    )
    monkeypatch.setattr(storage, "_settings_for_trace", lambda: {})
    return storage, updated


def test_storage_validates_tenant_and_expected_dependency_identity(monkeypatch):
    storage, updated = _storage(monkeypatch)
    manifest = _build_manifest()

    wrong_tenant = manifest.model_copy(update={"user_id": "other-user"})
    with pytest.raises(ValueError, match="tenant"):
        storage.record_evaluation_manifest(
            "startup-manifest-1",
            wrong_tenant,
            manifest_identity=_manifest_identity(),
            partner_execution_prompt_version="partner-prompt-hash",
        )

    wrong_identity = deepcopy(_manifest_identity())
    wrong_identity["dependency_identity"]["policy_hash"] = "different-hash"
    with pytest.raises(ValueError, match="dependency"):
        storage.record_evaluation_manifest(
            "startup-manifest-1",
            manifest,
            manifest_identity=wrong_identity,
            partner_execution_prompt_version="partner-prompt-hash",
        )

    assert updated == []


def test_storage_merges_validated_manifest_without_losing_stage_data(monkeypatch):
    startup = _startup()
    startup.agent_trace = {"scout": {"status": "completed"}}
    storage, updated = _storage(monkeypatch, startup)
    manifest = _build_manifest(run_id="pipeline-run-4")

    assert storage.record_evaluation_manifest(
        "startup-manifest-1",
        manifest,
        manifest_identity=_manifest_identity(),
        partner_execution_prompt_version="partner-prompt-hash",
    ) is True
    assert len(updated) == 1
    trace = updated[0][1]["agent_trace"]
    assert trace["scout"] == {"status": "completed"}
    assert trace["evaluation_manifest"]["pipeline_run_id"] == "pipeline-run-4"


def test_partner_persistence_uses_captured_identity_without_environment_reads(
    monkeypatch,
):
    run_id = "8c24745e-1d48-4ea1-b2fd-f7835f64ad73"
    startup = _startup()
    partner_info = startup.partner_info
    startup.partner_info = None
    startup.agent_trace = {
        "scout": {"status": "completed", "pipeline_run_id": run_id},
        "reviewer": {"status": "completed", "pipeline_run_id": run_id},
    }
    storage, updated = _storage(monkeypatch, startup)
    supabase_storage = importlib.import_module("legacy_supabase.storage")
    monkeypatch.setattr(
        supabase_storage.os,
        "getenv",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("persistence must not read mutable environment")
        ),
    )

    assert storage.add_partner_decision(
        startup.startup_id,
        partner_info,
        pipeline_run_id=run_id,
        evaluation_manifest_identity=_manifest_identity(),
        partner_execution_prompt_version="partner-prompt-hash",
    ) is True

    assert len(updated) == 1
    trace = updated[0][1]["agent_trace"]
    assert trace["partner"]["status"] == "completed"
    assert trace["evaluation_manifest"]["evaluation_path"] == "manual_lookup"
    assert (
        trace["evaluation_manifest"]["stage_identities"]["partner"]
        ["model_identity"]["model_id"]
        == "gpt-5-mini"
    )
    assert trace["evaluation_manifest"]["user_id"] == "manifest-user"


def _stage_trace(*, scout_run: str, reviewer_run: str, partner_run: str, prior=None):
    trace = {
        "scout": {"status": "completed", "pipeline_run_id": scout_run},
        "reviewer": {"status": "completed", "pipeline_run_id": reviewer_run},
        "partner": {"status": "completed", "pipeline_run_id": partner_run},
    }
    if prior is not None:
        trace["evaluation_manifest"] = prior.model_dump(mode="json")
    return trace


def test_rerun_manifest_reuses_original_scout_identity_not_unused_current_model():
    original = _startup()
    original.agent_trace = _stage_trace(
        scout_run="original-run",
        reviewer_run="original-run",
        partner_run="original-run",
    )
    original_manifest = _manifest_module().build_evaluation_manifest(
        original,
        pipeline_run_id="original-run",
        evaluation_path="manual_lookup",
        manifest_identity=_manifest_identity(),
        partner_execution_prompt_version="partner-prompt-hash",
    )

    rerun = _startup()
    rerun.agent_trace = _stage_trace(
        scout_run="original-run",
        reviewer_run="rerun-2",
        partner_run="rerun-2",
        prior=original_manifest,
    )
    rerun_identity = deepcopy(_manifest_identity())
    rerun_identity["model_identities"]["scout"] = _model_identity(
        "new-unused-scout-model", "new-unused-scout-config"
    )

    manifest = _manifest_module().build_evaluation_manifest(
        rerun,
        pipeline_run_id="rerun-2",
        evaluation_path="rerun",
        manifest_identity=rerun_identity,
        partner_execution_prompt_version="partner-prompt-hash",
    )

    scout = manifest.stage_identities["scout"]
    assert manifest.manifest_version == "evaluation-manifest-v3"
    assert scout.execution_state == "reused"
    assert scout.source_pipeline_run_id == "original-run"
    assert scout.model_identity.model_id == "gpt-5-nano"
    assert manifest.stage_identities["reviewer"].execution_state == "executed"
    assert manifest.stage_identities["partner"].execution_state == "executed"
    assert "new-unused-scout-model" not in str(manifest.model_dump(mode="json"))


def test_manifest_marks_unexecuted_reviewer_and_rule_partner_prompts_not_run():
    startup = _startup()
    startup.review_info.reviews = startup.review_info.reviews[:2]
    startup.partner_info.prompt_version = None
    startup.partner_info.llm_fallback_reason = None
    startup.agent_trace = _stage_trace(
        scout_run="rule-run",
        reviewer_run="rule-run",
        partner_run="rule-run",
    )

    manifest = _manifest_module().build_evaluation_manifest(
        startup,
        pipeline_run_id="rule-run",
        evaluation_path="manual_lookup",
        manifest_identity=_manifest_identity(),
        partner_execution_prompt_version=None,
    )

    opportunist = manifest.stage_identities["reviewer"].prompt_identities[
        "OpportunistReviewer"
    ]
    partner = manifest.stage_identities["partner"]
    assert opportunist.execution_state == "not_run"
    assert opportunist.execution_prompt_version is None
    assert partner.prompt_identities["decision"].execution_state == "not_run"
    assert partner.model_identity is None


def test_manifest_rejects_forged_partner_prompt_against_engine_execution_identity():
    startup = _startup()
    startup.partner_info.prompt_version = "forged-output-hash"
    startup.agent_trace = _stage_trace(
        scout_run="forgery-run",
        reviewer_run="forgery-run",
        partner_run="forgery-run",
    )

    with pytest.raises(ValueError, match="partner execution prompt"):
        _manifest_module().build_evaluation_manifest(
            startup,
            pipeline_run_id="forgery-run",
            evaluation_path="manual_lookup",
            manifest_identity=_manifest_identity(),
            partner_execution_prompt_version="actual-engine-invocation-hash",
        )
