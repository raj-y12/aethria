"""Tenant policy preview/publish helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from services.scoring.policy_compiler import (
    PolicyValidationError,
    compile_policy_from_fund_config,
    validate_compiled_policy_bundle,
)
from supabase_doc_store import list_append, list_get_all
from utils.settings_loader import load_settings, save_settings


POLICY_TABLE = "fund_policy_versions"


class PolicyNotPublishedError(RuntimeError):
    """The tenant has no hash-bound published policy available for evaluation."""


def preview_policy(fund_config: Dict[str, Any] | None) -> Dict[str, Any]:
    return compile_policy_from_fund_config(fund_config or {})


def load_active_policy(user_id: str) -> Dict[str, Any]:
    settings = load_settings(user_id)
    fund_config = settings.get("fund_config") if isinstance(settings.get("fund_config"), dict) else {}
    active_id = str(fund_config.get("activePolicyVersionId") or "").strip()
    if active_id:
        for version in list_get_all(POLICY_TABLE, user_id=user_id):
            if str(version.get("policy_version_id") or version.get("id") or "") == active_id:
                return dict(version)
    return compile_policy_from_fund_config(fund_config)


def load_published_policy(
    user_id: str, *, settings: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """Load the exact active published policy, failing closed on draft fallback."""
    settings = settings if isinstance(settings, dict) else load_settings(user_id)
    fund_config = (
        settings.get("fund_config")
        if isinstance(settings.get("fund_config"), dict)
        else {}
    )
    active_id = str(fund_config.get("activePolicyVersionId") or "").strip()
    published_hash = str(fund_config.get("publishedPolicyHash") or "").strip()
    if not active_id or not published_hash:
        raise PolicyNotPublishedError(
            "An active published scoring policy is required before evaluation"
        )
    for version in list_get_all(POLICY_TABLE, user_id=user_id):
        candidate_id = str(
            version.get("policy_version_id") or version.get("id") or ""
        ).strip()
        candidate_hash = str(version.get("policy_hash") or "").strip()
        if candidate_id == active_id and candidate_hash == published_hash:
            try:
                validated = validate_compiled_policy_bundle(dict(version))
            except PolicyValidationError as exc:
                detail = str(exc).lower()
                reason = "hash" if "hash" in detail else "complete decision bundle"
                raise PolicyNotPublishedError(
                    f"The active published policy has an invalid {reason}"
                ) from exc
            return validated
    raise PolicyNotPublishedError(
        "The active published scoring policy could not be resolved"
    )


def publish_policy(user_id: str, fund_config: Dict[str, Any] | None = None) -> Dict[str, Any]:
    settings = load_settings(user_id, use_cache=False)
    fc = dict(fund_config if isinstance(fund_config, dict) else settings.get("fund_config") or {})
    compiled = compile_policy_from_fund_config(fc, require_publish_ready=True)
    existing_versions = list_get_all(POLICY_TABLE, user_id=user_id)
    for version in existing_versions:
        if version.get("policy_hash") == compiled["policy_hash"]:
            try:
                active = validate_compiled_policy_bundle(dict(version))
            except PolicyValidationError:
                continue
            _set_active_policy(settings, active, user_id, fund_config=fc)
            return active

    policy_id = f"policy_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{compiled['policy_hash'][:8]}"
    published = {
        **compiled,
        "id": policy_id,
        "policy_version_id": policy_id,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    list_append(POLICY_TABLE, published, user_id=user_id)
    _set_active_policy(settings, published, user_id, fund_config=fc)
    return published


def _set_active_policy(
    settings: Dict[str, Any],
    policy: Dict[str, Any],
    user_id: str,
    *,
    fund_config: Dict[str, Any] | None = None,
) -> None:
    current = dict(settings)
    next_fund_config = dict(
        fund_config
        if isinstance(fund_config, dict)
        else current.get("fund_config")
        if isinstance(current.get("fund_config"), dict)
        else {}
    )
    next_fund_config["activePolicyVersionId"] = policy["policy_version_id"]
    next_fund_config["publishedPolicyHash"] = policy["policy_hash"]
    next_fund_config["draftPolicyHash"] = policy["policy_hash"]
    next_fund_config["lastPublishedAt"] = policy.get("published_at") or policy.get("generated_at")
    current["fund_config"] = next_fund_config
    save_settings(current, user_id)
