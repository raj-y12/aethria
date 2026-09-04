"""Deterministic, descriptive observations over historical Decision Case episodes."""

from __future__ import annotations

import json
import hashlib
from collections import defaultdict
from datetime import datetime
from itertools import combinations
from typing import Any, Iterable

from utils.partner_codes import ruling_aligns_with_recommendation


MIN_SAMPLE_SIZE = 3
# These bands are copied from the active canonical score_bands policy.
_SCORE_BANDS = {
    "weak": (1, 3), "concerning": (4, 5),
    "promising": (6, 7), "strong": (8, 10),
}
MAX_INTERACTION_CRITERIA = 8


def _score_band_source() -> str:
    """Name the same rubric version that runtime policy resolution selected."""
    from core.policy_resolver import get_active_meta_snapshot

    version = str(get_active_meta_snapshot()["evaluation_rubric"])
    return f"resources/config/evaluation_rubric/{version}.json"


def _text(value: Any) -> str:
    return str(value or "").strip().lower()


def _time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if value:
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _case_id(case: dict[str, Any]) -> str:
    return str(case.get("evaluation_id") or "")


def _linked_cases(cases: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [
            case for case in cases
            if _case_id(case)
            and isinstance(case.get("recommendation"), dict)
            and isinstance(case.get("ruling"), dict)
            and case["recommendation"].get("recommended_state")
            and case["ruling"].get("decision")
        ],
        key=lambda case: (_time(case.get("decision_time")) or datetime.min, _case_id(case)),
    )


def _sufficiency(sample_size: int) -> tuple[str, float]:
    if sample_size < MIN_SAMPLE_SIZE:
        raise ValueError("insufficient sample")
    if sample_size <= 5:
        return "emerging", 0.55
    if sample_size <= 9:
        return "moderate", 0.75
    return "strong", 0.9


def _window(cases: list[dict[str, Any]]) -> dict[str, Any]:
    times = [case.get("decision_time") for case in cases if case.get("decision_time") is not None]
    return {
        "from": min(times).isoformat() if times and isinstance(min(times), datetime) else (str(min(times)) if times else None),
        "to": max(times).isoformat() if times and isinstance(max(times), datetime) else (str(max(times)) if times else None),
    }


def _versions(cases: list[dict[str, Any]], key: str) -> list[str]:
    return sorted({_text(case.get(key)) for case in cases if _text(case.get(key))})


