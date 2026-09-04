"""Build and validate immutable identities for governed evaluations."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Literal, Mapping

from models import (
    EvaluationDependencyIdentity,
    EvaluationManifest,
    EvaluationManifestIdentity,
    EvaluationModelIdentity,
    EvaluationPromptIdentity,
    EvaluationStageIdentity,
    Startup,
)


EvaluationPath = Literal["manual_lookup", "autonomous_discovery", "rerun"]
_REVIEWER_TYPES = (
    "DefaultReviewer",
    "SkepticalReviewer",
    "OpportunistReviewer",
)


def stable_document_hash(document: Any) -> str:
    """Return a full canonical SHA-256 identity without reading mutable state."""
    canonical = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_model_identity(
    *,
    provider_id: str,
    model_id: str,
    configuration_id: str,
    configuration: Mapping[str, Any],
) -> EvaluationModelIdentity:
    """Capture a model/provider request configuration without secrets."""
    return EvaluationModelIdentity(
        provider_id=str(provider_id or "").strip(),
        model_id=str(model_id or "").strip(),
        configuration_id=str(configuration_id or "").strip(),
        configuration_hash=stable_document_hash(dict(configuration)),
    )


def capture_evaluation_manifest_identity(
    *,
    dependency_identity: Mapping[str, Any] | EvaluationDependencyIdentity,
    model_identities: Mapping[str, Any],
    construction_prompt_versions: Mapping[str, Any],
) -> EvaluationManifestIdentity:
    """Take one defensive, validated construction-time identity snapshot."""
    payload = {
        "dependency_identity": (
            dependency_identity.model_dump(mode="python")
            if isinstance(dependency_identity, EvaluationDependencyIdentity)
            else dict(dependency_identity)
        ),
        "model_identities": {
            str(key): (
                value.model_dump(mode="python")
                if isinstance(value, EvaluationModelIdentity)
                else dict(value)
            )
            for key, value in model_identities.items()
        },
        "construction_prompt_versions": {
            str(key): str(value or "").strip()
            for key, value in construction_prompt_versions.items()
        },
    }
    return EvaluationManifestIdentity.model_validate(payload)


def _required_text(value: Any, *, field: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field} is required for governed evaluation persistence")
    return normalized


def _validate_startup_dependency_identity(
    startup: Startup,
    identity: EvaluationManifestIdentity,
) -> None:
    dependency = identity.dependency_identity
    review = startup.review_info
    if review is None:
        raise ValueError("review identity is required for governed evaluation persistence")
    thesis_version = _required_text(
        review.fund_thesis_version_id,
        field="review thesis version identity",
    )
    if thesis_version != dependency.thesis_version_id:
        raise ValueError(
            "review thesis identity does not match the construction identity"
        )
    scoring = review.structured_scoring
    # Qualitative reviewers no longer persist a numeric structured trace. Their
    # policy/runtime identity is carried as separate provenance fields instead.
    identity_source = scoring if isinstance(scoring, dict) else review.model_dump(mode="python")
    expected_policy = {
        "policy_version_id": dependency.policy_version_id,
        "policy_hash": dependency.policy_hash,
        "rubric_version": dependency.rubric_version,
    }
    for key, expected in expected_policy.items():
        if _required_text(identity_source.get(key), field=f"review {key}") != expected:
            raise ValueError(
                f"review policy identity {key} does not match construction identity"
            )
    expected_runtime = {
        "scoring_runtime_version": dependency.scoring_runtime_version,
        "scoring_runtime_hash": dependency.scoring_runtime_hash,
    }
    for key, expected in expected_runtime.items():
        if _required_text(identity_source.get(key), field=f"review {key}") != expected:
            raise ValueError(
                f"review runtime identity {key} does not match construction identity"
            )


def _trace_payload(startup: Startup) -> Dict[str, Any]:
    return dict(startup.agent_trace) if isinstance(startup.agent_trace, dict) else {}


def _stage_trace_run_id(startup: Startup, stage: str) -> str | None:
    trace = _trace_payload(startup).get(stage)
    if not isinstance(trace, dict):
        return None
    return str(trace.get("pipeline_run_id") or "").strip() or None


def _prior_manifest_payload(startup: Startup) -> Dict[str, Any]:
    prior = _trace_payload(startup).get("evaluation_manifest")
    return dict(prior) if isinstance(prior, dict) else {}


def _prior_model_identity(
    prior: Mapping[str, Any], stage: str
) -> EvaluationModelIdentity | None:
    stage_identities = prior.get("stage_identities")
    raw: Any = None
    if isinstance(stage_identities, dict):
        stage_identity = stage_identities.get(stage)
        if isinstance(stage_identity, dict):
            raw = stage_identity.get("model_identity")
    if raw is None:
        model_identities = prior.get("model_identities")
        if isinstance(model_identities, dict):
            raw = model_identities.get(stage)
    if not isinstance(raw, dict):
        return None
    return EvaluationModelIdentity.model_validate(raw)


def _prior_prompt_identity(
    prior: Mapping[str, Any],
    *,
    stage: str,
    prompt_name: str,
    legacy_execution_key: str,
    legacy_construction_key: str,
) -> EvaluationPromptIdentity | None:
    stage_identities = prior.get("stage_identities")
    if isinstance(stage_identities, dict):
        stage_identity = stage_identities.get(stage)
        if isinstance(stage_identity, dict):
            prompts = stage_identity.get("prompt_identities")
            if isinstance(prompts, dict) and isinstance(prompts.get(prompt_name), dict):
                return EvaluationPromptIdentity.model_validate(prompts[prompt_name])

    execution_prompts = prior.get("prompt_versions")
    construction_prompts = prior.get("construction_prompt_versions")
    execution_version = (
        str(execution_prompts.get(legacy_execution_key) or "").strip()
        if isinstance(execution_prompts, dict)
        else ""
    )
    if not execution_version or execution_version.startswith("not-executed"):
        return None
    construction_version = (
        str(construction_prompts.get(legacy_construction_key) or "").strip()
        if isinstance(construction_prompts, dict)
        else ""
    )
    return EvaluationPromptIdentity(
        execution_state="reused",
        construction_prompt_key=(
            legacy_construction_key if construction_version else None
        ),
        construction_prompt_version=construction_version or None,
        execution_prompt_version=execution_version,
    )


def _artifact_stage_state(
    *,
    artifact_exists: bool,
    trace_run_id: str | None,
    pipeline_run_id: str,
) -> Literal["executed", "reused", "not_run"]:
    if trace_run_id == pipeline_run_id:
        return "executed"
    if artifact_exists:
        return "reused"
    return "not_run"


def _not_run_prompt() -> EvaluationPromptIdentity:
    return EvaluationPromptIdentity(execution_state="not_run")


def _stage_identity_manifest(
    startup: Startup,
    *,
    pipeline_run_id: str,
    evaluation_path: EvaluationPath,
    identity: EvaluationManifestIdentity,
    partner_execution_prompt_version: str | None,
) -> Dict[str, EvaluationStageIdentity]:
    prompts = identity.construction_prompt_versions
    prior = _prior_manifest_payload(startup)

    scout_run = _stage_trace_run_id(startup, "scout")
    scout_state = _artifact_stage_state(
        artifact_exists=startup.scout_info is not None,
        trace_run_id=scout_run,
        pipeline_run_id=pipeline_run_id,
    )
    if evaluation_path == "rerun" and scout_state == "executed":
        raise ValueError("rerun Scout identity must be reused, not executed")
    scout_prompt = _required_text(
        startup.scout_info.prompt_version, field="scout prompt identity"
    )
    scout_prompt_identity: EvaluationPromptIdentity
    if scout_state == "executed":
        scout_key = f"scout.{startup.scout_info.scout_type}"
        expected_scout_prompt = prompts.get(scout_key)
        if expected_scout_prompt is None or scout_prompt != expected_scout_prompt:
            raise ValueError(
                "scout prompt identity does not match executed construction identity"
            )
        scout_prompt_identity = EvaluationPromptIdentity(
            execution_state="executed",
            construction_prompt_key=scout_key,
            construction_prompt_version=expected_scout_prompt,
            execution_prompt_version=scout_prompt,
        )
    elif scout_state == "reused":
        prior_scout = _prior_prompt_identity(
            prior,
            stage="scout",
            prompt_name="discovery",
            legacy_execution_key="scout",
            legacy_construction_key=f"scout.{startup.scout_info.scout_type}",
        )
        if (
            prior_scout is not None
            and prior_scout.execution_prompt_version != scout_prompt
        ):
            raise ValueError("reused scout prompt identity does not match its source")
        scout_prompt_identity = EvaluationPromptIdentity(
            execution_state="reused",
            construction_prompt_key=(
                prior_scout.construction_prompt_key if prior_scout else None
            ),
            construction_prompt_version=(
                prior_scout.construction_prompt_version if prior_scout else None
            ),
            execution_prompt_version=scout_prompt,
        )
    else:  # pragma: no cover - Startup currently requires scout_info
        scout_prompt_identity = _not_run_prompt()

    reviewer_run = _stage_trace_run_id(startup, "reviewer")
    reviewer_state = _artifact_stage_state(
        artifact_exists=startup.review_info is not None,
        trace_run_id=reviewer_run,
        pipeline_run_id=pipeline_run_id,
    )
    reviewer_prompt_identities: Dict[str, EvaluationPromptIdentity] = {
        reviewer_type: _not_run_prompt() for reviewer_type in _REVIEWER_TYPES
    }
    reviews = startup.review_info.reviews if startup.review_info else None
    seen_reviewers: set[str] = set()
    for review in reviews or []:
        reviewer_type = str(review.reviewer_type)
        construction_key = f"reviewer.{reviewer_type}"
        if reviewer_type in seen_reviewers:
            raise ValueError(f"duplicate reviewer prompt identity for {reviewer_type}")
        seen_reviewers.add(reviewer_type)
        actual = _required_text(
            review.prompt_version,
            field=f"{reviewer_type} prompt identity",
        )
        if reviewer_state == "executed":
            expected = prompts.get(construction_key)
            if actual != expected:
                raise ValueError(
                    f"{reviewer_type} prompt identity does not match executed "
                    "construction identity"
                )
            reviewer_prompt_identities[reviewer_type] = EvaluationPromptIdentity(
                execution_state="executed",
                construction_prompt_key=construction_key,
                construction_prompt_version=expected,
                execution_prompt_version=actual,
            )
        elif reviewer_state == "reused":
            prior_reviewer = _prior_prompt_identity(
                prior,
                stage="reviewer",
                prompt_name=reviewer_type,
                legacy_execution_key=construction_key,
                legacy_construction_key=construction_key,
            )
            if (
                prior_reviewer is not None
                and prior_reviewer.execution_prompt_version != actual
            ):
                raise ValueError(
                    f"reused {reviewer_type} prompt identity does not match its source"
                )
            reviewer_prompt_identities[reviewer_type] = EvaluationPromptIdentity(
                execution_state="reused",
                construction_prompt_key=(
                    prior_reviewer.construction_prompt_key
                    if prior_reviewer
                    else None
                ),
                construction_prompt_version=(
                    prior_reviewer.construction_prompt_version
                    if prior_reviewer
                    else None
                ),
                execution_prompt_version=actual,
            )

    partner = startup.partner_info
    if partner is None:
        raise ValueError("partner identity is required for governed persistence")
    partner_run = _stage_trace_run_id(startup, "partner")
    if partner_run != pipeline_run_id:
        raise ValueError("partner stage identity was not executed by this pipeline run")
    actual_partner_prompt = str(partner.prompt_version or "").strip()
    expected_partner_prompt = str(partner_execution_prompt_version or "").strip()
    if expected_partner_prompt:
        if actual_partner_prompt != expected_partner_prompt:
            raise ValueError(
                "partner execution prompt identity does not match engine invocation"
            )
        partner_prompt_identity = EvaluationPromptIdentity(
            execution_state="executed",
            construction_prompt_key="partner.template",
            construction_prompt_version=prompts["partner.template"],
            execution_prompt_version=expected_partner_prompt,
        )
        partner_model_identity = identity.model_identities["partner"]
    else:
        if actual_partner_prompt:
            raise ValueError(
                "partner execution prompt identity was persisted without an engine invocation"
            )
        partner_prompt_identity = _not_run_prompt()
        partner_model_identity = None
    if (
        partner_prompt_identity.execution_state == "not_run"
        and str(partner.llm_fallback_reason or "").strip()
    ):
        raise ValueError(
            "partner prompt identity is required when the LLM fallback executed"
        )

    return {
        "scout": EvaluationStageIdentity(
            execution_state=scout_state,
            source_pipeline_run_id=scout_run,
            model_identity=(
                identity.model_identities["scout"]
                if scout_state == "executed"
                else _prior_model_identity(prior, "scout")
                if scout_state == "reused"
                else None
            ),
            prompt_identities={"discovery": scout_prompt_identity},
        ),
        "reviewer": EvaluationStageIdentity(
            execution_state=reviewer_state,
            source_pipeline_run_id=reviewer_run,
            model_identity=(
                identity.model_identities["reviewer"]
                if reviewer_state == "executed"
                else _prior_model_identity(prior, "reviewer")
                if reviewer_state == "reused"
                else None
            ),
            prompt_identities=reviewer_prompt_identities,
        ),
        "partner": EvaluationStageIdentity(
            execution_state="executed",
            source_pipeline_run_id=partner_run,
            model_identity=partner_model_identity,
            prompt_identities={"decision": partner_prompt_identity},
        ),
    }


def build_evaluation_manifest(
    startup: Startup,
    *,
    pipeline_run_id: str,
    evaluation_path: EvaluationPath,
    manifest_identity: Mapping[str, Any] | EvaluationManifestIdentity,
    partner_execution_prompt_version: str | None,
) -> EvaluationManifest:
    """Bind execution evidence to the exact dependencies captured at construction."""
    run_id = _required_text(pipeline_run_id, field="pipeline_run_id")
    # Revalidate from a dump to sever aliases to mutable caller dictionaries.
    identity = EvaluationManifestIdentity.model_validate(
        manifest_identity.model_dump(mode="python")
        if isinstance(manifest_identity, EvaluationManifestIdentity)
        else dict(manifest_identity)
    )
    _validate_startup_dependency_identity(startup, identity)
    stage_identities = _stage_identity_manifest(
        startup,
        pipeline_run_id=run_id,
        evaluation_path=evaluation_path,
        identity=identity,
        partner_execution_prompt_version=partner_execution_prompt_version,
    )
    dependency = identity.dependency_identity
    dependency_payload = dependency.model_dump(mode="python")
    return EvaluationManifest(
        pipeline_run_id=run_id,
        evaluation_path=evaluation_path,
        **dependency_payload,
        stage_identities=stage_identities,
    )


def validate_evaluation_manifest_for_persistence(
    manifest: Mapping[str, Any] | EvaluationManifest,
    *,
    manifest_identity: Mapping[str, Any] | EvaluationManifestIdentity,
    partner_execution_prompt_version: str | None,
    user_id: str,
) -> EvaluationManifest:
    """Fail closed unless tenant and captured dependencies are byte-for-byte equal."""
    validated = EvaluationManifest.model_validate(manifest)
    identity = EvaluationManifestIdentity.model_validate(
        manifest_identity.model_dump(mode="python")
        if isinstance(manifest_identity, EvaluationManifestIdentity)
        else dict(manifest_identity)
    )
    expected_user_id = str(user_id or "").strip()
    if validated.user_id != expected_user_id:
        raise ValueError("evaluation manifest tenant does not match storage tenant")

    dependency_fields = tuple(
        EvaluationDependencyIdentity.model_fields.keys()
    )
    actual_dependency = {
        key: getattr(validated, key) for key in dependency_fields
    }
    if actual_dependency != identity.dependency_identity.model_dump(mode="python"):
        raise ValueError(
            "evaluation manifest dependency identity does not match construction identity"
        )
    for stage, stage_identity in validated.stage_identities.items():
        if stage_identity.execution_state != "executed":
            continue
        if stage in {"scout", "reviewer"}:
            if stage_identity.model_identity != identity.model_identities[stage]:
                raise ValueError(
                    f"executed {stage} model identity does not match construction identity"
                )
        for prompt in stage_identity.prompt_identities.values():
            if prompt.execution_state != "executed":
                continue
            construction_key = str(prompt.construction_prompt_key or "")
            if (
                identity.construction_prompt_versions.get(construction_key)
                != prompt.construction_prompt_version
            ):
                raise ValueError(
                    f"executed {stage} prompt identity does not match construction identity"
                )

    partner_stage = validated.stage_identities["partner"]
    partner_prompt = partner_stage.prompt_identities["decision"]
    expected_partner_prompt = str(partner_execution_prompt_version or "").strip()
    if expected_partner_prompt:
        if (
            partner_prompt.execution_state != "executed"
            or partner_prompt.execution_prompt_version != expected_partner_prompt
            or partner_stage.model_identity != identity.model_identities["partner"]
        ):
            raise ValueError(
                "partner execution prompt identity does not match engine invocation"
            )
    elif (
        partner_prompt.execution_state != "not_run"
        or partner_stage.model_identity is not None
    ):
        raise ValueError(
            "partner model identity cannot be recorded when no model invocation ran"
        )
    return validated
