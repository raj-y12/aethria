"""Explicit, tenant-scoped upgrade for legacy published scoring policies."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict

from services.scoring.policy_compiler import (
    PolicyValidationError,
    compile_policy_from_fund_config,
    validate_compiled_policy_bundle,
)
from supabase_client import get_service_client
from supabase_doc_store import doc_get_strict, list_get_all_strict
from tenant_context import require_user_id


POLICY_TABLE = "fund_policy_versions"
SETTINGS_TABLE = "settings"


class PolicyUpgradeStoreUnavailable(RuntimeError):
    """The authoritative policy/settings transaction could not be completed."""


class PolicyUpgradeMode(str, Enum):
    DRY_RUN = "dry_run"
    APPLY = "apply"


class PolicyUpgradeStatus(str, Enum):
    UPGRADE_REQUIRED = "upgrade_required"
    APPLIED = "applied"
    ALREADY_CURRENT = "already_current"


class ExistingPolicyState(str, Enum):
    MISSING = "missing"
    LEGACY = "legacy"
    COMPLETE = "complete"


class PublishedPolicyUpgradeReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: str
    mode: PolicyUpgradeMode
    status: PolicyUpgradeStatus
    old_policy_state: ExistingPolicyState
    old_policy_id: Optional[str] = None
    old_policy_hash: Optional[str] = None
    new_policy_id: str
    new_policy_hash: str
    appended: bool = False
    pointer_switched: bool = False


def _load_authoritative_state(user_id: str) -> tuple[Dict[str, Any], list[Dict[str, Any]]]:
    try:
        settings = doc_get_strict(SETTINGS_TABLE, user_id, user_id=user_id)
        versions = list_get_all_strict(POLICY_TABLE, user_id=user_id)
    except Exception as exc:
        raise PolicyUpgradeStoreUnavailable(
            "Published policy upgrade could not read authoritative tenant state"
        ) from exc
    if not isinstance(settings, dict):
        raise PolicyUpgradeStoreUnavailable(
            "Published policy upgrade requires an existing tenant settings record"
        )
    return deepcopy(settings), [dict(version) for version in versions]


def _existing_policy_state(
    versions: list[Dict[str, Any]],
    *,
    active_id: str,
    published_hash: str,
) -> tuple[ExistingPolicyState, Optional[Dict[str, Any]]]:
    if not active_id or not published_hash:
        return ExistingPolicyState.MISSING, None
    active = next(
        (
            version
            for version in versions
            if str(version.get("policy_version_id") or version.get("id") or "").strip()
            == active_id
        ),
        None,
    )
    if active is None:
        return ExistingPolicyState.MISSING, None
    if str(active.get("policy_hash") or "").strip() != published_hash:
        return ExistingPolicyState.LEGACY, None
    try:
        return ExistingPolicyState.COMPLETE, validate_compiled_policy_bundle(active)
    except PolicyValidationError:
        return ExistingPolicyState.LEGACY, None


def _apply_upgrade_transaction(
    *,
    user_id: str,
    expected_policy_id: str,
    expected_policy_hash: str,
    policy_record: Dict[str, Any],
    settings_data: Dict[str, Any],
) -> Dict[str, Any]:
    params = {
        "p_user_id": user_id,
        "p_expected_policy_id": expected_policy_id or None,
        "p_expected_policy_hash": expected_policy_hash or None,
        "p_new_policy_id": policy_record["policy_version_id"],
        "p_new_policy_hash": policy_record["policy_hash"],
        "p_policy_record": policy_record,
        "p_settings_data": settings_data,
    }
    try:
        response = get_service_client().rpc("upgrade_fund_policy", params).execute()
    except Exception as exc:
        raise PolicyUpgradeStoreUnavailable(
            "Published policy upgrade transaction failed"
        ) from exc
    data = getattr(response, "data", None)
    if isinstance(data, list) and len(data) == 1:
        data = data[0]
    if not isinstance(data, dict) or data.get("status") != "applied":
        raise PolicyUpgradeStoreUnavailable(
            "Published policy upgrade transaction returned an invalid result"
        )
    return data


def upgrade_published_policy(
    user_id: str,
    *,
    fund_config: Dict[str, Any],
    apply: bool,
) -> PublishedPolicyUpgradeReport:
    """Plan or atomically apply a strict republish from selected current config.

    Historical rows are only classified as complete/legacy/missing. They are
    never repaired or used as compilation input; the operator-selected current
    configuration is compiled exactly once into a new immutable version.
    """
    uid = require_user_id(user_id, context="upgrade_published_policy")
    if not isinstance(fund_config, dict):
        raise ValueError("fund_config must be an operator-selected object")
    settings, versions = _load_authoritative_state(uid)
    stored_config = (
        settings.get("fund_config")
        if isinstance(settings.get("fund_config"), dict)
        else {}
    )
    old_policy_id = str(stored_config.get("activePolicyVersionId") or "").strip()
    old_policy_hash = str(stored_config.get("publishedPolicyHash") or "").strip()
    old_state, complete_active = _existing_policy_state(
        versions,
        active_id=old_policy_id,
        published_hash=old_policy_hash,
    )

    compiled = compile_policy_from_fund_config(
        deepcopy(fund_config), require_publish_ready=True
    )
    new_policy_hash = str(compiled["policy_hash"])
    new_policy_id = f"policy_upgrade_{new_policy_hash}"
    mode = PolicyUpgradeMode.APPLY if apply else PolicyUpgradeMode.DRY_RUN
    if (
        complete_active is not None
        and old_policy_hash == new_policy_hash
    ):
        return PublishedPolicyUpgradeReport(
            user_id=uid,
            mode=mode,
            status=PolicyUpgradeStatus.ALREADY_CURRENT,
            old_policy_state=ExistingPolicyState.COMPLETE,
            old_policy_id=old_policy_id,
            old_policy_hash=old_policy_hash,
            new_policy_id=old_policy_id,
            new_policy_hash=new_policy_hash,
        )

    if not apply:
        return PublishedPolicyUpgradeReport(
            user_id=uid,
            mode=mode,
            status=PolicyUpgradeStatus.UPGRADE_REQUIRED,
            old_policy_state=old_state,
            old_policy_id=old_policy_id or None,
            old_policy_hash=old_policy_hash or None,
            new_policy_id=new_policy_id,
            new_policy_hash=new_policy_hash,
        )

    published_at = datetime.now(timezone.utc).isoformat()
    policy_record = validate_compiled_policy_bundle(
        {
            **compiled,
            "id": new_policy_id,
            "policy_version_id": new_policy_id,
            "published_at": published_at,
        }
    )
    next_settings = deepcopy(settings)
    next_fund_config = deepcopy(fund_config)
    next_fund_config["activePolicyVersionId"] = new_policy_id
    next_fund_config["publishedPolicyHash"] = new_policy_hash
    next_fund_config["draftPolicyHash"] = new_policy_hash
    next_fund_config["lastPublishedAt"] = published_at
    next_settings["fund_config"] = next_fund_config
    transaction = _apply_upgrade_transaction(
        user_id=uid,
        expected_policy_id=old_policy_id,
        expected_policy_hash=old_policy_hash,
        policy_record=policy_record,
        settings_data=next_settings,
    )
    return PublishedPolicyUpgradeReport(
        user_id=uid,
        mode=mode,
        status=PolicyUpgradeStatus.APPLIED,
        old_policy_state=old_state,
        old_policy_id=old_policy_id or None,
        old_policy_hash=old_policy_hash or None,
        new_policy_id=new_policy_id,
        new_policy_hash=new_policy_hash,
        appended=bool(transaction.get("appended", True)),
        pointer_switched=True,
    )
