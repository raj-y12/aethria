"""Fail-closed validation and consensus for governed Reviewer scoring traces."""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Dict, Iterable, Mapping, Sequence

from evaluation_v2.prerequisites import EvaluationPrerequisites


class GovernedScoringError(RuntimeError):
    """A governed stage cannot prove that scores came from its certified policy."""


# Top-level fields emitted by DeterministicScoringEngine, plus the fields added by
# the governed consensus layer. Keeping this schema closed makes a newly introduced
# score-like dimension fail until it is present in the compiled policy as well.
_TRACE_METADATA_FIELDS = frozenset(
    {
        "overall_score",
        "overall_confidence",
        "overall_dispersion",
        "raw_signals",
        "policy_version_id",
        "policy_hash",
        "stage_cohort",
        "stage_cohort_label",
        "sector_tam_benchmark",
        "calibration",
        "scoring_runtime_version",
        "scoring_runtime_hash",
        "trace_kind",
        "resolution_strategy",
        "persona_count",
        "input_traces",
    }
)

_CONSERVATIVE_MIN_WEIGHT = 0.45
_MATERIAL_SPREAD = 2.0


def configured_scoring_dimensions(
    prerequisites: EvaluationPrerequisites,
) -> tuple[str, ...]:
    policy = prerequisites.compiled_scoring_policy
    raw_dimensions = policy.get("dimensions")
    if not isinstance(raw_dimensions, Mapping) or not raw_dimensions:
        raise GovernedScoringError(
            "governed compiled scoring policy has no configured dimensions"
        )
    dimensions: list[str] = []
    for raw_name, definition in raw_dimensions.items():
        name = str(raw_name or "").strip()
        if not name or not isinstance(definition, Mapping):
            raise GovernedScoringError(
                "governed compiled scoring policy has malformed dimensions"
            )
        if name in _TRACE_METADATA_FIELDS:
            raise GovernedScoringError(
                f"governed compiled scoring policy uses reserved dimension {name}"
            )
        dimensions.append(name)
    return tuple(dimensions)


def _finite_number(value: Any, *, minimum: float, maximum: float) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and minimum <= float(value) <= maximum
    )


def _validate_dimension_detail(dimension: str, detail: Any) -> None:
    if not isinstance(detail, Mapping):
        raise GovernedScoringError(
            f"governed structured scoring trace is incomplete for {dimension}"
        )
    if not isinstance(detail.get("unscored"), bool):
        raise GovernedScoringError(
            f"governed structured scoring trace has invalid missingness for {dimension}"
        )
    if not isinstance(detail.get("components"), Mapping):
        raise GovernedScoringError(
            f"governed structured scoring trace has invalid components for {dimension}"
        )
    if not _finite_number(detail.get("confidence"), minimum=0.0, maximum=1.0):
        raise GovernedScoringError(
            f"governed structured scoring trace has invalid confidence for {dimension}"
        )

    unscored = detail["unscored"]
    score = detail.get("score")
    reasons = detail.get("missing_reasons")
    if unscored:
        if score is not None:
            raise GovernedScoringError(
                f"governed structured scoring trace has a numeric default for unscored {dimension}"
            )
        if (
            not isinstance(reasons, list)
            or not reasons
            or any(not isinstance(reason, str) or not reason.strip() for reason in reasons)
            or len(set(reasons)) != len(reasons)
        ):
            raise GovernedScoringError(
                f"governed structured scoring trace lacks stable missing reasons for {dimension}"
            )
        return

    if not _finite_number(score, minimum=0.0, maximum=10.0):
        raise GovernedScoringError(
            f"governed structured scoring trace has an invalid {dimension} score"
        )
    if reasons not in (None, []):
        raise GovernedScoringError(
            f"governed structured scoring trace contradicts scored {dimension}"
        )


