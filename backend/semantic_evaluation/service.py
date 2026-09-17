"""Shadow-only semantic evaluation.

`evaluate()` is typed in, typed out, and never raises — every failure mode
(provider outage, timeout, in-process rate cap, disabled) becomes an explicit
`SemanticEvaluationStatus`, never an exception the caller must catch. This is
a deliberate departure from `investment_analysis.model_gateway.AnalysisBlocked`:
that gateway is on the *authoritative* path and correctly fails closed;
semantic evaluation is non-authoritative while SHADOW, so it fails open —
its own failure can never block or alter Scout/Reviewer/Partner.

`schedule_shadow_evaluation()` is what authoritative callers actually use: it
fires `evaluate()` as a background `asyncio.Task` and returns immediately, so
a slow or unavailable provider cannot add latency to the pipeline it shadows.
See `semantic_evaluation/README.md` for the SHADOW invariant this protects
and the test that proves it.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Optional
from uuid import uuid4

import env_config
import metrics
from pipeline_state import pipeline_stage_log
from tenant_context import require_user_id

from semantic_evaluation.definitions import definition_for
from semantic_evaluation.models import (
    SemanticEvaluationInput,
    SemanticEvaluationRecord,
    SemanticEvaluationResult,
    SemanticEvaluationRolloutMode,
    SemanticEvaluationStatus,
)
from semantic_evaluation.providers.base import SemanticEvaluationProvider
from semantic_evaluation.providers.mock import MockSemanticEvaluationProvider
from semantic_evaluation.repository import SemanticEvaluationRepository

logger = logging.getLogger("semantic_evaluation")

_PHASE_BY_STATUS = {
    SemanticEvaluationStatus.SUCCESS: "DONE",
    SemanticEvaluationStatus.TIMEOUT: "FAILED",
    SemanticEvaluationStatus.PROVIDER_ERROR: "FAILED",
    SemanticEvaluationStatus.BUDGET_SKIPPED: "SKIPPED",
    SemanticEvaluationStatus.DISABLED: "SKIPPED",
}

# In-process rate cap, deliberately not a dollar budget — see
# SEMANTIC_EVALUATION_MAX_CALLS_PER_MINUTE in env_config.py. Process-local by
# design: a multi-worker deployment gets one cap per worker, which is fine
# for a safety valve that only needs to prevent a runaway loop, not enforce
# an exact global rate.
_window_start_monotonic = 0.0
_window_call_count = 0


def _rate_limited() -> bool:
    global _window_start_monotonic, _window_call_count
    now = time.monotonic()
    if now - _window_start_monotonic >= 60.0:
        _window_start_monotonic = now
        _window_call_count = 0
    _window_call_count += 1
    return _window_call_count > max(0, env_config.get_int("SEMANTIC_EVALUATION_MAX_CALLS_PER_MINUTE"))


def reset_rate_limit_window() -> None:
    """Test-only reset of the in-process rate-cap window (mirrors
    `research.search_providers.reset_providers`'s test-isolation role)."""
    global _window_start_monotonic, _window_call_count
    _window_start_monotonic = 0.0
    _window_call_count = 0


def _resolve_provider(name: str) -> Optional[SemanticEvaluationProvider]:
    if name == "mock":
        return MockSemanticEvaluationProvider()
    return None  # 'jev' intentionally not implemented yet.


def _rollout_mode() -> SemanticEvaluationRolloutMode:
    raw = (env_config.get_str("SEMANTIC_EVALUATION_ROLLOUT_MODE") or "shadow").strip().lower()
    try:
        return SemanticEvaluationRolloutMode(raw)
    except ValueError:
        logger.warning("Unknown SEMANTIC_EVALUATION_ROLLOUT_MODE=%r; defaulting to shadow", raw)
        return SemanticEvaluationRolloutMode.SHADOW


def _input_digest(evaluation_input: SemanticEvaluationInput) -> str:
    payload = {
        "state": evaluation_input.state,
        "questions": [q.model_dump(mode="json") for q in evaluation_input.questions],
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _log(evaluation_input: SemanticEvaluationInput, result: SemanticEvaluationResult, user_id: str) -> None:
    metrics.inc_semantic_evaluation(
        evaluation_type=evaluation_input.evaluation_type.value,
        provider=result.provider or "none",
        status=result.status.value,
    )
    pipeline_stage_log(
        evaluation_input.pipeline_run_id,
        startup_id=evaluation_input.startup_id or "",
        user_id=user_id,
        stage=f"semantic_evaluation:{evaluation_input.evaluation_type.value}",
        phase=_PHASE_BY_STATUS[result.status],
    )


async def _persist(
    *, evaluation_input: SemanticEvaluationInput, result: SemanticEvaluationResult,
    user_id: str, rollout_mode: SemanticEvaluationRolloutMode, provider_name: str,
    repository: Optional[SemanticEvaluationRepository],
) -> None:
    if repository is None:
        return
    try:
        definition = definition_for(evaluation_input.evaluation_type)
        record = SemanticEvaluationRecord(
            evaluation_id=str(uuid4()),
            user_id=user_id,
            pipeline_run_id=evaluation_input.pipeline_run_id,
            workflow_run_id=evaluation_input.workflow_run_id,
            startup_id=evaluation_input.startup_id,
            opportunity_id=evaluation_input.opportunity_id,
            evaluation_type=evaluation_input.evaluation_type,
            evaluation_version=definition.evaluation_version,
            criteria_version=definition.criteria_version,
            rollout_mode=rollout_mode,
            provider=provider_name,
            model=result.model,
            provider_model_version=result.provider_model_version,
            status=result.status,
            input_digest=_input_digest(evaluation_input),
            claim_ids=list(evaluation_input.claim_ids),
            source_ids=list(evaluation_input.source_ids),
            selected_answer=result.selected_answer,
            confidence=result.confidence,
            distribution=list(result.distribution),
            latency_ms=result.latency_ms,
            tokens=result.tokens,
            estimated_cost_usd=result.estimated_cost_usd,
            error=result.error,
        )
        await repository.record(record)
    except Exception as exc:  # noqa: BLE001 - persistence must never affect the caller
        logger.warning("semantic_evaluation persistence failed: %s", exc)


async def evaluate(
    evaluation_input: SemanticEvaluationInput,
    *,
    user_id: str,
    repository: Optional[SemanticEvaluationRepository] = None,
    provider: Optional[SemanticEvaluationProvider] = None,
) -> SemanticEvaluationResult:
    """Typed in, typed out, never raises. See module docstring for why this
    fails open rather than reusing `AnalysisBlocked` semantics."""
    uid = require_user_id(user_id, context="semantic_evaluation.evaluate")
    rollout_mode = _rollout_mode()

    if not env_config.get_bool("SEMANTIC_EVALUATION_ENABLED"):
        result = SemanticEvaluationResult(status=SemanticEvaluationStatus.DISABLED)
        _log(evaluation_input, result, uid)
        return result

    provider_name = env_config.get_str("SEMANTIC_EVALUATION_PROVIDER") or "mock"
    active_provider = provider or _resolve_provider(provider_name)
    if active_provider is None:
        result = SemanticEvaluationResult(
            status=SemanticEvaluationStatus.PROVIDER_ERROR,
            error=f"Unknown or unimplemented provider: {provider_name!r}",
        )
        await _persist(evaluation_input=evaluation_input, result=result, user_id=uid,
                       rollout_mode=rollout_mode, provider_name=provider_name, repository=repository)
        _log(evaluation_input, result, uid)
        return result

    if _rate_limited():
        result = SemanticEvaluationResult(status=SemanticEvaluationStatus.BUDGET_SKIPPED, provider=active_provider.name)
        await _persist(evaluation_input=evaluation_input, result=result, user_id=uid,
                       rollout_mode=rollout_mode, provider_name=active_provider.name, repository=repository)
        _log(evaluation_input, result, uid)
        return result

    timeout_seconds = env_config.get_float("SEMANTIC_EVALUATION_TIMEOUT_SECONDS") or 5.0
    started = time.monotonic()
    try:
        result = await asyncio.wait_for(active_provider.evaluate(evaluation_input), timeout=timeout_seconds)
        if result.latency_ms is None:
            result = result.model_copy(update={"latency_ms": (time.monotonic() - started) * 1000})
    except asyncio.TimeoutError:
        result = SemanticEvaluationResult(
            status=SemanticEvaluationStatus.TIMEOUT, provider=active_provider.name,
            latency_ms=(time.monotonic() - started) * 1000,
        )
    except Exception as exc:  # noqa: BLE001 - a provider failure must never propagate
        logger.warning("semantic_evaluation provider %s failed: %s", active_provider.name, exc)
        result = SemanticEvaluationResult(
            status=SemanticEvaluationStatus.PROVIDER_ERROR, provider=active_provider.name,
            error=str(exc)[:500], latency_ms=(time.monotonic() - started) * 1000,
        )

    await _persist(evaluation_input=evaluation_input, result=result, user_id=uid,
                   rollout_mode=rollout_mode, provider_name=active_provider.name, repository=repository)
    _log(evaluation_input, result, uid)
    return result


# Strong references to in-flight shadow tasks. asyncio only weakly tracks a
# task once nothing else holds a reference to it, and can garbage-collect it
# mid-execution — the standard fix (per the asyncio.create_task docs) is a
# module-level set the task removes itself from on completion. Without this,
# a fire-and-forget shadow evaluation could silently vanish before finishing.
_background_tasks: set[asyncio.Task] = set()


def schedule_shadow_evaluation(
    evaluation_input: SemanticEvaluationInput,
    *,
    user_id: str,
    repository: Optional[SemanticEvaluationRepository] = None,
    provider: Optional[SemanticEvaluationProvider] = None,
) -> "asyncio.Task[SemanticEvaluationResult]":
    """What authoritative callers (Scout, investment_analysis) actually call.

    Returns the underlying `asyncio.Task` purely so a test can `await` it and
    make persistence deterministic. Production callers must never await the
    returned task or read its result to influence behaviour — doing so would
    reintroduce exactly the latency and authority coupling this design
    exists to prevent. There is no return-value use for authoritative code;
    if a caller finds itself wanting one, that is a promotion decision (see
    README.md), not something to slip in here.
    """

    async def _run() -> SemanticEvaluationResult:
        try:
            return await evaluate(evaluation_input, user_id=user_id, repository=repository, provider=provider)
        except Exception as exc:  # noqa: BLE001 - belt-and-suspenders; evaluate() must not raise
            logger.warning("semantic_evaluation shadow dispatch failed unexpectedly: %s", exc)
            return SemanticEvaluationResult(status=SemanticEvaluationStatus.PROVIDER_ERROR, error=str(exc)[:500])

    task = asyncio.create_task(_run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def wait_for_pending_shadow_evaluations() -> None:
    """Test-only: await every currently in-flight shadow evaluation task.

    Production code must never call this — it exists so a test can make a
    fire-and-forget dispatch deterministic (e.g. asserting on what got
    persisted) without the caller under test needing to expose its own
    internal task handle.
    """
    pending = list(_background_tasks)
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
