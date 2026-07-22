"""Scoring consistency audit: narrative/score alignment, signal density, memo quality gate."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple

from config.scoring_config import CANONICAL_DIMENSIONS, DIMENSION_SCORE_BANDS


ConsistencyStatus = Literal["consistent", "mildly_inconsistent", "materially_inconsistent"]

DIMENSION_KEYS = ("market", "product", "technical", "execution", "defensibility")

# ─── Positive signal catalog (keyword → tier weight) ─────────────────────────

_HIGH_POSITIVE: Tuple[Tuple[str, str], ...] = (
    (r"\by\s*combinator\b|\byc\s+(backed|alumni|batch)\b", "YC or top-tier accelerator backing"),
    (r"\btier[- ]?1\s+accelerator\b|\btechstars\b|\ba16z\b|\bsequoia\b", "Tier-1 accelerator or lead investor"),
    (r"\brevenue\s+growth\b|\b\d+%\s+(yoy|year[- ]over[- ]year)\b|\bhypergrowth\b", "Revenue growth trajectory"),
    (r"\blarge\s+contract\b|\benterprise\s+contract\b|\b\d+m\s+arr\b|\b\d+m\s+revenue\b", "Large commercial contracts or ARR"),
    (r"\bstrong\s+retention\b|\bhigh\s+retention\b|\blow\s+churn\b|\bnet\s+retention\b", "Strong retention metrics"),
    (r"\bpatent\b|\bip\s+portfolio\b|\bproprietary\s+technology\b", "Patents or proprietary technology"),
    (r"\bnetwork\s+effect\b|\bdata\s+moat\b|\bplatform\s+lock[- ]in\b", "Network effects or compounding moat"),
    (r"\bprior\s+exit\b|\bserial\s+founder\b|\bexited\s+founder\b", "Founder exit track record"),
    (r"\bproduct[- ]market\s+fit\b|\bpmf\b|\bstrong\s+pull\b", "Product-market fit indicators"),
    (r"\bdistribution\s+advantage\b|\bchannel\s+fit\b|\brepeatable\s+gtm\b", "Distribution or GTM advantage"),
    (r"\btechnical\s+moat\b|\bdefensible\s+architecture\b|\bdeeptech\b", "Technical moat"),
)

_MEDIUM_POSITIVE: Tuple[Tuple[str, str], ...] = (
    (r"\bpilot\b|\bpilots\b|\bearly\s+customer\b|\bpaying\s+customer\b", "Early customer or pilot traction"),
    (r"\bseries\s+[ab]\b|\bseed\s+round\b|\bfunded\b", "Institutional funding stage"),
    (r"\bus\s+expansion\b|\binternational\s+expansion\b", "Geographic expansion"),
    (r"\bpartnership\b|\bchannel\s+partner\b", "Strategic partnerships"),
    (r"\bstrong\s+team\b|\bdomain\s+expertise\b", "Credible team credentials"),
    (r"\bdifferentiated\b|\bunique\s+approach\b|\b10x\b", "Differentiation claims"),
    (r"\bscalable\b|\bhigh\s+margin\b", "Scalability or margin profile"),
)

_WEAK_POSITIVE: Tuple[Tuple[str, str], ...] = (
    (r"\bmvp\b|\bbeta\b|\bprototype\b", "Pre-scale product stage"),
    (r"\bearly\s+traction\b|\binitial\s+traction\b", "Early traction language"),
    (r"\bgrowing\s+market\b|\btailwind\b", "Market tailwinds"),
    (r"\bclear\s+value\s+prop\b", "Articulated value proposition"),
)

# ─── Negative signal catalog ──────────────────────────────────────────────────

_HIGH_NEGATIVE: Tuple[Tuple[str, str], ...] = (
    (r"\bno\s+gtm\b|\bgtm\s+unclear\b|\bgo[- ]to[- ]market\s+unclear\b|\bundefined\s+acquisition\b", "Unclear go-to-market"),
    (r"\bno\s+traction\b|\bpre[- ]revenue\b|\bno\s+revenue\b|\bzero\s+revenue\b", "No revenue or traction"),
    (r"\bfounder\s+risk\b|\bkey[- ]person\s+risk\b|\bweak\s+team\b", "Founder or team risk"),
    (r"\bcustomer\s+concentration\b|\bsingle\s+customer\b", "Customer concentration"),
    (r"\bregulatory\s+risk\b|\bcompliance\s+burden\b|\bregulation\b", "Regulatory risk"),
    (r"\bhigh\s+burn\b|\bcash\s+runway\b|\bburn\s+rate\b", "Burn or runway pressure"),
    (r"\bweak\s+retention\b|\bhigh\s+churn\b|\blow\s+retention\b", "Weak retention"),
    (r"\bcrowded\s+market\b|\bintense\s+competition\b|\bcommoditiz", "Crowded or commoditized market"),
    (r"\bpoor\s+margin\b|\blow\s+margin\b|\bnegative\s+unit\s+economics\b", "Margin or unit economics concern"),
)

_MEDIUM_NEGATIVE: Tuple[Tuple[str, str], ...] = (
    (r"\bunproven\b|\bunvalidated\b|\bnot\s+verified\b", "Unvalidated claims"),
    (r"\blimited\s+evidence\b|\binsufficient\s+data\b", "Limited supporting data"),
    (r"\bearly\s+stage\b|\bimmature\b", "Early-stage maturity gaps"),
    (r"\bcompetitive\s+pressure\b|\bincumbent\b", "Competitive pressure"),
)

_WEAK_NEGATIVE: Tuple[Tuple[str, str], ...] = (
    (r"\bunclear\b|\bunknown\b|\bunquantified\b", "Ambiguity in evidence"),
    (r"\bmissing\b|\bnot\s+disclosed\b", "Undisclosed metrics"),
)


@dataclass
class SignalDensity:
    positive_signal_strength: float
    positive_signal_count: int
    positive_high: int
    positive_medium: int
    positive_weak: int
    negative_signal_strength: float
    negative_signal_count: int
    negative_high: int
    negative_medium: int
    negative_weak: int
    positive_matches: List[str] = field(default_factory=list)
    negative_matches: List[str] = field(default_factory=list)


@dataclass
class DimensionConsistency:
    dimension: str
    score: float
    consistency_status: ConsistencyStatus
    consistency_explanation: str
    consistency_penalty: float
    signal_density: SignalDensity
    evidence_coverage: str
    evidence_coverage_warning: Optional[str]
    implied_score_range: Tuple[float, float]
    score_justification: str
    why_not_higher: List[str]


@dataclass
class ConsistencyAudit:
    dimensions: Dict[str, DimensionConsistency]
    overall_status: ConsistencyStatus
    review_notes: List[str] = field(default_factory=list)


def _clamp(value: float, lo: float = 0.0, hi: float = 10.0) -> float:
    return max(lo, min(hi, value))


def _match_catalog(text: str, catalog: Tuple[Tuple[str, str], ...]) -> List[str]:
    lower = text.lower()
    hits: List[str] = []
    for pattern, label in catalog:
        if re.search(pattern, lower):
            hits.append(label)
    return hits


def extract_signal_density(text: str, *, component_boost: float = 0.0) -> SignalDensity:
    """Count positive/negative signals in narrative corpus and derive 0–10 strength."""
    high_pos = _match_catalog(text, _HIGH_POSITIVE)
    med_pos = _match_catalog(text, _MEDIUM_POSITIVE)
    weak_pos = _match_catalog(text, _WEAK_POSITIVE)
    high_neg = _match_catalog(text, _HIGH_NEGATIVE)
    med_neg = _match_catalog(text, _MEDIUM_NEGATIVE)
    weak_neg = _match_catalog(text, _WEAK_NEGATIVE)

    pos_strength = _clamp(
        len(high_pos) * 2.2 + len(med_pos) * 1.1 + len(weak_pos) * 0.4 + component_boost
    )
    neg_strength = _clamp(high_neg.__len__() * 2.0 + len(med_neg) * 1.0 + len(weak_neg) * 0.35)

    return SignalDensity(
        positive_signal_strength=round(pos_strength, 2),
        positive_signal_count=len(high_pos) + len(med_pos) + len(weak_pos),
        positive_high=len(high_pos),
        positive_medium=len(med_pos),
        positive_weak=len(weak_pos),
        positive_matches=high_pos + med_pos + weak_pos,
        negative_signal_strength=round(neg_strength, 2),
        negative_signal_count=len(high_neg) + len(med_neg) + len(weak_neg),
        negative_high=len(high_neg),
        negative_medium=len(med_neg),
        negative_weak=len(weak_neg),
        negative_matches=high_neg + med_neg + weak_neg,
    )


def evidence_coverage_label(confidence: float | None, missing_count: int) -> str:
    if confidence is None:
        return "Limited"
    c = max(0.0, min(1.0, float(confidence)))
    if missing_count >= 4:
        return "Limited"
    if c >= 0.75 and missing_count <= 1:
        return "Extensive"
    if c >= 0.50 and missing_count <= 2:
        return "Strong"
    if c >= 0.25 and missing_count <= 3:
        return "Moderate"
    return "Limited"


def evidence_coverage_warning(
    score: float,
    coverage: str,
    missing_count: int,
) -> Optional[str]:
    if score >= 7.0 and coverage in ("Limited", "Moderate") and missing_count >= 2:
        return "Analyst review recommended: evidence coverage is limited relative to the score."
    if score >= 8.0 and coverage == "Limited":
        return "Analyst review recommended: evidence coverage is limited relative to the score."
    return None


def build_analyst_review_note(audit: DimensionConsistency) -> Optional[str]:
    """Soft, non-blocking note for memo UI. Never uses publication/gate language."""
    if audit.evidence_coverage_warning:
        return audit.evidence_coverage_warning
    if audit.consistency_status == "materially_inconsistent":
        pos = audit.signal_density.positive_signal_strength
        neg = audit.signal_density.negative_signal_strength
        if audit.score <= 5.5 and pos >= 5.5:
            return "Analyst review recommended: the narrative appears stronger than the assigned score."
        if audit.score >= 8.0 and neg >= 4.5 and pos < 4.0:
            return "Analyst review recommended: evidence coverage is limited relative to the score."
        return "Analyst review recommended: score narrative may require review."
    if audit.consistency_status == "mildly_inconsistent":
        return "Score narrative may require review."
    return None


def _implied_score_range(density: SignalDensity) -> Tuple[float, float]:
    center = 5.0 + (density.positive_signal_strength - density.negative_signal_strength) * 0.45
    center = _clamp(center)
    spread = 1.2 if density.positive_high + density.negative_high >= 2 else 1.8
    return (_clamp(center - spread), _clamp(center + spread))


def _primary_positive(supports: List[str], density: SignalDensity, components: List[Dict]) -> str:
    if supports:
        return supports[0].rstrip(".")
    strong = [c["label"].lower() for c in components if c.get("has_evidence") and c.get("score", 0) >= 7]
    if strong:
        return f"evidence around {strong[0]}"
    if density.positive_matches:
        return density.positive_matches[0].lower()
    return "available diligence, though conviction drivers remain thin"


def _primary_limiter(weakens: List[str], missing: List[Dict], density: SignalDensity) -> str:
    if weakens:
        return weakens[0].rstrip(".")
    if missing:
        return f"{missing[0]['label'].lower()} has not been independently verified"
    if density.negative_matches:
        return density.negative_matches[0].lower()
    return "material gaps in independently verified metrics"


def _above_average_reason(score: float, supports: List[str], density: SignalDensity) -> str:
    if score <= 5.0:
        return "the opportunity shows enough signal to remain in the diligence queue"
    if supports and len(supports) >= 2:
        return "multiple corroborating factors partially offset the main constraints"
    if density.positive_high >= 1:
        return "at least one high-quality positive signal prevents a lower rating"
    return "baseline market and product signals are not structurally broken"


def _higher_rating_blocker(missing: List[Dict], weakens: List[str], density: SignalDensity) -> str:
    if missing:
        return missing[0]["label"].lower()
    if weakens:
        w = weakens[0].lower()
        if "not been" in w or "unverified" in w:
            return w.split(" has")[0] if " has" in w else w
        return w.rstrip(".")
    if density.negative_high >= 1:
        return density.negative_matches[0].lower()
    return "repeatable traction and retention proof"


def build_score_justification(
    dimension_key: str,
    score: float,
    *,
    supports: List[str],
    weakens: List[str],
    missing_evidence: List[Dict[str, str]],
    density: SignalDensity,
    components: List[Dict[str, Any]],
) -> str:
    """Four-part analyst justification; no scoring-engine language."""
    dim_label = CANONICAL_DIMENSIONS.get(dimension_key, {}).get("label", dimension_key.title())
    rounded = max(1, min(10, round(score)))
    positive = _primary_positive(supports, density, components)
    limiter = _primary_limiter(weakens, missing_evidence, density)
    above = _above_average_reason(score, supports, density)
    blocker = _higher_rating_blocker(missing_evidence, weakens, density)

    return (
        f"{dim_label} scores {rounded}/10 because {positive}. "
        f"The score is constrained by {limiter}. "
        f"It remains above a pass threshold due to {above}. "
        f"Further evidence on {blocker} would be required to justify a higher rating."
    )


def build_why_not_higher(
    score: float,
    *,
    weakens: List[str],
    missing_evidence: List[Dict[str, str]],
    density: SignalDensity,
) -> List[str]:
    if score < 6.0:
        return []
    items: List[str] = []
    for m in missing_evidence[:3]:
        items.append(f"No independent validation of {m['label'].lower()}")
    for w in weakens[:3]:
        cleaned = w.rstrip(".")
        if cleaned and cleaned not in items:
            items.append(cleaned)
    for neg in density.negative_matches[:2]:
        if len(items) >= 5:
            break
        phrase = neg if neg[0].islower() else neg.lower()
        if phrase not in " ".join(items).lower():
            items.append(phrase)
    return items[:5]


def _classify_consistency(
    score: float,
    density: SignalDensity,
    implied_lo: float,
    implied_hi: float,
    *,
    supports_count: int,
    weakens_count: int,
    missing_count: int,
    evidence_coverage: str,
) -> Tuple[ConsistencyStatus, str, float]:
    """Return status, explanation, penalty."""
    center = (implied_lo + implied_hi) / 2.0
    delta = score - center

    # Case A: bullish narrative, mediocre score
    if score <= 5.5 and density.positive_signal_strength >= 5.5 and density.positive_high >= 2:
        penalty = _clamp((density.positive_signal_strength - score) / 5.0)
        return (
            "materially_inconsistent",
            (
                f"Narrative contains multiple strong positive signals (e.g. "
                f"{', '.join(density.positive_matches[:3])}) that exceed a typical "
                f"{score:.0f}/10 profile. Either recalibrate toward the "
                f"{max(6, round(center)):.0f}–{min(7, round(implied_hi)):.0f} range or document "
                f"explicit weakening rationale for the current score."
            ),
            round(penalty, 3),
        )

    # Case B: strong score, weak evidence narrative
    if score >= 8.0 and density.negative_signal_strength >= 4.5 and density.positive_signal_strength < 4.0:
        penalty = _clamp((score - density.positive_signal_strength) / 5.0)
        return (
            "materially_inconsistent",
            (
                f"A {score:.0f}/10 score is not supported by the evidence profile: "
                f"material weaknesses ({', '.join(density.negative_matches[:3])}) dominate. "
                "Recommend downgrade or require additional validation before publication."
            ),
            round(penalty, 3),
        )

    if score >= 7.0 and evidence_coverage == "Limited" and missing_count >= 3:
        return (
            "materially_inconsistent",
            (
                f"Strong {score:.0f}/10 conviction coexists with limited evidence coverage "
                f"and {missing_count} open diligence gaps."
            ),
            0.5,
        )

    if supports_count >= 3 and weakens_count == 0 and score < 6.0:
        return (
            "materially_inconsistent",
            "Supporting evidence is bullish but the assigned score reads average — "
            "support and weakness lists must be reconciled.",
            0.55,
        )

    if missing_count >= 3 and supports_count >= 2 and score >= 7.0:
        return (
            "mildly_inconsistent",
            "Diligence gaps are present alongside a strong score; missing items should "
            "appear under weaknesses, not as supporting conviction.",
            0.35,
        )

    if score > implied_hi + 1.5:
        penalty = _clamp((score - implied_hi) / 5.0)
        return (
            "materially_inconsistent" if penalty >= 0.45 else "mildly_inconsistent",
            f"Score {score:.1f} sits above the narrative-implied range "
            f"({implied_lo:.1f}–{implied_hi:.1f}).",
            round(penalty, 3),
        )

    if score < implied_lo - 1.5:
        penalty = _clamp((implied_lo - score) / 5.0)
        return (
            "materially_inconsistent" if penalty >= 0.45 else "mildly_inconsistent",
            f"Score {score:.1f} sits below the narrative-implied range "
            f"({implied_lo:.1f}–{implied_hi:.1f}).",
            round(penalty, 3),
        )

    if abs(delta) > 1.0:
        return (
            "mildly_inconsistent",
            f"Score and narrative emphasis diverge modestly (implied ~{center:.1f}, assigned {score:.1f}).",
            round(_clamp(abs(delta) / 5.0), 3),
        )

    return ("consistent", "Score, evidence profile, and narrative emphasis are aligned.", 0.0)


def build_narrative_corpus(
    *,
    raw_dim: Dict[str, Any] | None,
    presentation_dim: Dict[str, Any] | None,
    scout_output: Dict[str, Any] | None,
    reviewer_output: Dict[str, Any] | None,
) -> str:
    chunks: List[str] = []
    if scout_output:
        for key in ("problem", "solution", "one_line", "why_now", "primary_thesis"):
            v = scout_output.get(key)
            if v:
                chunks.append(str(v))
    if reviewer_output:
        for key in (
            "market_reasoning",
            "product_reasoning",
            "technical_reasoning",
            "execution_reasoning",
            "defensibility_reasoning",
            "business_model_analysis",
            "competition_analysis",
            "team_analysis",
            "overall_summary",
        ):
            val = reviewer_output.get(key)
            if isinstance(val, list):
                chunks.extend(str(x) for x in val)
            elif val:
                chunks.append(str(val))
    if raw_dim:
        comps = raw_dim.get("components") or {}
        if isinstance(comps, dict):
            for comp in comps.values():
                if isinstance(comp, dict):
                    for k in ("reasoning", "evidence"):
                        if comp.get(k):
                            chunks.append(str(comp[k]))
    if presentation_dim:
        for key in ("headline", "analyst_summary", "supports", "weakens"):
            val = presentation_dim.get(key)
            if isinstance(val, list):
                chunks.extend(str(x) for x in val)
            elif val:
                chunks.append(str(val))
    return " ".join(chunks)


def audit_dimension(
    dimension_key: str,
    *,
    score: float,
    confidence: float | None,
    supports: List[str],
    weakens: List[str],
    missing_evidence: List[Dict[str, str]],
    components: List[Dict[str, Any]],
    narrative_corpus: str,
) -> DimensionConsistency:
    component_boost = sum(
        0.35 for c in components if c.get("has_evidence") and float(c.get("score", 0)) >= 7.5
    )
    density = extract_signal_density(narrative_corpus, component_boost=component_boost)
    missing_count = len(missing_evidence)
    coverage = evidence_coverage_label(confidence, missing_count)
    warning = evidence_coverage_warning(score, coverage, missing_count)
    implied_lo, implied_hi = _implied_score_range(density)

    status, explanation, penalty = _classify_consistency(
        score,
        density,
        implied_lo,
        implied_hi,
        supports_count=len(supports),
        weakens_count=len(weakens),
        missing_count=missing_count,
        evidence_coverage=coverage,
    )

    justification = build_score_justification(
        dimension_key,
        score,
        supports=supports,
        weakens=weakens,
        missing_evidence=missing_evidence,
        density=density,
        components=components,
    )
    why_not = build_why_not_higher(
        score,
        weakens=weakens,
        missing_evidence=missing_evidence,
        density=density,
    )

    return DimensionConsistency(
        dimension=dimension_key,
        score=score,
        consistency_status=status,
        consistency_explanation=explanation,
        consistency_penalty=penalty,
        signal_density=density,
        evidence_coverage=coverage,
        evidence_coverage_warning=warning,
        implied_score_range=(implied_lo, implied_hi),
        score_justification=justification,
        why_not_higher=why_not,
    )


def run_consistency_audit(
    raw_scoring: Dict[str, Any],
    presentation: Dict[str, Any],
    *,
    scout_output: Dict[str, Any] | None = None,
    reviewer_output: Dict[str, Any] | None = None,
) -> ConsistencyAudit:
    dim_audits: Dict[str, DimensionConsistency] = {}
    review_notes: List[str] = []

    pres_by_id = {d["id"]: d for d in presentation.get("dimensions", []) if isinstance(d, dict)}

    for dim_key in DIMENSION_KEYS:
        pres = pres_by_id.get(dim_key)
        if not pres:
            continue
        # Missing evidence is not a numeric 5.0. An unscored dimension has no
        # score whose narrative consistency can be audited.
        if pres.get("score") is None:
            continue
        raw_dim = raw_scoring.get(dim_key) if isinstance(raw_scoring.get(dim_key), dict) else None
        corpus = build_narrative_corpus(
            raw_dim=raw_dim,
            presentation_dim=pres,
            scout_output=scout_output,
            reviewer_output=reviewer_output,
        )
        audit = audit_dimension(
            dim_key,
            score=float(pres.get("score", 5.0)),
            confidence=raw_dim.get("confidence") if raw_dim else None,
            supports=list(pres.get("supports") or []),
            weakens=list(pres.get("weakens") or []),
            missing_evidence=list(pres.get("missing_evidence") or []),
            components=list(pres.get("components") or []),
            narrative_corpus=corpus,
        )
        dim_audits[dim_key] = audit
        note = build_analyst_review_note(audit)
        if note:
            dim_label = CANONICAL_DIMENSIONS.get(dim_key, {}).get("label", dim_key.title())
            review_notes.append(f"{dim_label}: {note}")

    statuses = [a.consistency_status for a in dim_audits.values()]
    if any(s == "materially_inconsistent" for s in statuses):
        overall: ConsistencyStatus = "materially_inconsistent"
    elif any(s == "mildly_inconsistent" for s in statuses):
        overall = "mildly_inconsistent"
    else:
        overall = "consistent"

    return ConsistencyAudit(
        dimensions=dim_audits,
        overall_status=overall,
        review_notes=review_notes,
    )


def attach_scoring_consistency_notes(
    raw_scoring: Dict[str, Any],
    presentation: Dict[str, Any],
    *,
    scout_output: Dict[str, Any] | None = None,
    reviewer_output: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Single-pass audit: attach diagnostics and soft notes without mutating scores or memo copy."""
    audit = run_consistency_audit(
        raw_scoring,
        presentation,
        scout_output=scout_output,
        reviewer_output=reviewer_output,
    )
    out = dict(presentation)
    dimensions_out: List[Dict[str, Any]] = []

    for dim in presentation.get("dimensions", []):
        if not isinstance(dim, dict):
            continue
        dim_id = dim.get("id")
        dim_audit = audit.dimensions.get(dim_id or "")
        if not dim_audit:
            dimensions_out.append(dim)
            continue

        updated = dict(dim)
        lo, hi = dim_audit.implied_score_range
        updated["evidence_coverage"] = dim_audit.evidence_coverage
        updated["score_justification"] = dim_audit.score_justification
        updated["why_not_higher"] = dim_audit.why_not_higher
        updated["consistency_status"] = dim_audit.consistency_status
        updated["consistency_explanation"] = dim_audit.consistency_explanation
        updated["consistency_penalty"] = dim_audit.consistency_penalty
        updated["positive_signal_strength"] = dim_audit.signal_density.positive_signal_strength
        updated["positive_signal_count"] = dim_audit.signal_density.positive_signal_count
        updated["negative_signal_strength"] = dim_audit.signal_density.negative_signal_strength
        updated["negative_signal_count"] = dim_audit.signal_density.negative_signal_count
        updated["implied_score_range"] = [round(lo, 1), round(hi, 1)]
        if dim_audit.evidence_coverage_warning:
            updated["evidence_coverage_warning"] = dim_audit.evidence_coverage_warning
        note = build_analyst_review_note(dim_audit)
        if note:
            updated["analyst_review_note"] = note
        dimensions_out.append(updated)

    out["dimensions"] = dimensions_out
    out["consistency_audit"] = {
        "overall_status": audit.overall_status,
        "review_notes": audit.review_notes,
    }
    return out
