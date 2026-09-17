"""Canonical policy upgrade plus an isolated historical CLI compatibility shim.

Normal runtime callers must use ``upgrade_published_policy_with_repository``.
The synchronous helpers below are retained only for the historical operator
CLI and its tests; they are not imported by API or pipeline execution.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict

from services.scoring.policy_compiler import (
    PolicyValidationError,
    compile_policy_from_fund_config,
    validate_compiled_policy_bundle,
)
from tenant_context import require_user_id


POLICY_TABLE = "fund_policy_versions"
SETTINGS_TABLE = "settings"


def doc_get_strict(table: str, key: str, *, user_id: str):
    from legacy_supabase.doc_store import doc_get_strict as _doc_get_strict

    return _doc_get_strict(table, key, user_id=user_id)


def list_get_all_strict(table: str, *, user_id: str):
    from legacy_supabase.doc_store import list_get_all_strict as _list_get_all_strict

    return _list_get_all_strict(table, user_id=user_id)


def get_service_client():
    from legacy_supabase.client import get_service_client as _get_service_client

    return _get_service_client()


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


async def upgrade_published_policy_with_repository(
    repository: Any,
    user_id: str,
    *,
    fund_config: Dict[str, Any],
    apply: bool,
    actor_id: Optional[str] = None,
) -> PublishedPolicyUpgradeReport:
    """Canonical asyncpg policy upgrade; retained separately from the legacy CLI adapter."""
    uid = require_user_id(user_id, context="upgrade_published_policy_with_repository")
    if not isinstance(fund_config, dict):
        raise ValueError("fund_config must be an operator-selected object")
    try:
        current = await repository.get_active_published_policy(user_id=uid)
    except LookupError:
        current = None
    old_id = str((current or {}).get("governed_policy_version_id") or "").strip()
    old_hash = str((current or {}).get("policy_hash") or "").strip()
    old_state = ExistingPolicyState.COMPLETE if current else ExistingPolicyState.MISSING
    compiled = compile_policy_from_fund_config(deepcopy(fund_config), require_publish_ready=True)
    new_hash = str(compiled["policy_hash"])
    if current is not None and old_hash == new_hash:
        return PublishedPolicyUpgradeReport(
            user_id=uid,
            mode=PolicyUpgradeMode.APPLY if apply else PolicyUpgradeMode.DRY_RUN,
            status=PolicyUpgradeStatus.ALREADY_CURRENT,
            old_policy_state=old_state,
            old_policy_id=old_id,
            old_policy_hash=old_hash,
            new_policy_id=old_id,
            new_policy_hash=new_hash,
        )
    new_id = str(uuid5(NAMESPACE_URL, f"aethria:governed-policy:{uid}:{new_hash}"))
    if not apply:
        return PublishedPolicyUpgradeReport(
            user_id=uid,
            mode=PolicyUpgradeMode.DRY_RUN,
            status=PolicyUpgradeStatus.UPGRADE_REQUIRED,
            old_policy_state=old_state,
            old_policy_id=old_id or None,
            old_policy_hash=old_hash or None,
            new_policy_id=new_id,
            new_policy_hash=new_hash,
        )
    published = await repository.publish_settings_policy(
        user_id=uid,
        actor_id=actor_id or uid,
        fund_config=fund_config,
        policy_hash=new_hash,
        expected_policy_id=old_id,
        expected_policy_hash=old_hash,
        governed_policy_version_id=new_id,
    )
    return PublishedPolicyUpgradeReport(
        user_id=uid,
        mode=PolicyUpgradeMode.APPLY,
        status=PolicyUpgradeStatus.APPLIED,
        old_policy_state=old_state,
        old_policy_id=old_id or None,
        old_policy_hash=old_hash or None,
        new_policy_id=str(published.get("governed_policy_version_id") or new_id),
        new_policy_hash=new_hash,
        appended=True,
        pointer_switched=True,
    )


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
    settings_patch: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        from services.scoring.legacy_policy_compat import apply_upgrade_transaction
        data = apply_upgrade_transaction(
            service_client_factory=get_service_client,
            user_id=user_id,
            expected_policy_id=expected_policy_id,
            expected_policy_hash=expected_policy_hash,
            policy_record=policy_record,
            settings_patch=settings_patch,
        )
    except Exception as exc:
        raise PolicyUpgradeStoreUnavailable(
            "Published policy upgrade transaction failed"
        ) from exc
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
    settings_patch = {
        "fund_config": {
            "activePolicyVersionId": new_policy_id,
            "publishedPolicyHash": new_policy_hash,
            "draftPolicyHash": new_policy_hash,
            "lastPublishedAt": published_at,
        }
    }
    transaction = _apply_upgrade_transaction(
        user_id=uid,
        expected_policy_id=old_policy_id,
        expected_policy_hash=old_policy_hash,
        policy_record=policy_record,
        settings_patch=settings_patch,
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