def validate_governed_scoring_trace(
    trace: Any,
    prerequisites: EvaluationPrerequisites,
    *,
    require_resolved: bool = False,
) -> Mapping[str, Any]:
    """Validate exact policy identity and one record per configured dimension.

    Persona traces and the resolved trace use the same dimension contract. Partner
    additionally sets ``require_resolved`` so a stale persona trace cannot cross the
    decision boundary even when its policy identifiers happen to match.
    """

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
    runtime = policy.get("scoring_runtime")
    expected_runtime_version = (
        str(runtime.get("semantic_version") or "")
        if isinstance(runtime, Mapping)
        else ""
    )
    expected_runtime_hash = str(policy.get("scoring_runtime_hash") or "")
    if not expected_runtime_version or not expected_runtime_hash:
        raise GovernedScoringError(
            "governed compiled policy has no certified scoring runtime"
        )
    if (
        str(trace.get("scoring_runtime_version") or "")
        != expected_runtime_version
    ):
        raise GovernedScoringError(
            "governed structured scoring trace runtime version does not match prerequisites"
        )
    if str(trace.get("scoring_runtime_hash") or "") != expected_runtime_hash:
        raise GovernedScoringError(
            "governed structured scoring trace runtime hash does not match prerequisites"
        )

    dimensions = configured_scoring_dimensions(prerequisites)
    unknown = sorted(set(trace) - set(dimensions) - _TRACE_METADATA_FIELDS)
    if unknown:
        raise GovernedScoringError(
            "governed structured scoring trace contains unknown scoring dimensions: "
            + ", ".join(unknown)
        )
    for dimension in dimensions:
        _validate_dimension_detail(dimension, trace.get(dimension))

    any_unscored = any(bool(trace[dimension]["unscored"]) for dimension in dimensions)
    overall_score = trace.get("overall_score")
    if any_unscored:
        if require_resolved and overall_score is not None:
            raise GovernedScoringError(
                "governed structured scoring trace publishes a partial overall score"
            )
        if overall_score is not None and not _finite_number(
            overall_score, minimum=0.0, maximum=10.0
        ):
            raise GovernedScoringError(
                "governed structured scoring trace has an invalid overall score"
            )
    elif not _finite_number(overall_score, minimum=0.0, maximum=10.0):
        raise GovernedScoringError(
            "governed structured scoring trace has an invalid overall score"
        )
    if not _finite_number(
        trace.get("overall_confidence"), minimum=0.0, maximum=1.0
    ):
        raise GovernedScoringError(
            "governed structured scoring trace has invalid overall confidence"
        )

    if require_resolved:
        if trace.get("trace_kind") != "resolved_consensus":
            raise GovernedScoringError(
                "governed Partner requires a resolved consensus scoring trace"
            )
        inputs = trace.get("input_traces")
        if not isinstance(inputs, list) or not inputs:
            raise GovernedScoringError(
                "governed resolved consensus trace has no input traces"
            )
        if trace.get("persona_count") != len(inputs):
            raise GovernedScoringError(
                "governed resolved consensus trace has inconsistent persona count"
            )
        for item in inputs:
            if (
                not isinstance(item, Mapping)
                or not isinstance(item.get("reviewer_type"), str)
                or not item["reviewer_type"].strip()
            ):
                raise GovernedScoringError(
                    "governed resolved consensus trace has malformed input provenance"
                )
            validate_governed_scoring_trace(
                item.get("trace"), prerequisites, require_resolved=False
            )
    return trace


def _resolved_number(values: Sequence[float]) -> tuple[float, str, float]:
    if not values:
        raise GovernedScoringError("governed consensus has no numeric inputs")
    mean_value = sum(values) / len(values)
    spread = max(values) - min(values)
    if len(values) >= 2 and spread >= _MATERIAL_SPREAD:
        resolved = (
            (1.0 - _CONSERVATIVE_MIN_WEIGHT) * mean_value
            + _CONSERVATIVE_MIN_WEIGHT * min(values)
        )
        strategy = "conservative_mean_floor"
    else:
        resolved = mean_value
        strategy = "mean"
    # Trace values cross a JSON/storage boundary. Bound decimal precision here so
    # identities such as 5.99 do not drift to 5.989999999999999 in projections.
    return round(max(0.0, min(10.0, resolved)), 6), strategy, round(spread, 6)