def _interpretation_provenance(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    provenance: list[dict[str, Any]] = []
    for case in sorted(cases, key=lambda item: _case_id(item)):
        interpretation = case.get("interpretation") or {}
        if not interpretation.get("version"):
            continue
        ruling = case.get("ruling") or {}
        provenance.append({
            "case_id": _case_id(case),
            "ruling_id": str(ruling.get("ruling_id") or ""),
            "interpretation_id": str(interpretation.get("interpretation_id") or ""),
            "version": interpretation.get("version"),
            "source": interpretation.get("source"),
            "created_at": interpretation.get("created_at"),
            **({"provenance": interpretation["provenance"]} if interpretation.get("provenance") is not None else {}),
        })
    return provenance


def _observation(
    *,
    observation_type: str,
    segment: dict[str, str],
    cases: list[dict[str, Any]],
    supporting: list[str],
    contradictory: list[str],
    metric: dict[str, Any],
    limitations: list[str] | None = None,
) -> dict[str, Any] | None:
    if len(cases) < MIN_SAMPLE_SIZE:
        return None
    sufficiency, confidence = _sufficiency(len(cases))
    interpretation_provenance = _interpretation_provenance(cases)
    return {
        "observation_type": observation_type,
        "segment": segment,
        "supporting_case_ids": sorted(set(supporting)),
        "contradictory_case_ids": sorted(set(contradictory)),
        "sample_size": len(cases),
        "time_window": _window(cases),
        "thesis_versions": _versions(cases, "thesis_version_id"),
        "mandate_versions": _versions(cases, "thesis_version_id"),
        "policy_versions": _versions(cases, "policy_version_id"),
        "metric": metric,
        "sufficiency": sufficiency,
        "descriptive_confidence": confidence,
        "interpretation_as_of": "latest_retrospective" if interpretation_provenance else "none_available",
        "interpretation_provenance": interpretation_provenance,
        "limitations": sorted(set((limitations or []) + [
            "Descriptive association only; this observation does not establish causality.",
            "Later outcome observations are excluded from this metric.",
        ])),
    }


def _factor_values(case: dict[str, Any]) -> set[str]:
    interpretation = case.get("interpretation") or {}
    values: set[str] = set()
    for key in ("positive_factors", "negative_factors", "accepted_risks", "decisive_factors"):
        raw = interpretation.get(key) or []
        if isinstance(raw, str):
            raw = [raw]
        for value in raw:
            text = _text(value.get("text") if isinstance(value, dict) else value)
            if text:
                values.add(text)
    return values


def _score_band(score: Any) -> str | None:
    try:
        numeric = float(score)
    except (TypeError, ValueError):
        return None
    for band, (lower, upper) in _SCORE_BANDS.items():
        if lower <= numeric <= upper:
            return band
    return None


def _criteria(case: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in case.get("criteria") or []:
        criterion = _text(item.get("criterion") or item.get("criterion_id"))
        band = _score_band(item.get("score"))
        if criterion and band:
            result[criterion] = band
    return result


def _approved(case: dict[str, Any]) -> bool:
    return _text((case.get("ruling") or {}).get("decision")) in {"advance", "invest"}


def _interaction(
    *,
    family: str,
    cases: list[dict[str, Any]],
    supporting: list[str],
    contradictory: list[str],
    involved_criteria: list[str] | None = None,
    involved_factors: list[str] | None = None,
    direction: str,
    value_ranges: dict[str, str] | None = None,
    segment: dict[str, str],
) -> dict[str, Any] | None:
    item = _observation(
        observation_type=family,
        segment=segment,
        cases=cases,
        supporting=supporting,
        contradictory=contradictory,
        metric={"supporting_count": len(supporting), "contradictory_count": len(contradictory)},
        limitations=[
            "This is an observed association/trade-off, not an inferred policy rule.",
            "Score bands are canonical rubric bands; no new numeric threshold was introduced.",
        ],
    )
    if item is None:
        return None
    item.update({
        "observation_family": family,
        "involved_criteria": sorted(involved_criteria or []),
        "involved_factors": sorted(involved_factors or []),
        "direction": direction,
        "value_ranges": value_ranges or {},
        "score_band_source": _score_band_source(),
        "segment_scope": "cross_segment" if segment == {"scope": "fund"} else "segment_specific",
    })
    return item


def _segments(cases: list[dict[str, Any]]) -> list[tuple[dict[str, str], list[dict[str, Any]]]]:
    segments: list[tuple[dict[str, str], list[dict[str, Any]]]] = [({"scope": "fund"}, cases)]
    for dimension in ("sector", "stage", "geography"):
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for case in cases:
            value = _text((case.get("dimensions") or {}).get(dimension))
            if value:
                groups[value].append(case)
        segments.extend(
            (({"dimension": dimension, "value": value}, group) for value, group in sorted(groups.items()))
        )
    thesis_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        thesis = _text(case.get("thesis_version_id"))
        if thesis:
            thesis_groups[thesis].append(case)
    segments.extend(
        (({"dimension": "thesis_version_id", "value": value}, group) for value, group in sorted(thesis_groups.items()))
    )
    return segments


def _build_interactions(linked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for segment, group in _segments(linked):
        criterion_names = sorted({criterion for case in group for criterion in _criteria(case)})[:MAX_INTERACTION_CRITERIA]
        for first, second in combinations(criterion_names, 2):
            for strong, weak in ((first, second), (second, first)):
                profile = [
                    case for case in group
                    if _criteria(case).get(strong) == "strong" and _criteria(case).get(weak) == "weak"
                ]
                supporting = [_case_id(case) for case in profile if _approved(case)]
                contradictory = [_case_id(case) for case in profile if not _approved(case)]
                if len(supporting) >= MIN_SAMPLE_SIZE:
                    item = _interaction(
                        family="criterion_tradeoff", cases=profile, supporting=supporting,
                        contradictory=contradictory, involved_criteria=[weak, strong],
                        direction=f"strong {strong} / weak {weak}",
                        value_ranges={strong: "strong", weak: "weak"}, segment=segment,
                    )
                    if item:
                        observations.append(item)

        for weak in criterion_names:
            gate_profile = [
                case for case in group
                if _criteria(case).get(weak) == "weak"
                and any(band == "strong" for name, band in _criteria(case).items() if name != weak)
            ]
            gate_supporting = [_case_id(case) for case in gate_profile if not _approved(case)]
            gate_contradictory = [_case_id(case) for case in gate_profile if _approved(case)]
            if len(gate_supporting) >= MIN_SAMPLE_SIZE:
                item = _interaction(
                    family="practical_gate", cases=gate_profile, supporting=gate_supporting,
                    contradictory=gate_contradictory, involved_criteria=[weak],
                    direction=f"weak {weak} associated with non-approval",
                    value_ranges={weak: "weak"}, segment=segment,
                )
                if item:
                    observations.append(item)

        risk_pairs: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for case in group:
            interpretation = case.get("interpretation") or {}
            risks = interpretation.get("accepted_risks") or []
            factors = interpretation.get("positive_factors") or []
            risks = [(_text(item.get("text") if isinstance(item, dict) else item)) for item in risks]
            factors = [(_text(item.get("text") if isinstance(item, dict) else item)) for item in factors]
            for risk in sorted(set(risks)):
                for positive in sorted(set(factors)):
                    if risk and positive:
                        risk_pairs[(risk, positive)].append(case)
        for (risk, positive), profile in sorted(risk_pairs.items()):
            supporting = [_case_id(case) for case in profile if _approved(case)]
            contradictory = [_case_id(case) for case in profile if not _approved(case)]
            if len(supporting) < MIN_SAMPLE_SIZE:
                continue
            item = _interaction(
                family="discounted_risk", cases=profile, supporting=supporting,
                contradictory=contradictory, involved_factors=[positive, risk],
                direction="accepted risk with recurring positive factor",
                segment=segment,
            )
            if item:
                observations.append(item)
    return observations


def _filtered(
    cases: Iterable[dict[str, Any]],
    *,
    sector: str | None = None,
    stage: str | None = None,
    geography: str | None = None,
    thesis_version_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[dict[str, Any]]:
    result = []
    for case in cases:
        dimensions = case.get("dimensions") or {}
        decision_time = _time(case.get("decision_time"))
        if sector and _text(dimensions.get("sector")) != _text(sector):
            continue
        if stage and _text(dimensions.get("stage")) != _text(stage):
            continue
        if geography and _text(dimensions.get("geography")) != _text(geography):
            continue
        if thesis_version_id and _text(case.get("thesis_version_id")) != _text(thesis_version_id):
            continue
        if date_from and (decision_time is None or decision_time < date_from):
            continue
        if date_to and (decision_time is None or decision_time > date_to):
            continue
        result.append(case)
    return result


def build_observations(
    cases: Iterable[dict[str, Any]],
    *,
    sector: str | None = None,
    stage: str | None = None,
    geography: str | None = None,
    thesis_version_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    observation_type: str | None = None,
) -> list[dict[str, Any]]:
    filtered = _filtered(
        cases, sector=sector, stage=stage, geography=geography,
        thesis_version_id=thesis_version_id, date_from=date_from, date_to=date_to,
    )
    linked = _linked_cases(filtered)
    observations: list[dict[str, Any]] = []
    observations.extend(_build_interactions(linked))

    aligned = [
        case for case in linked
        if ruling_aligns_with_recommendation(
            case["recommendation"]["recommended_state"], case["ruling"]["decision"]
        )
    ]
    agreement = _observation(
        observation_type="recommendation_ruling_agreement", segment={"scope": "fund"},
        cases=linked, supporting=[_case_id(case) for case in aligned],
        contradictory=[_case_id(case) for case in linked if case not in aligned],
        metric={"numerator": len(aligned), "denominator": len(linked), "rate": len(aligned) / len(linked)}
        if linked else {},
    )
    if agreement:
        observations.append(agreement)

    overridden = [case for case in linked if _text((case.get("ruling") or {}).get("override_type"))]
    fund_override = _observation(
        observation_type="override_rate", segment={"scope": "fund"}, cases=linked,
        supporting=[_case_id(case) for case in overridden],
        contradictory=[_case_id(case) for case in linked if case not in overridden],
        metric={"numerator": len(overridden), "denominator": len(linked), "rate": len(overridden) / len(linked)}
        if linked else {},
    )
    if fund_override:
        observations.append(fund_override)

    for dimension in ("sector", "stage", "geography"):
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for case in linked:
            value = _text((case.get("dimensions") or {}).get(dimension))
            if value:
                groups[value].append(case)
        for value, group in groups.items():
            overridden = [case for case in group if _text((case.get("ruling") or {}).get("override_type"))]
            item = _observation(
                observation_type="override_rate", segment={"dimension": dimension, "value": value},
                cases=group, supporting=[_case_id(case) for case in overridden],
                contradictory=[_case_id(case) for case in group if case not in overridden],
                metric={"numerator": len(overridden), "denominator": len(group), "rate": len(overridden) / len(group)},
            )
            if item:
                observations.append(item)

    factor_cases: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in linked:
        for factor in _factor_values(case):
            factor_cases[factor].append(case)
    for factor, group in factor_cases.items():
        item = _observation(
            observation_type="recurring_factor", segment={"factor": factor}, cases=group,
            supporting=[_case_id(case) for case in group], contradictory=[], metric={"count": len(group)},
        )
        if item:
            observations.append(item)

    by_thesis: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in linked:
        thesis = _text(case.get("thesis_version_id"))
        if thesis:
            by_thesis[thesis].append(case)
    if len(by_thesis) >= 2 and all(len(group) >= MIN_SAMPLE_SIZE for group in by_thesis.values()):
        rates = {
            thesis: round(
                sum(case in aligned for case in group) / len(group), 6
            )
            for thesis, group in sorted(by_thesis.items())
        }
        item = _observation(
            observation_type="mandate_behavior", segment={"scope": "thesis_versions"}, cases=linked,
            supporting=[_case_id(case) for case in aligned],
            contradictory=[_case_id(case) for case in linked if case not in aligned],
            metric={"agreement_rate_by_thesis": rates},
            limitations=["Behavior is grouped by recorded thesis version; it does not explain why behavior changed."],
        )
        if item:
            observations.append(item)

    if observation_type:
        observations = [item for item in observations if item["observation_type"] == observation_type]
    for item in observations:
        canonical = json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        item["observation_id"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]
    observations.sort(
        key=lambda item: (
            item["observation_type"],
            json.dumps(item["segment"], sort_keys=True, separators=(",", ":")),
        )
    )
    return observations
