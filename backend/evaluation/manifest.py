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
    if not isinstance(scoring, dict):
        raise ValueError("review policy identity is required for governed persistence")
    expected_policy = {
        "policy_version_id": dependency.policy_version_id,
        "policy_hash": dependency.policy_hash,
        "rubric_version": dependency.rubric_version,
    }
    for key, expected in expected_policy.items():
        if _required_text(scoring.get(key), field=f"review {key}") != expected:
            raise ValueError(
                f"review policy identity {key} does not match construction identity"
            )
    expected_runtime = {
        "scoring_runtime_version": dependency.scoring_runtime_version,
        "scoring_runtime_hash": dependency.scoring_runtime_hash,
    }
    for key, expected in expected_runtime.items():
        if _required_text(scoring.get(key), field=f"review {key}") != expected:
            raise ValueError(
                f"review runtime identity {key} does not match construction identity"
            )


def _execution_prompt_manifest(
    startup: Startup,
    *,
    evaluation_path: EvaluationPath,
    identity: EvaluationManifestIdentity,
) -> Dict[str, str]:
    prompts = identity.construction_prompt_versions
    scout_prompt = _required_text(
        startup.scout_info.prompt_version,
        field="scout prompt identity",
    )
    # A rerun deliberately reuses the original Scout artifact. Fresh discovery
    # must prove that the persisted prompt is the exact constructed persona.
    if evaluation_path != "rerun":
        scout_key = f"scout.{startup.scout_info.scout_type}"
        expected_scout_prompt = prompts.get(scout_key)
        if expected_scout_prompt is None or scout_prompt != expected_scout_prompt:
            raise ValueError(
                "scout prompt identity does not match construction identity"
            )

    execution: Dict[str, str] = {
        "scout": scout_prompt,
        **{
            f"reviewer.{reviewer_type}": "not-executed"
            for reviewer_type in _REVIEWER_TYPES
        },
        "partner": "not-executed:rule-based",
    }
    reviews = startup.review_info.reviews if startup.review_info else None
    seen_reviewers: set[str] = set()
    for review in reviews or []:
        reviewer_type = str(review.reviewer_type)
        key = f"reviewer.{reviewer_type}"
        if reviewer_type in seen_reviewers:
            raise ValueError(f"duplicate reviewer prompt identity for {reviewer_type}")
        seen_reviewers.add(reviewer_type)
        actual = _required_text(
            review.prompt_version,
            field=f"{reviewer_type} prompt identity",
        )
        if actual != prompts.get(key):
            raise ValueError(
                f"{reviewer_type} prompt identity does not match construction identity"
            )
        execution[key] = actual

    partner = startup.partner_info
    if partner is None:
        raise ValueError("partner identity is required for governed persistence")
    partner_prompt = str(partner.prompt_version or "").strip()
    if partner_prompt:
        execution["partner"] = partner_prompt
    elif str(partner.llm_fallback_reason or "").strip():
        raise ValueError(
            "partner prompt identity is required when the LLM fallback executed"
        )
    return execution


def build_evaluation_manifest(
    startup: Startup,
    *,
    pipeline_run_id: str,
    evaluation_path: EvaluationPath,
    manifest_identity: Mapping[str, Any] | EvaluationManifestIdentity,
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
    execution_prompts = _execution_prompt_manifest(
        startup,
        evaluation_path=evaluation_path,
        identity=identity,
    )
    dependency = identity.dependency_identity
    dependency_payload = dependency.model_dump(mode="python")
    return EvaluationManifest(
        pipeline_run_id=run_id,
        evaluation_path=evaluation_path,
        **dependency_payload,
        models={
            stage: model_identity.model_id
            for stage, model_identity in identity.model_identities.items()
        },
        model_identities=identity.model_identities,
        construction_prompt_versions=identity.construction_prompt_versions,
        prompt_versions=execution_prompts,
    )


def validate_evaluation_manifest_for_persistence(
    manifest: Mapping[str, Any] | EvaluationManifest,
    *,
    manifest_identity: Mapping[str, Any] | EvaluationManifestIdentity,
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
    if validated.model_identities != identity.model_identities:
        raise ValueError(
            "evaluation manifest model identity does not match construction identity"
        )
    if (
        validated.construction_prompt_versions
        != identity.construction_prompt_versions
    ):
        raise ValueError(
            "evaluation manifest prompt identity does not match construction identity"
        )
    return validated