def resolve_governed_scoring_traces(
    persona_results: Iterable[Mapping[str, Any]],
    prerequisites: EvaluationPrerequisites,
) -> Dict[str, Any]:
    """Build the sole authoritative post-persona scoring artifact.

    Missingness is conservative: if any successful persona cannot score a configured
    dimension, the consensus cannot score it either. Every raw trace is embedded with
    persona provenance so persistence and Partner can revalidate the exact inputs.
    """

    results = list(persona_results)
    if not results:
        raise GovernedScoringError("governed consensus has no persona results")

    validated_inputs: list[tuple[str, Mapping[str, Any]]] = []
    for index, result in enumerate(results):
        reviewer_type = str(result.get("reviewer_type") or f"reviewer-{index + 1}")
        trace = validate_governed_scoring_trace(
            result.get("structured_scoring"), prerequisites
        )
        validated_inputs.append((reviewer_type, trace))

    first_trace = validated_inputs[0][1]
    dimensions = configured_scoring_dimensions(prerequisites)
    resolved: Dict[str, Any] = {
        key: deepcopy(first_trace[key])
        for key in (
            "raw_signals",
            "stage_cohort",
            "stage_cohort_label",
            "sector_tam_benchmark",
            "calibration",
            "scoring_runtime_version",
            "scoring_runtime_hash",
        )
        if key in first_trace
    }
    resolved.update(
        {
            "policy_version_id": first_trace["policy_version_id"],
            "policy_hash": first_trace["policy_hash"],
            "trace_kind": "resolved_consensus",
            "resolution_strategy": {
                "version": "reviewer-consensus-v1",
                "material_spread": _MATERIAL_SPREAD,
                "conservative_min_weight": _CONSERVATIVE_MIN_WEIGHT,
                "missingness": "union",
            },
            "persona_count": len(validated_inputs),
            "input_traces": [
                {"reviewer_type": reviewer_type, "trace": deepcopy(trace)}
                for reviewer_type, trace in validated_inputs
            ],
        }
    )

    any_unscored = False
    confidences: list[float] = []
    for dimension in dimensions:
        details = [trace[dimension] for _, trace in validated_inputs]
        confidences.extend(float(detail["confidence"]) for detail in details)
        if any(bool(detail["unscored"]) for detail in details):
            any_unscored = True
            resolved[dimension] = {
                "score": None,
                "confidence": min(float(detail["confidence"]) for detail in details),
                "components": {
                    "persona_resolution": {
                        "strategy": "missingness_union",
                        "reviewers": [name for name, _ in validated_inputs],
                    }
                },
                "unscored": True,
                "missing_reasons": [f"persona_unscored:{dimension}"],
            }
            continue

        values = [float(detail["score"]) for detail in details]
        score, strategy, spread = _resolved_number(values)
        resolved[dimension] = {
            "score": score,
            "confidence": min(float(detail["confidence"]) for detail in details),
            "components": {
                "persona_resolution": {
                    "strategy": strategy,
                    "scores": values,
                    "spread": spread,
                }
            },
            "unscored": False,
        }

    if any_unscored:
        resolved["overall_score"] = None
    else:
        overall_inputs = [float(trace["overall_score"]) for _, trace in validated_inputs]
        resolved["overall_score"] = _resolved_number(overall_inputs)[0]
    resolved["overall_confidence"] = min(confidences) if confidences else 0.0
    resolved["overall_dispersion"] = None

    validate_governed_scoring_trace(resolved, prerequisites, require_resolved=True)
    return resolved
