"""Fail-closed tenant prerequisites shared by evaluation entry paths."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict

from core.policy_resolver import get_partner_rules
from evaluation_v2.models import EvaluationPolicy
from evaluation_v2.policy import evaluation_policy_from_compiled
from fund_thesis import (
    FundThesisError,
    FundThesisIncompleteError,
    FundThesisMissingError,
    get_active_thesis,
)
from services.scoring.policy_compiler import compile_policy_from_fund_config
from services.scoring.policy_store import PolicyNotPublishedError, load_published_policy
from supabase_client import get_service_client
from tenant_context import require_user_id


@dataclass(frozen=True)
class EvaluationPrerequisites:
    thesis_version_id: str
    policy: EvaluationPolicy


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
) -> EvaluationPrerequisites:
    """Resolve one tenant's exact thesis, published policy, and Partner rules."""
    uid = require_user_id(user_id, context="load_evaluation_prerequisites")

    async def resolve_thesis() -> Any:
        if load_thesis is not None:
            value = load_thesis(uid)
            return await value if inspect.isawaitable(value) else value
        return await asyncio.to_thread(
            lambda: get_active_thesis(get_service_client(), uid)
        )

    async def resolve_policy() -> Dict[str, Any]:
        if load_policy is not None:
            value = load_policy(uid)
            return await value if inspect.isawaitable(value) else value
        return await asyncio.to_thread(load_published_policy, uid)

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
    if fund_intelligence_repository is not None:
        try:
            governed = (
                await fund_intelligence_repository.get_active_published_policy(
                    user_id=uid
                )
            )
        except LookupError:
            governed = None
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
        if governed is not None:
            try:
                compiled = await asyncio.to_thread(
                    compile_policy_from_fund_config,
                    governed["policy_patch"],
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
        rules = await resolve_rules()
        policy = evaluation_policy_from_compiled(compiled, partner_rules=rules)
    except Exception as exc:
        raise EvaluationPrerequisiteError(
            code="prerequisite_unavailable",
            detail="The versioned evaluation policy could not be compiled.",
            recovery_action="Republish the scoring policy before retrying.",
        ) from exc

    return EvaluationPrerequisites(
        thesis_version_id=str(thesis.version_id),
        policy=policy,
    )
