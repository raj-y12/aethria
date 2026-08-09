"""Explainable deterministic ranking over historical Decision Case episodes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional


_DIMENSION_WEIGHTS = {
    "same_opportunity": 4.0,
    "same_company": 3.0,
    "sector": 3.0,
    "stage": 2.0,
    "geography": 1.5,
    "criterion_profile": 3.0,
    "evidence_coverage": 1.0,
    "mandate": 2.0,
    "recommendation": 0.5,
    "ruling": 0.5,
    "override": 0.5,
    "temporal_proximity": 1.0,
}


def _episode(case: Dict[str, Any]) -> Dict[str, Any]:
    episodes = case.get("cases") or []
    return episodes[0] if episodes else case


def _text(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("value", "name", "label", "sector", "stage", "geography", "country"):
            if value.get(key) is not None:
                return _text(value[key])
        return ""
    if isinstance(value, (list, tuple, set)):
        return ",".join(sorted(_text(item) for item in value if _text(item)))
    return str(value or "").strip().lower()


def _claim_dimensions(episode: Dict[str, Any]) -> Dict[str, str]:
    dimensions: Dict[str, str] = {}
    aliases = {
        "sector": "sector", "industry": "sector", "category": "sector",
        "stage": "stage", "funding_stage": "stage",
        "geography": "geography", "location": "geography", "country": "geography",
    }
    for claim in episode.get("evaluation", {}).get("claim_snapshot") or []:
        key = aliases.get(_text(claim.get("claim_type")))
        value = _text(claim.get("normalized_value")) or _text(claim.get("display_text"))
        if key and value and key not in dimensions:
            dimensions[key] = value
    return dimensions


def _criterion_profile(episode: Dict[str, Any]) -> Dict[str, float]:
    return {
        _text(item.get("criterion")): float(item.get("score"))
        for item in episode.get("criteria") or []
        if _text(item.get("criterion")) and item.get("score") is not None
    }


def _coverage(episode: Dict[str, Any]) -> Optional[float]:
    claims = episode.get("evaluation", {}).get("claim_snapshot") or []
    if not claims:
        return None
    covered = sum(
        bool(claim.get("supporting_evidence_ids") or claim.get("contradicting_evidence_ids"))
        for claim in claims
    )
    return covered / len(claims)


def _parse_time(value: Any) -> Optional[datetime]:
    if value is None or isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _days_between(left: Any, right: Any) -> Optional[float]:
    first, second = _parse_time(left), _parse_time(right)
    if first is None or second is None:
        return None
    return abs((first - second).total_seconds()) / 86400


def _first_ruling(episode: Dict[str, Any]) -> Dict[str, Any]:
    rulings = episode.get("rulings") or []
    if not rulings:
        return {}

    def sort_key(ruling: Dict[str, Any]) -> tuple[int, str, str]:
        created_at = _parse_time(ruling.get("created_at"))
        if created_at is not None:
            normalized = (
                created_at.astimezone(timezone.utc)
                if created_at.tzinfo is not None
                else created_at
            )
            return (0, normalized.isoformat(), str(ruling.get("ruling_id") or ""))
        return (1, str(ruling.get("created_at") or ""), str(ruling.get("ruling_id") or ""))

    return max(rulings, key=sort_key)


def _add_reason(reasons: list[str], text: str) -> None:
    if text not in reasons:
        reasons.append(text)


def _score(target: Dict[str, Any], candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    target_episode, candidate_episode = _episode(target), _episode(candidate)
    target_eval = target_episode.get("evaluation") or {}
    candidate_eval = candidate_episode.get("evaluation") or {}
    target_id, candidate_id = str(target_eval.get("evaluation_id") or ""), str(candidate_eval.get("evaluation_id") or "")
    if not candidate_id or candidate_id == target_id:
        return None

    target_opp, candidate_opp = target.get("opportunity", {}), candidate.get("opportunity", {})
    components: Dict[str, float] = {}
    reasons: list[str] = []
    limitations: list[str] = []
    target_dims, candidate_dims = _claim_dimensions(target_episode), _claim_dimensions(candidate_episode)
    for dimension in ("sector", "stage", "geography"):
        if target_dims.get(dimension) and target_dims.get(dimension) == candidate_dims.get(dimension):
            components[dimension] = _DIMENSION_WEIGHTS[dimension]
            _add_reason(reasons, f"same {dimension}: {target_dims[dimension]}")
    if target_dims.get("sector") == candidate_dims.get("sector") and target_dims.get("stage") == candidate_dims.get("stage"):
        if target_dims.get("sector") and target_dims.get("stage"):
            _add_reason(reasons, f"same {target_dims['stage']} {target_dims['sector']} profile")

    if target_opp.get("opportunity_id") and target_opp.get("opportunity_id") == candidate_opp.get("opportunity_id"):
        components["same_opportunity"] = _DIMENSION_WEIGHTS["same_opportunity"]
        _add_reason(reasons, "same canonical opportunity evaluated in a different episode")
    elif target_opp.get("company_id") and target_opp.get("company_id") == candidate_opp.get("company_id"):
        components["same_company"] = _DIMENSION_WEIGHTS["same_company"]
        _add_reason(reasons, "same canonical company")

    target_profile, candidate_profile = _criterion_profile(target_episode), _criterion_profile(candidate_episode)
    common = set(target_profile) & set(candidate_profile)
    if common:
        profile_similarity = sum(
            max(0.0, 1.0 - abs(target_profile[name] - candidate_profile[name]) / 10.0)
            for name in common
        ) / len(common)
        components["criterion_profile"] = round(_DIMENSION_WEIGHTS["criterion_profile"] * profile_similarity, 4)
        _add_reason(reasons, f"similar criterion score profile across {', '.join(sorted(common))}")

    target_coverage, candidate_coverage = _coverage(target_episode), _coverage(candidate_episode)
    if target_coverage is not None and candidate_coverage is not None and abs(target_coverage - candidate_coverage) <= 0.25:
        components["evidence_coverage"] = _DIMENSION_WEIGHTS["evidence_coverage"]
        _add_reason(reasons, "similar decision-time evidence coverage")

    target_thesis, candidate_thesis = _text(target_eval.get("thesis_version_id")), _text(candidate_eval.get("thesis_version_id"))
    if target_thesis and candidate_thesis:
        if target_thesis == candidate_thesis:
            components["mandate"] = _DIMENSION_WEIGHTS["mandate"]
            _add_reason(reasons, f"same mandate/thesis version: {target_thesis}")
        else:
            components["mandate"] = -1.0
            limitations.append("mandate/thesis versions differ; comparability is reduced")

    target_recommendation = _text((target_episode.get("recommendation") or {}).get("recommended_state"))
    candidate_recommendation = _text((candidate_episode.get("recommendation") or {}).get("recommended_state"))
    if target_recommendation and target_recommendation == candidate_recommendation:
        components["recommendation"] = _DIMENSION_WEIGHTS["recommendation"]
        _add_reason(reasons, f"same Aethria recommendation: {target_recommendation}")
    elif not candidate_recommendation:
        limitations.append("candidate has no linked recommendation")

    target_ruling, candidate_ruling = _first_ruling(target_episode), _first_ruling(candidate_episode)
    if target_ruling.get("decision") and target_ruling.get("decision") == candidate_ruling.get("decision"):
        components["ruling"] = _DIMENSION_WEIGHTS["ruling"]
        _add_reason(reasons, f"same human ruling: {target_ruling['decision']}")
    if target_ruling.get("override_type") and target_ruling.get("override_type") == candidate_ruling.get("override_type"):
        components["override"] = _DIMENSION_WEIGHTS["override"]
        _add_reason(reasons, f"same override type: {target_ruling['override_type']}")

    days = _days_between(target_episode.get("decision_time"), candidate_episode.get("decision_time"))
    if days is not None and days <= 730:
        components["temporal_proximity"] = 1.0 if days <= 365 else 0.5
        _add_reason(reasons, "temporally proximate decision episode")

    structural_keys = {
        "same_opportunity", "same_company", "sector", "stage", "geography", "criterion_profile"
    }
    structural_score = sum(
        value for key, value in components.items() if key in structural_keys and value > 0
    )
    has_strong_structural_match = any(
        key in components and components[key] >= 2.0
        for key in ("same_opportunity", "same_company", "sector", "stage", "criterion_profile")
    )
    if not reasons or structural_score < 2.0 or not has_strong_structural_match:
        return None
    unpaired = len(candidate.get("unpaired_rulings") or [])
    incomplete = not bool(candidate_recommendation) or not bool(candidate_episode.get("rulings")) or unpaired > 0
    if unpaired:
        limitations.append(f"candidate has {unpaired} unpaired ruling(s)")
    if not candidate_episode.get("rulings"):
        limitations.append("candidate has no linked human ruling")
    if not candidate.get("outcomes"):
        limitations.append("no later outcome recorded")
    return {
        "evaluation_id": candidate_id,
        "opportunity_id": candidate_opp.get("opportunity_id"),
        "decision_time": candidate_episode.get("decision_time"),
        "score": round(sum(components.values()), 4),
        "component_scores": components,
        "scoring_dimensions": sorted(components),
        "match_reasons": reasons,
        "limitations": limitations,
        "incomplete": incomplete,
        "later_outcomes": candidate.get("outcomes") or [],
        "outcome_context_used_for_scoring": False,
    }


def rank_precedents(
    target: Dict[str, Any], candidates: Iterable[Dict[str, Any]], *, limit: int = 10
) -> list[Dict[str, Any]]:
    ranked = [result for candidate in candidates if (result := _score(target, candidate)) is not None]
    ranked.sort(key=lambda item: (-item["score"], str(item.get("decision_time") or ""), item["evaluation_id"]))
    return ranked[: max(1, min(int(limit), 50))]
