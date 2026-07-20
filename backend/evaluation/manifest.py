"""Build immutable dependency manifests for current-pipeline evaluations."""

from __future__ import annotations

from typing import Any, Dict, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field

from models import EvaluationManifest, Startup


EvaluationPath = Literal["manual_lookup", "autonomous_discovery", "rerun"]
_MODEL_KEYS = ("scout", "reviewer", "partner")
_REVIEWER_TYPES = (
    "DefaultReviewer",
    "SkepticalReviewer",
    "OpportunistReviewer",
)


class EvaluationDependencyIdentity(BaseModel):
    """Exact dependency identity already consumed by governed evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_version_id: str = Field(min_length=1)
    policy_hash: str = Field(min_length=1)
    rubric_version: str = Field(min_length=1)
    partner_rules_version: str = Field(min_length=1)
    partner_rules_hash: str = Field(min_length=1)


def _known_or_unknown(value: Any) -> str:
    normalized = str(value or "").strip()
    return normalized or "unknown"


def _model_manifest(model_metadata: Mapping[str, Any]) -> Dict[str, str]:
    return {
        key: _known_or_unknown(model_metadata.get(key))
        for key in _MODEL_KEYS
    }


def _prompt_manifest(startup: Startup) -> Dict[str, str]:
    prompts: Dict[str, str] = {
        "scout": _known_or_unknown(startup.scout_info.prompt_version),
        **{f"reviewer.{reviewer_type}": "unknown" for reviewer_type in _REVIEWER_TYPES},
        "partner": _known_or_unknown(
            startup.partner_info.prompt_version if startup.partner_info else None
        ),
    }
    reviews = startup.review_info.reviews if startup.review_info else None
    for review in reviews or []:
        prompts[f"reviewer.{review.reviewer_type}"] = _known_or_unknown(
            review.prompt_version
        )
    return prompts


def build_evaluation_manifest(
    startup: Startup,
    *,
    pipeline_run_id: str,
    evaluation_path: EvaluationPath,
    model_metadata: Mapping[str, Any],
    dependency_identity: Mapping[str, Any] | EvaluationDependencyIdentity,
) -> EvaluationManifest:
    run_id = str(pipeline_run_id or "").strip()
    if not run_id:
        raise ValueError("pipeline_run_id is required for an evaluation manifest")
    identity = EvaluationDependencyIdentity.model_validate(
        dependency_identity
    )
    return EvaluationManifest(
        pipeline_run_id=run_id,
        evaluation_path=evaluation_path,
        models=_model_manifest(model_metadata),
        prompt_versions=_prompt_manifest(startup),
        policy_version_id=identity.policy_version_id,
        policy_hash=identity.policy_hash,
        rubric_version=identity.rubric_version,
        partner_rules_version=identity.partner_rules_version,
        partner_rules_hash=identity.partner_rules_hash,
    )
