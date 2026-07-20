"""Fail-closed validation for governed Reviewer → Partner scoring traces."""

from __future__ import annotations

import math
from typing import Any, Mapping

from evaluation_v2.prerequisites import EvaluationPrerequisites


REQUIRED_SCORE_DIMENSIONS = ("market", "product", "technical", "execution")


class GovernedScoringError(RuntimeError):
    """A governed stage cannot prove that scores came from its certified policy."""


def validate_governed_scoring_trace(
    trace: Any,
    prerequisites: EvaluationPrerequisites,
) -> Mapping[str, Any]:
    if not isinstance(trace, Mapping) or not trace:
        raise GovernedScoringError(
            "governed structured scoring trace is absent or malformed"
        )
    policy = prerequisites.compiled_scoring_policy
    expected_version = str(policy.get("policy_version_id") or "")
    expected_hash = str(policy.get("policy_hash") or "")
    if str(trace.get("policy_version_id") or "") != expected_version:
        raise GovernedScoringError(
            "governed structured scoring trace policy version does not match prerequisites"
        )
    if str(trace.get("policy_hash") or "") != expected_hash:
        raise GovernedScoringError(
            "governed structured scoring trace policy hash does not match prerequisites"
        )
    for dimension in REQUIRED_SCORE_DIMENSIONS:
        detail = trace.get(dimension)
        if not isinstance(detail, Mapping) or detail.get("unscored") is not False:
            raise GovernedScoringError(
                f"governed structured scoring trace is incomplete for {dimension}"
            )
        score = detail.get("score")
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(float(score))
            or not 0 <= float(score) <= 10
        ):
            raise GovernedScoringError(
                f"governed structured scoring trace has an invalid {dimension} score"
            )
    return trace
