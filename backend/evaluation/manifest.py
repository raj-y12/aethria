"""Build immutable dependency manifests for current-pipeline evaluations."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Literal, Mapping

from core.policy_resolver import get_partner_rules, get_policy_file_path
from models import EvaluationManifest, Startup


EvaluationPath = Literal["manual_lookup", "autonomous_discovery", "rerun"]
_MODEL_KEYS = ("scout", "reviewer", "partner")
_REVIEWER_TYPES = (
    "DefaultReviewer",
    "SkepticalReviewer",
    "OpportunistReviewer",
)


def stable_document_hash(document: Any) -> str:
    canonical = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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


def _scoring_metadata(startup: Startup) -> Dict[str, Any]:
    if startup.review_info is None:
        return {}
    structured = startup.review_info.structured_scoring
    return dict(structured) if isinstance(structured, dict) else {}


def build_evaluation_manifest(
    startup: Startup,
    *,
    pipeline_run_id: str,
    evaluation_path: EvaluationPath,
    model_metadata: Mapping[str, Any],
) -> EvaluationManifest:
    run_id = str(pipeline_run_id or "").strip()
    if not run_id:
        raise ValueError("pipeline_run_id is required for an evaluation manifest")
    scoring = _scoring_metadata(startup)
    partner_rules = get_partner_rules()
    rules_version = _known_or_unknown(
        partner_rules.get("version") if isinstance(partner_rules, dict) else None
    )
    return EvaluationManifest(
        pipeline_run_id=run_id,
        evaluation_path=evaluation_path,
        models=_model_manifest(model_metadata),
        prompt_versions=_prompt_manifest(startup),
        policy_version_id=scoring.get("policy_version_id"),
        policy_hash=scoring.get("policy_hash"),
        rubric_version=scoring.get("rubric_version"),
        partner_rules_version=rules_version,
        partner_rules_hash=stable_document_hash(partner_rules),
    )
