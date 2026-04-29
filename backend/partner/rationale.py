"""
Deterministic partner decision rationale aligned with canonical score-band recommendation.

Rationale is composed AFTER final_recommendation is fixed so prose cannot contradict PASS/MONITOR/INVEST.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, List, Tuple


# Ordered dominance for narrative lead-in (first matching tag wins).
TAG_PRIORITY: Tuple[str, ...] = (
    "critical_risk",
    "weak_verdict",
    "below_pass_threshold",
    "contradictory_scores",
    "reviewer_disagreement",
    "missing_qualitative",
    "grey_zone",
    "borderline_medium",
    "strong_below_yes_bar",
    "medium_watch_high",
    "strong_commit",
    "default_pass",
)


def derive_situation_tags(
    *,
    effective_verdict: str,
    avg_score: float,
    min_avg_pass: float,
    min_avg_strong_yes: float,
    min_avg_medium_maybe: float,
    min_avg_borderline_low: float,
    max_avg_borderline_high: float,
    has_critical_risk: bool,
    has_contradiction: bool,
    grey_zone_active: bool,
    reviewer_disagreement: bool,
    has_missing_critical_qualitative: bool,
) -> FrozenSet[str]:
    tags: set[str] = set()
    if has_critical_risk:
        tags.add("critical_risk")
    if effective_verdict == "WEAK":
        tags.add("weak_verdict")
    if avg_score < min_avg_pass:
        tags.add("below_pass_threshold")
    if effective_verdict == "STRONG" and min_avg_pass <= avg_score < min_avg_strong_yes:
        tags.add("strong_below_yes_bar")
    if effective_verdict == "STRONG" and avg_score >= min_avg_strong_yes:
        tags.add("strong_commit")
    if effective_verdict == "MEDIUM" and avg_score >= min_avg_medium_maybe:
        tags.add("medium_watch_high")
    if effective_verdict == "MEDIUM" and min_avg_borderline_low <= avg_score < max_avg_borderline_high:
        tags.add("borderline_medium")
    if grey_zone_active:
        tags.add("grey_zone")
    if has_contradiction:
        tags.add("contradictory_scores")
    if reviewer_disagreement:
        tags.add("reviewer_disagreement")
    if has_missing_critical_qualitative:
        tags.add("missing_qualitative")
    if not tags:
        tags.add("default_pass")
    return frozenset(tags)


def primary_tag(tags: FrozenSet[str]) -> str:
    for t in TAG_PRIORITY:
        if t in tags:
            return t
    return "default_pass"


def ordered_decision_drivers(tags: FrozenSet[str], primary: str) -> List[str]:
    """Stable list for analytics/UI: primary first, then remaining tags by TAG_PRIORITY."""
    out = [primary]
    for t in TAG_PRIORITY:
        if t in tags and t != primary:
            out.append(t)
    return out


def _dim_line(m: int, p: int, t: int, e: int) -> str:
    return (
        f"Market {m}/10, Product {p}/10, Technical {t}/10, Execution {e}/10."
    )


def _tension_sentence(
    *,
    has_contradiction: bool,
    reviewer_disagreement: bool,
    market_score: int,
    product_score: int,
    technical_score: int,
    execution_score: int,
    gap_threshold: int = 3,
) -> str:
    if has_contradiction:
        return (
            "Material tension across dimensions warrants reconciliation before commitment."
        )
    if reviewer_disagreement:
        return (
            "Reviewer perspectives diverged; narrow uncertainty with targeted diligence."
        )
    scores = [market_score, product_score, technical_score, execution_score]
    hi = max(scores)
    lo = min(scores)
    if hi - lo >= gap_threshold:
        return (
            f"Score dispersion is notable (high {hi}/10 vs low {lo}/10); focus validation on the weakest link."
        )
    return ""


def compose_decision_rationale(
    *,
    final_recommendation: str,
    tags: FrozenSet[str],
    primary: str,
    label: str,
    avg_score: float,
    market_score: int,
    product_score: int,
    technical_score: int,
    execution_score: int,
    min_avg_pass: float,
    min_avg_strong_yes: float,
    min_avg_medium_maybe: float,
    min_avg_borderline_low: float,
    max_avg_borderline_high: float,
    has_contradiction: bool,
    reviewer_disagreement: bool,
    sector_concentration_note: bool,
) -> Tuple[str, List[str]]:
    """
    Returns (decision_rationale, decision_drivers).
    """
    drivers = ordered_decision_drivers(tags, primary)
    dims = _dim_line(market_score, product_score, technical_score, execution_score)
    tension = _tension_sentence(
        has_contradiction=has_contradiction,
        reviewer_disagreement=reviewer_disagreement,
        market_score=market_score,
        product_score=product_score,
        technical_score=technical_score,
        execution_score=execution_score,
    )

    parts: List[str] = []

    if final_recommendation == "PASS":
        if primary == "critical_risk":
            parts.append(
                "We pass at this stage because unresolved diligence risks remain elevated "
                "(e.g., regulatory exposure or execution feasibility)."
            )
        elif primary == "weak_verdict":
            parts.append(
                f"We pass at this stage given cautious reviewer quality versus our bar "
                f"(quality read: {label})."
            )
        elif primary == "below_pass_threshold":
            parts.append(
                f"We pass at this stage: average score {avg_score:.1f}/10 sits below our "
                f"minimum pass threshold ({min_avg_pass})."
            )
        else:
            parts.append(
                f"We pass at this stage: the profile does not clear underwriting yet "
                f"(quality read: {label})."
            )
        parts.append(f"Average score {avg_score:.1f}/10. {dims}")
        if tension:
            parts.append(tension)
        parts.append(
            "Revisit when new evidence improves conviction or materially reduces risk."
        )

    elif final_recommendation == "MONITOR":
        if primary == "critical_risk":
            parts.append(
                "We monitor at this stage while material diligence risks are clarified "
                "with credible evidence before advancing."
            )
        elif primary == "weak_verdict":
            parts.append(
                f"We monitor at this stage with a cautious quality read ({label}) versus mandate; "
                f"averages sit at {avg_score:.1f}/10 but fundamentals still need proof."
            )
        elif primary == "strong_below_yes_bar":
            parts.append(
                f"We monitor at this stage: scores clear the base hurdle ({min_avg_pass}) "
                f"but remain below our strong-YES bar ({min_avg_strong_yes})."
            )
        elif primary == "borderline_medium":
            parts.append(
                f"We monitor at this stage: averages sit in the borderline band "
                f"({min_avg_borderline_low:.1f}-{max_avg_borderline_high:.1f}), "
                f"below the higher watchlist threshold ({min_avg_medium_maybe}) "
                f"yet at or above the pass bar ({min_avg_pass})."
            )
        elif primary == "medium_watch_high":
            parts.append(
                f"We monitor at this stage with constructive averages ({avg_score:.1f}/10) "
                f"while collecting incremental proof on execution and market pull."
            )
        elif primary == "grey_zone":
            parts.append(
                "We monitor at this stage given confidence-adjusted scores sit in the grey zone "
                "where incremental diligence commonly changes conviction."
            )
        elif primary == "contradictory_scores":
            parts.append(
                "We monitor at this stage because reviewer dimensions imply materially mixed signals."
            )
        else:
            parts.append(
                f"We monitor at this stage pending stronger validation signals versus our mandate "
                f"(average {avg_score:.1f}/10)."
            )
        parts.append(dims)
        if tension:
            parts.append(tension)
        parts.append(
            "Track milestones that would upgrade or downgrade the thesis."
        )

    else:  # INVEST
        if primary == "critical_risk":
            parts.append(
                "We advance subject to confirmatory diligence that materially resolves "
                "flagged diligence risks despite headline scores."
            )
        elif primary == "missing_qualitative":
            parts.append(
                "We advance to confirmatory diligence; qualitative gaps on team or business model "
                "should be closed in parallel with standard IC work."
            )
        else:
            parts.append(
                f"We advance to confirmatory diligence given scores versus our bar "
                f"(average {avg_score:.1f}/10)."
            )
        parts.append(dims)
        if tension:
            parts.append(tension)
        parts.append(
            "Proceed with ownership, pricing, and technical diligence consistent with policy."
        )

    rationale = " ".join(p for p in parts if p).strip()
    if sector_concentration_note:
        rationale += " Portfolio concentration in this sector merits sizing discipline."
    return rationale, drivers
