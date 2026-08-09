"""Conservative, deterministic hypotheses grounded only in Fund Intelligence observations."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


_SUFFICIENCY_RANK = {"insufficient": 0, "emerging": 1, "moderate": 2, "strong": 3}
_MIN_HYPOTHESIS_RANK = _SUFFICIENCY_RANK["moderate"]


def _eligible(observation: dict[str, Any]) -> bool:
    return (
        bool(observation.get("observation_id"))
        and _SUFFICIENCY_RANK.get(str(observation.get("sufficiency")), 0) >= _MIN_HYPOTHESIS_RANK
    )


def _rate(observation: dict[str, Any]) -> float | None:
    value = (observation.get("metric") or {}).get("rate")
    return float(value) if isinstance(value, (float, int)) else None


def _merged_ids(observations: Iterable[dict[str, Any]], key: str) -> list[str]:
    return sorted({str(case_id) for observation in observations for case_id in observation.get(key) or []})


def _versions(observations: Iterable[dict[str, Any]], key: str) -> list[str]:
    return sorted({str(version) for observation in observations for version in observation.get(key) or []})


def _time_window(observations: list[dict[str, Any]]) -> dict[str, Any]:
    starts = [item.get("time_window", {}).get("from") for item in observations if item.get("time_window", {}).get("from")]
    ends = [item.get("time_window", {}).get("to") for item in observations if item.get("time_window", {}).get("to")]
    return {"from": min(starts) if starts else None, "to": max(ends) if ends else None}


def _hypothesis(
    *,
    family: str,
    statement: str,
    observations: list[dict[str, Any]],
    segment: dict[str, str],
    sample_size: int,
    limitations: list[str],
    case_observations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    source_ids = sorted(str(item["observation_id"]) for item in observations)
    evidence_observations = case_observations or observations
    payload = {
        "hypothesis_family": family,
        "statement": statement,
        "source_observation_ids": source_ids,
        "source_observation_types": sorted({str(item["observation_type"]) for item in observations}),
        "segment": segment,
        "supporting_case_ids": _merged_ids(evidence_observations, "supporting_case_ids"),
        "contradictory_case_ids": _merged_ids(evidence_observations, "contradictory_case_ids"),
        "sample_size": sample_size,
        "sufficiency": min(
            (str(item["sufficiency"]) for item in observations),
            key=lambda value: _SUFFICIENCY_RANK.get(value, 0),
        ),
        "descriptive_confidence": round(min(float(item["descriptive_confidence"]) for item in observations), 4),
        "mandate_versions": _versions(observations, "mandate_versions"),
        "thesis_versions": _versions(observations, "thesis_versions"),
        "policy_versions": _versions(observations, "policy_versions"),
        "time_window": _time_window(observations),
        "limitations": sorted(set(limitations + [
            "This is a descriptive/inferential hypothesis, not a causal conclusion.",
            "This hypothesis does not change policy or production behavior.",
            "Later outcome observations are excluded.",
        ])),
        "status": "descriptive_hypothesis",
    }
    identity = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    payload["hypothesis_id"] = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return payload


def build_hypotheses(
    observations: Iterable[dict[str, Any]], *, hypothesis_family: str | None = None
) -> list[dict[str, Any]]:
    eligible = [item for item in observations if _eligible(item)]
    results: list[dict[str, Any]] = []

    fund_override = next(
        (
            item for item in eligible
            if item.get("observation_type") == "override_rate"
            and item.get("segment") == {"scope": "fund"}
        ),
        None,
    )
    if fund_override:
        baseline = _rate(fund_override)
        if baseline is not None:
            for item in eligible:
                segment = item.get("segment") or {}
                rate = _rate(item)
                if (
                    item.get("observation_type") == "override_rate"
                    and segment.get("dimension") in {"sector", "stage", "geography"}
                    and rate is not None
                    and abs(rate - baseline) >= 0.2
                ):
                    dimension = str(segment["dimension"])
                    value = str(segment["value"])
                    direction = "more often" if rate > baseline else "less often"
                    results.append(_hypothesis(
                        family="segment_specific_behavior",
                        statement=(
                            f"The fund appears to record human overrides {direction} in {value} "
                            f"({rate:.0%}) than across the fund overall ({baseline:.0%})."
                        ),
                        observations=[fund_override, item],
                        segment={"dimension": dimension, "value": value},
                        sample_size=int(item["sample_size"]),
                        limitations=["The segment is compared with the recorded fund-wide baseline; this does not explain the difference."],
                        case_observations=[item],
                    ))

    for item in eligible:
        if item.get("observation_type") != "mandate_behavior":
            continue
        rates = (item.get("metric") or {}).get("agreement_rate_by_thesis") or {}
        if len(rates) < 2:
            continue
        ordered = sorted(((str(version), float(rate)) for version, rate in rates.items()), key=lambda pair: pair[0])
        low, high = min(ordered, key=lambda pair: pair[1]), max(ordered, key=lambda pair: pair[1])
        if high[1] - low[1] < 0.2:
            continue
        hypothesis = _hypothesis(
            family="mandate_behavior_divergence",
            statement=(
                f"Recorded recommendation/ruling agreement differs across thesis versions: "
                f"{high[0]} ({high[1]:.0%}) versus {low[0]} ({low[1]:.0%})."
            ),
            observations=[item], segment={"scope": "thesis_versions"}, sample_size=int(item["sample_size"]),
            limitations=["The comparison describes behavior under recorded thesis versions; it does not explain why the rates differ."],
        )
        hypothesis["mandate_versions"] = sorted(str(version) for version in rates)
        hypothesis["thesis_versions"] = sorted(str(version) for version in rates)
        results.append(hypothesis)

    if hypothesis_family:
        results = [item for item in results if item["hypothesis_family"] == hypothesis_family]
    results.sort(key=lambda item: (item["hypothesis_family"], item["hypothesis_id"]))
    return results
