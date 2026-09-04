"""Fail-closed tenant prerequisites shared by evaluation entry paths."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict

import env_config

from core.policy_resolver import get_evaluation_rubric, get_partner_rules
from evaluation_v2.models import EvaluationPolicy
from evaluation_v2.partner_rules import PartnerRules, parse_partner_rules
from models import EvaluationDependencyIdentity
from evaluation_v2.policy import evaluation_policy_from_compiled
from fund_thesis import (
    FundThesisError,
    FundThesisIncompleteError,
    FundThesisMissingError,
    get_active_thesis,
    get_active_thesis_from_repository,
)
from services.scoring.policy_compiler import (
    PolicyValidationError,
    compile_policy_from_fund_config,
    validate_compiled_policy_bundle,
)
from services.scoring.policy_store import PolicyNotPublishedError, load_published_policy
from tenant_context import require_user_id
from settings_repository import SettingsRepository
from utils.settings_loader import load_settings


_GOVERNED_POLICY_NOT_FOUND = object()


def get_service_client():
    """Legacy dev/test seam; production thesis resolution uses PostgreSQL."""
    from supabase_client import get_service_client as _get_service_client

    return _get_service_client()


@dataclass(frozen=True)
class EvaluationPrerequisites:
    user_id: str
    thesis_context: Dict[str, Any]
    thesis_version_id: str
    compiled_scoring_policy: Dict[str, Any]
    partner_rules: PartnerRules
    fund_config: Dict[str, Any]
    policy: EvaluationPolicy
    _dependency_identity_payload: Dict[str, str] = field(
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        # Direct construction is used by engine tests and adapters. Preserve the
        # same parse-once invariant as the production loader at that boundary.
        object.__setattr__(
            self,
            "partner_rules",
            parse_partner_rules(self.partner_rules),
        )
        # Every mutable document is copied at the prerequisite boundary. Engines
        # receive further copies, so later cache/settings/test mutations cannot
        # rewrite the dependencies already certified for this run.
        object.__setattr__(self, "thesis_context", copy.deepcopy(self.thesis_context))
        object.__setattr__(
            self,
            "compiled_scoring_policy",
            copy.deepcopy(self.compiled_scoring_policy),
        )
        object.__setattr__(self, "fund_config", copy.deepcopy(self.fund_config))

        runtime = self.compiled_scoring_policy.get("scoring_runtime")
        runtime = runtime if isinstance(runtime, dict) else {}
        thesis_context = self.thesis_context
        thesis_context = thesis_context if isinstance(thesis_context, dict) else {}
        canonical_thesis = json.dumps(
            thesis_context,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        policy_version_id = str(
            getattr(self.policy, "policy_version_id", "") or ""
        ).strip()
        payload = {
            "user_id": str(self.user_id or "").strip(),
            "thesis_id": str(
                thesis_context.get("thesis_id")
                or thesis_context.get("version_id")
                or self.thesis_version_id
                or ""
            ).strip(),
            "thesis_version_id": str(self.thesis_version_id or "").strip(),
            "thesis_hash": hashlib.sha256(
                canonical_thesis.encode("utf-8")
            ).hexdigest(),
            "policy_id": str(
                self.compiled_scoring_policy.get("id") or policy_version_id
            ).strip(),
            "policy_version_id": policy_version_id,
            "policy_hash": str(
                getattr(self.policy, "policy_hash", "") or ""
            ).strip(),
            "rubric_version": str(
                getattr(self.policy, "rubric_version", "") or ""
            ).strip(),
            "partner_rules_id": "partner-rules",
            "partner_rules_version": str(
                getattr(self.policy, "partner_rules_version", "") or ""
            ).strip(),
            "partner_rules_hash": str(
                getattr(self.policy, "partner_rules_hash", "") or ""
            ).strip(),
            "scoring_runtime_version": str(
                runtime.get("semantic_version") or ""
            ).strip(),
            "scoring_runtime_hash": str(
                self.compiled_scoring_policy.get("scoring_runtime_hash") or ""
            ).strip(),
        }
        object.__setattr__(self, "_dependency_identity_payload", payload)

    @property
    def dependency_identity(self) -> Dict[str, str]:
        try:
            identity = EvaluationDependencyIdentity.model_validate(
                dict(self._dependency_identity_payload)
            )
        except Exception as exc:
            raise RuntimeError(
                "Evaluation prerequisites have incomplete dependency identity"
            ) from exc
        return identity.model_dump(mode="python")

    def require_tenant(self, user_id: str, *, context: str) -> str:
        uid = require_user_id(user_id, context=context)
        if uid != self.user_id:
            raise RuntimeError(
                f"{context}: evaluation prerequisite tenant mismatch "
                f"({uid!r} != {self.user_id!r})"
            )
        return uid


class EvaluationPrerequisiteError(RuntimeError):
    def __init__(self, *, code: str, detail: str, recovery_action: str):
        self.code = code
        self.detail = detail
        self.recovery_action = recovery_action
        super().__init__(f"{code}: {detail}")


async def load_evaluation_prerequisites(
    *,
    user_id: str,
    fund_intelligence_repository: Any | None,
    load_thesis: Callable[[str], Any] | None = None,
    load_policy: Callable[[str], Dict[str, Any]] | None = None,
    load_partner_rules: Callable[[], Dict[str, Any]] | None = None,
    load_fund_config: Callable[[str], Dict[str, Any]] | None = None,
    settings_repository: SettingsRepository | None = None,
) -> EvaluationPrerequisites:
    """Resolve one tenant's exact thesis, published policy, and Partner rules."""
    uid = require_user_id(user_id, context="load_evaluation_prerequisites")
    resolved_legacy_settings: Dict[str, Any] | None = None

    async def resolve_thesis() -> Any:
        if load_thesis is not None:
            value = load_thesis(uid)
            return await value if inspect.isawaitable(value) else value
        pool = getattr(fund_intelligence_repository, "pool", None)
        if pool is not None:
            return await get_active_thesis_from_repository(
                fund_intelligence_repository.thesis_repository,
                uid,
            )
        if env_config.is_production_env():
            raise EvaluationPrerequisiteError(
                code="institutional_thesis_repository_required",
                detail="Production evaluation requires the shared PostgreSQL thesis repository.",
                recovery_action="Configure the durable PostgreSQL pool and retry.",
            )
        from fund_thesis import get_active_thesis
        return await asyncio.to_thread(lambda: get_active_thesis(get_service_client(), uid))

    async def resolve_policy() -> Dict[str, Any]:
        nonlocal resolved_legacy_settings
        if load_policy is not None:
            value = load_policy(uid)
            return await value if inspect.isawaitable(value) else value
        repository_pool = getattr(fund_intelligence_repository, "pool", None)
        if repository_pool is None and env_config.is_production_env():
            raise EvaluationPrerequisiteError(
                code="governed_policy_repository_required",
                detail="Production evaluation requires the canonical governed policy repository.",
                recovery_action="Configure the shared PostgreSQL pool and retry.",
            )
        if repository_pool is not None:
            try:
                governed = await fund_intelligence_repository.get_active_published_policy(
                    user_id=uid
                )
            except LookupError as exc:
                raise EvaluationPrerequisiteError(
                    code="published_policy_required",
                    detail="No active governed policy is published for this tenant.",
                    recovery_action="Publish a governed policy before evaluation.",
                ) from exc
            except Exception as exc:
                raise EvaluationPrerequisiteError(
                    code="prerequisite_unavailable",
                    detail="The governed policy could not be loaded.",
                    recovery_action="Retry after the policy store is available.",
                ) from exc
            if not isinstance(governed, dict):
                raise EvaluationPrerequisiteError(
                    code="prerequisite_unavailable",
                    detail="The governed policy store returned an invalid response.",
                    recovery_action="Retry after the policy store is available.",
                )
            patch = governed.get("policy_patch")
            if not isinstance(patch, dict):
                raise EvaluationPrerequisiteError(
                    code="prerequisite_unavailable",
                    detail="The governed policy payload is invalid.",
                    recovery_action="Republish the governed policy before retrying.",
                )
            compiled = await asyncio.to_thread(
                compile_policy_from_fund_config,
                patch,
                require_publish_ready=True,
            )
            if compiled.get("policy_hash") != governed.get("policy_hash"):
                raise EvaluationPrerequisiteError(
                    code="prerequisite_unavailable",
                    detail="The governed policy hash is inconsistent.",
                    recovery_action="Republish the governed policy before retrying.",
                )
            compiled["policy_version_id"] = governed.get("governed_policy_version_id")
            return compiled
        try:
            resolved_legacy_settings = await load_settings(
                uid, repository=settings_repository, use_cache=False
            )
        except TypeError:
            resolved_legacy_settings = load_settings(uid, use_cache=False)
            if inspect.isawaitable(resolved_legacy_settings):
                resolved_legacy_settings = await resolved_legacy_settings
        return await asyncio.to_thread(
            lambda: load_published_policy(uid, settings=resolved_legacy_settings)
        )

    async def resolve_rules() -> Dict[str, Any]:
        if load_partner_rules is not None:
            value = load_partner_rules()
            return await value if inspect.isawaitable(value) else value
        return await asyncio.to_thread(get_partner_rules)

    try:
        thesis = await resolve_thesis()
    except FundThesisMissingError as exc:
        raise EvaluationPrerequisiteError(
            code="thesis_required",
            detail="An active fund thesis is required before evaluation.",
            recovery_action="Create and publish the fund thesis in Settings.",
        ) from exc
    except FundThesisIncompleteError as exc:
        raise EvaluationPrerequisiteError(
            code="thesis_required",
            detail="The active fund thesis is incomplete.",
            recovery_action="Complete and publish the fund thesis in Settings.",
        ) from exc
    except FundThesisError as exc:
        raise EvaluationPrerequisiteError(
            code="prerequisite_unavailable",
            detail="The active fund thesis could not be loaded.",
            recovery_action="Retry after the thesis store is available.",
        ) from exc
    except Exception as exc:
        raise EvaluationPrerequisiteError(
            code="prerequisite_unavailable",
            detail="The active fund thesis could not be loaded.",
            recovery_action="Retry after the thesis store is available.",
        ) from exc
    if thesis is None:
        raise EvaluationPrerequisiteError(
            code="thesis_required",
            detail="An active fund thesis is required before evaluation.",
            recovery_action="Create and publish the fund thesis in Settings.",
        )

    compiled: Dict[str, Any] | None = None
    exact_fund_config: Dict[str, Any] | None = None
    if fund_intelligence_repository is not None:
        governed: Any = _GOVERNED_POLICY_NOT_FOUND
        try:
            governed = (
                await fund_intelligence_repository.get_active_published_policy(
                    user_id=uid
                )
            )
        except LookupError:
            pass
        except Exception as exc:
            raise EvaluationPrerequisiteError(
                code="prerequisite_unavailable",
                detail="The governed policy could not be loaded.",
                recovery_action="Retry after the policy store is available.",
            ) from exc
        if governed is None:
            raise EvaluationPrerequisiteError(
                code="prerequisite_unavailable",
                detail="The governed policy store returned an invalid response.",
                recovery_action="Retry after the policy store is available.",
            )
        if governed is not _GOVERNED_POLICY_NOT_FOUND:
            try:
                governed_patch = governed["policy_patch"]
                if not isinstance(governed_patch, dict):
                    raise ValueError("governed policy patch must be an object")
                exact_fund_config = governed_patch
                compiled = await asyncio.to_thread(
                    compile_policy_from_fund_config,
                    exact_fund_config,
                    require_publish_ready=True,
                )
                if compiled["policy_hash"] != governed["policy_hash"]:
                    raise EvaluationPrerequisiteError(
                        code="prerequisite_unavailable",
                        detail="The governed policy hash is inconsistent.",
                        recovery_action=(
                            "Republish the governed policy before retrying."
                        ),
                    )
                compiled["policy_version_id"] = governed[
                    "governed_policy_version_id"
                ]
            except EvaluationPrerequisiteError:
                raise
            except Exception as exc:
                raise EvaluationPrerequisiteError(
                    code="prerequisite_unavailable",
                    detail="The governed policy could not be compiled.",
                    recovery_action=(
                        "Republish the governed policy before retrying."
                    ),
                ) from exc

    if compiled is None:
        try:
            compiled = await resolve_policy()
        except PolicyNotPublishedError as exc:
            raise EvaluationPrerequisiteError(
                code="published_policy_required",
                detail=(
                    "An active published scoring policy is required before "
                    "evaluation."
                ),
                recovery_action="Publish the fund scoring policy in Settings.",
            ) from exc
        except Exception as exc:
            raise EvaluationPrerequisiteError(
                code="prerequisite_unavailable",
                detail="The published policy could not be loaded.",
                recovery_action="Retry after the policy store is available.",
            ) from exc

    try:
        compiled = validate_compiled_policy_bundle(compiled)
    except PolicyValidationError as exc:
        raise EvaluationPrerequisiteError(
            code="prerequisite_unavailable",
            detail="The published policy decision bundle is incomplete or hash-invalid.",
            recovery_action="Republish the fund scoring policy before retrying.",
        ) from exc
    # The published normalized decision bundle is the only fund configuration a
    # governed engine may consume. Current settings are a mutable draft and are
    # intentionally ignored after the published policy has been resolved.
    exact_fund_config = compiled["decision_inputs"]

    try:
        rules = parse_partner_rules(await resolve_rules())
        policy = evaluation_policy_from_compiled(
            compiled,
            partner_rules=rules,
            rubric=get_evaluation_rubric(),
        )
    except Exception as exc:
        raise EvaluationPrerequisiteError(
            code="prerequisite_unavailable",
            detail="The versioned evaluation policy could not be compiled.",
            recovery_action="Republish the scoring policy before retrying.",
        ) from exc

    return EvaluationPrerequisites(
        user_id=uid,
        thesis_context=(
            thesis.as_engine_context()
            if callable(getattr(thesis, "as_engine_context", None))
            else {"version_id": str(thesis.version_id)}
        ),
        thesis_version_id=str(thesis.version_id),
        compiled_scoring_policy=compiled,
        partner_rules=rules,
        fund_config=exact_fund_config,
        policy=policy,
    )
