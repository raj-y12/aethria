"""Presentation serializer: transforms raw scoring output into investor-facing DTO.

This layer is the ONLY interface the frontend should consume for scoring data.
It never exposes scoring mechanics, weights, policy metadata, extraction logic,
or debug language. Output reads like analyst judgement.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from config.scoring_config import (
    CANONICAL_DIMENSIONS,
    CONFIDENCE_INTERPRETATIONS,
    DIMENSION_SCORE_BANDS,
    MISSING_EVIDENCE_ITEMS,
    get_confidence_level,
)
from services.scoring.consistency_layer import attach_scoring_consistency_notes


# ─── Evidence Confidence: describes quality of underlying evidence ────────────
# Separate from conviction/score. Never conflicts with the investment assessment.
EVIDENCE_CONFIDENCE_LABELS = {
    "extensive": {"min": 0.75, "label": "Extensive", "tooltip": "Multiple independent evidence sources corroborate the assessment."},
    "strong": {"min": 0.50, "label": "Strong", "tooltip": "Sufficient evidence is available to support the assessment with reasonable certainty."},
    "moderate": {"min": 0.25, "label": "Moderate", "tooltip": "Some evidence supports the direction but important data points are missing."},
    "limited": {"min": 0.00, "label": "Limited", "tooltip": "Limited evidence was available. Key data points remain unverified."},
}

SCORE_BAND_LABELS = {
    (1, 2): "Structurally Weak",
    (3, 4): "Below Threshold",
    (5, 6): "Promising, Incomplete",
    (7, 8): "Strong",
    (9, 10): "Exceptional",
}

COMPONENT_LABELS: Dict[str, str] = {
    "architecture": "Architecture",
    "barriers": "Barriers to entry",
    "brand": "Brand leverage",
    "competition": "Competitive pressure",
    "complexity": "Technical complexity",
    "data_advantage": "Data advantage",
    "differentiation": "Differentiation",
    "engineering_quality": "Engineering quality",
    "growth_rate": "Growth rate",
    "growth_velocity": "Growth velocity",
    "gtm_effectiveness": "Go-to-market effectiveness",
    "network_effects": "Network effects",
    "operational_velocity": "Operational velocity",
    "pain_alignment": "Pain alignment",
    "proprietary_data": "Proprietary data",
    "retention": "Retention",
    "scalability": "Scalability",
    "switching_costs": "Switching costs",
    "tam": "Market size",
    "team_execution": "Team execution",
    "timing": "Timing",
    "traction": "Traction",
    "urgency": "Customer urgency",
    "ux": "User experience",
    "value_prop": "Value proposition",
}

MISSING_EVIDENCE_EXPLANATIONS: Dict[str, Dict[str, str]] = {
    "market": {
        "tam": "No independently sourced TAM estimate was identified.",
        "growth_rate": "No market CAGR or category growth data was identified.",
        "urgency": "Customer urgency level could not be independently assessed.",
        "timing": "No clear evidence of favorable market timing was established.",
        "competition": "Competitive landscape depth could not be fully mapped.",
    },
    "product": {
        "value_prop": "Value proposition strength could not be independently validated.",
        "pain_alignment": "Customer pain severity was not quantified or validated.",
        "differentiation": "Differentiation from alternatives was not clearly established.",
        "ux": "No user experience quality evidence was identified.",
        "retention": "No retention or engagement metrics were disclosed.",
    },
    "technical": {
        "complexity": "Technical complexity depth could not be assessed.",
        "engineering_quality": "Engineering team quality was not independently verified.",
        "scalability": "Scalability evidence or architecture review was not available.",
        "data_advantage": "No proprietary data asset was identified or quantified.",
        "architecture": "Architecture maturity could not be evaluated.",
    },
    "execution": {
        "traction": "No traction metrics (revenue, users, pilots) were disclosed.",
        "growth_velocity": "Growth rate could not be independently verified.",
        "gtm_effectiveness": "Go-to-market channel performance was not demonstrated.",
        "team_execution": "Team execution track record was not verified.",
        "operational_velocity": "Operational speed indicators were not available.",
    },
    "defensibility": {
        "network_effects": "Network effect presence or strength was not quantified.",
        "switching_costs": "Switching cost magnitude was not assessed.",
        "proprietary_data": "Proprietary data position was not established.",
        "barriers": "Barrier-to-entry strength could not be evaluated.",
        "brand": "Brand leverage or recognition could not be assessed.",
    },
}

_INTERNAL_PATTERNS = [
    re.compile(r"^Computed from\b", re.IGNORECASE),
    re.compile(r"\bfrom scout payload\b", re.IGNORECASE),
    re.compile(r"\bfrom scout narrative\b", re.IGNORECASE),
    re.compile(r"\bfrom reviewer\b", re.IGNORECASE),
    re.compile(r"\bGrowth inferred from\b", re.IGNORECASE),
    re.compile(r"\bTAM from scout\b", re.IGNORECASE),
    re.compile(r"\bextracted? from\b", re.IGNORECASE),
    re.compile(r"\bpolicy[_\s]?hash\b", re.IGNORECASE),
    re.compile(r"\bpolicy[_\s]?version\b", re.IGNORECASE),
    re.compile(r"\bsource_components?\b", re.IGNORECASE),
    re.compile(r"\bnormalize_", re.IGNORECASE),
    re.compile(r"\b_extract_", re.IGNORECASE),
    re.compile(r"\bclassify_", re.IGNORECASE),
    re.compile(r"\braw extraction\b", re.IGNORECASE),
    re.compile(r"\bMissing-data rule:", re.IGNORECASE),
    re.compile(r"\bsignal pipeline\b", re.IGNORECASE),
    re.compile(r"\bscoring_engine\b", re.IGNORECASE),
    re.compile(r"\baggregation_layer\b", re.IGNORECASE),
    re.compile(r"\bnormalization_layer\b", re.IGNORECASE),
    re.compile(r"\bextraction_layer\b", re.IGNORECASE),
    re.compile(r"\bpolicy_compiler\b", re.IGNORECASE),
    re.compile(r"\bWeight \d+%", re.IGNORECASE),
    re.compile(r"\bEvidence partial\b", re.IGNORECASE),
    re.compile(r"\bEvidence: missing\b", re.IGNORECASE),
    re.compile(r"\bEvidence: complete\b", re.IGNORECASE),
    re.compile(r"\bStructured scoring\b", re.IGNORECASE),
    re.compile(r"\bNormalization\b", re.IGNORECASE),
    re.compile(r"\bAggregation\b", re.IGNORECASE),
    re.compile(r"\bExtraction\b", re.IGNORECASE),
    re.compile(r"\bRule engine\b", re.IGNORECASE),
    re.compile(r"\bPolicy inputs\b", re.IGNORECASE),
    re.compile(r"\bSource components\b", re.IGNORECASE),
    re.compile(r"\bComponent weights\b", re.IGNORECASE),
]

_MISSING_MARKER_RE = re.compile(r"^\s*\[?\s*missing(?::[^\]]*)?\]?\s*$", re.IGNORECASE)

_GENERIC_MISSING_PATTERNS = re.compile(
    r"(Evidence not available|Diligence required to establish baseline|No rationale recorded)",
    re.IGNORECASE,
)


def _sanitize_text(text: str | None) -> str | None:
    if not text or not isinstance(text, str):
        return None
    trimmed = text.strip()
    if not trimmed:
        return None
    for pattern in _INTERNAL_PATTERNS:
        if pattern.search(trimmed):
            sentences = re.split(r"(?<=[.!?])\s+", trimmed)
            clean = [s for s in sentences if not any(p.search(s) for p in _INTERNAL_PATTERNS)]
            return " ".join(clean).strip() or None
    return trimmed


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        text = value.strip()
        return not text or bool(_MISSING_MARKER_RE.match(text))
    return False


def _evidence_confidence(confidence: float | None) -> Dict[str, str]:
    """Map raw confidence to evidence quality labels (never conflicts with score conviction)."""
    if confidence is None:
        return {"label": "Limited", "tooltip": "Evidence quality could not be determined."}
    c = max(0.0, min(1.0, float(confidence)))
    if c >= 0.75:
        return EVIDENCE_CONFIDENCE_LABELS["extensive"]
    if c >= 0.50:
        return EVIDENCE_CONFIDENCE_LABELS["strong"]
    if c >= 0.25:
        return EVIDENCE_CONFIDENCE_LABELS["moderate"]
    return EVIDENCE_CONFIDENCE_LABELS["limited"]


def _score_band(score: float) -> str:
    rounded = max(1, min(10, round(score)))
    for (lo, hi), label in SCORE_BAND_LABELS.items():
        if lo <= rounded <= hi:
            return label
    return "Promising, Incomplete"


def _component_has_evidence(comp: Dict[str, Any]) -> bool:
    for key in ("value", "label"):
        raw = comp.get(key)
        if raw is None:
            continue
        if isinstance(raw, str):
            text = raw.strip()
            if text and not _MISSING_MARKER_RE.match(text):
                return True
        elif raw not in ("", [], {}):
            return True
    return False


def _build_component_presentation(
    name: str, comp: Dict[str, Any], dimension_key: str
) -> Dict[str, Any]:
    label = COMPONENT_LABELS.get(name, name.replace("_", " ").title())
    score = max(0.0, min(10.0, float(comp.get("score", 5.0))))
    has_evidence = _component_has_evidence(comp)
    band = _score_band(score)
    reasoning = _sanitize_text(comp.get("reasoning"))
    evidence_text = _sanitize_text(comp.get("evidence"))

    if not has_evidence:
        explanation = MISSING_EVIDENCE_EXPLANATIONS.get(dimension_key, {}).get(name)
        interpretation = explanation or f"{label} could not be assessed from available evidence."
    elif reasoning and not _GENERIC_MISSING_PATTERNS.search(reasoning):
        interpretation = reasoning
    elif evidence_text:
        interpretation = evidence_text
    else:
        interpretation = f"{label} assessed from available evidence."

    return {
        "id": name,
        "label": label,
        "score": round(score, 1),
        "band": band,
        "has_evidence": has_evidence,
        "interpretation": interpretation,
    }


def _deduplicate_text(texts: List[str], exclude_set: set[str] | None = None) -> List[str]:
    """Remove duplicate or near-duplicate strings from a list.

    Compares normalized (lowercase, stripped punctuation) forms to detect repetition.
    Also removes items that overlap with the exclude_set.
    """
    exclude = {_normalize_for_comparison(t) for t in (exclude_set or set())}
    seen: set[str] = set()
    output: List[str] = []
    for text in texts:
        normalized = _normalize_for_comparison(text)
        if normalized in seen or normalized in exclude:
            continue
        if any(_text_overlap(normalized, s) > 0.7 for s in seen):
            continue
        if any(_text_overlap(normalized, s) > 0.7 for s in exclude):
            continue
        seen.add(normalized)
        output.append(text)
    return output


def _normalize_for_comparison(text: str) -> str:
    return re.sub(r"[^\w\s]", "", text.lower()).strip()


def _text_overlap(a: str, b: str) -> float:
    """Return ratio of shared words between two normalized strings."""
    if not a or not b:
        return 0.0
    words_a = set(a.split())
    words_b = set(b.split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    return len(intersection) / min(len(words_a), len(words_b))


def _build_supports(
    components: List[Dict[str, Any]],
    headline: str,
) -> List[str]:
    """Extract concise factors that support conviction. Non-repetitive, high-signal."""
    raw_supports = []
    for comp in sorted(components, key=lambda c: c["score"], reverse=True):
        if comp["has_evidence"] and comp["score"] >= 7.0:
            raw_supports.append(comp["interpretation"])
    return _deduplicate_text(raw_supports[:5], exclude_set={headline})[:4]


def _build_weakens(
    components: List[Dict[str, Any]],
    missing_evidence: List[Dict[str, str]],
    weaknesses: List[str],
) -> List[str]:
    """Extract real factors that weaken conviction.

    Never returns empty when missing evidence or low-scoring components exist.
    Only shows 'no weakness' fallback when genuinely no weak signals AND no gaps.
    """
    weakens: List[str] = []

    for comp in sorted(components, key=lambda c: c["score"]):
        if comp["has_evidence"] and comp["score"] < 5.0:
            weakens.append(f"{comp['label']} evidence is weak or concerning")

    for comp in sorted(components, key=lambda c: c["score"]):
        if comp["has_evidence"] and 5.0 <= comp["score"] < 7.0 and len(weakens) < 3:
            weakens.append(f"{comp['label']} remains unproven at scale")

    for item in missing_evidence:
        if len(weakens) >= 5:
            break
        label = item["label"]
        verb = "have" if label.lower().endswith("s") else "has"
        weakens.append(f"{label} {verb} not been independently verified")

    for w in weaknesses:
        if len(weakens) >= 5:
            break
        cleaned = _sanitize_text(w)
        if cleaned:
            weakens.append(cleaned)

    return _deduplicate_text(weakens)[:5]


def _build_missing_evidence(
    components: List[Dict[str, Any]], dimension_key: str
) -> List[Dict[str, str]]:
    missing = []
    for comp in components:
        if not comp["has_evidence"]:
            explanation = MISSING_EVIDENCE_EXPLANATIONS.get(dimension_key, {}).get(
                comp["id"],
                f"No evidence was identified for {comp['label'].lower()}.",
            )
            missing.append({"label": comp["label"], "explanation": explanation})
    return missing


def _build_diligence_actions(
    missing_evidence: List[Dict[str, str]],
    weakens: List[str],
    dimension_key: str,
    components: List[Dict[str, Any]],
) -> List[str]:
    """Generate 2-5 startup-specific diligence actions.

    Actions reference the actual evidence gaps, component context, and
    domain-specific investigation steps rather than generic templates.
    """
    actions: List[str] = []

    _SPECIFIC_DILIGENCE_TEMPLATES: Dict[str, Dict[str, str]] = {
        "market": {
            "tam": "Verify addressable market size with independent industry sizing or analyst reports",
            "growth_rate": "Confirm category growth trajectory through market research or public data",
            "urgency": "Validate buyer urgency through customer interviews or win/loss analysis",
            "timing": "Assess whether market timing advantages are durable or transient",
            "competition": "Map competitive landscape depth including adjacent and emerging players",
        },
        "product": {
            "value_prop": "Test value proposition with target buyers through structured discovery",
            "pain_alignment": "Quantify the cost of the problem being solved for target customers",
            "differentiation": "Conduct competitive feature analysis to validate differentiation claims",
            "ux": "Assess product usability through user testing or workflow observation",
            "retention": "Obtain cohort-level retention data or proxy engagement metrics",
        },
        "technical": {
            "complexity": "Evaluate technical depth through architecture review or expert assessment",
            "engineering_quality": "Verify engineering team caliber through background checks and code review",
            "scalability": "Stress-test scalability claims with infrastructure cost projections",
            "data_advantage": "Quantify proprietary data assets and assess defensibility of data position",
            "architecture": "Review system architecture for extensibility and technical debt levels",
        },
        "execution": {
            "traction": "Verify claimed traction metrics through customer references or data room access",
            "growth_velocity": "Confirm growth rate trajectory with month-over-month data",
            "gtm_effectiveness": "Evaluate go-to-market repeatability through pipeline analysis",
            "team_execution": "Verify founding team track record through reference checks",
            "operational_velocity": "Assess operational cadence through milestone achievement history",
        },
        "defensibility": {
            "network_effects": "Evaluate whether network effects are present and measurable at current scale",
            "switching_costs": "Assess switching cost magnitude through customer workflow integration depth",
            "proprietary_data": "Determine whether proprietary data compounds over time and is defensible",
            "barriers": "Identify specific barriers that prevent fast-followers from replicating",
            "brand": "Assess brand recognition and trust level within the target market",
        },
    }

    dim_templates = _SPECIFIC_DILIGENCE_TEMPLATES.get(dimension_key, {})

    for item in missing_evidence[:3]:
        comp_id = next(
            (c["id"] for c in components if c["label"] == item["label"]),
            None,
        )
        template = dim_templates.get(comp_id or "", "") if comp_id else ""
        if template:
            actions.append(template)
        else:
            actions.append(f"Investigate {item['label'].lower()} through independent due diligence")

    for w in weakens[:2]:
        if len(actions) >= 5:
            break
        if "unproven" in w.lower():
            label = w.split(" remains")[0] if " remains" in w else w.split(" has")[0]
            actions.append(f"Validate {label.lower()} through longer-term observation or references")
        elif "not been" in w.lower() or "unverified" in w.lower():
            label = w.split(" has")[0] if " has" in w else w.rstrip(".")
            actions.append(f"Obtain independent verification of {label.lower()}")

    return _deduplicate_text(actions)[:5]


def _build_headline(
    dimension_key: str,
    score: float,
    supports: List[str],
    missing_evidence: List[Dict[str, str]],
    components: List[Dict[str, Any]],
) -> str:
    """Single-sentence analyst headline. Concise, thematic, never repeats support text verbatim."""
    dim_label = CANONICAL_DIMENSIONS.get(dimension_key, {}).get("label", dimension_key.title())
    band = _score_band(score)

    strong_labels = [c["label"] for c in components if c["has_evidence"] and c["score"] >= 7.0]

    if supports and missing_evidence:
        theme = _thematic_summary(strong_labels, dim_label)
        gap = missing_evidence[0]["label"].lower()
        return f"{theme} support conviction, but key {gap} evidence remains incomplete."
    if supports:
        theme = _thematic_summary(strong_labels, dim_label)
        return f"{theme} support {dim_label.lower()} conviction."
    if missing_evidence:
        return f"{dim_label} assessment is constrained by insufficient evidence across key criteria."
    return f"{dim_label} reads as {band.lower()} on available evidence, with limited corroboration so far."


def _thematic_summary(strong_labels: List[str], dim_label: str) -> str:
    """Build a concise thematic phrase from component labels (not their reasoning)."""
    if len(strong_labels) >= 3:
        return f"Strong {strong_labels[0].lower()}, {strong_labels[1].lower()} and {strong_labels[2].lower()} signals"
    if len(strong_labels) == 2:
        return f"Strong {strong_labels[0].lower()} and {strong_labels[1].lower()} signals"
    if len(strong_labels) == 1:
        return f"Strong {strong_labels[0].lower()} signal"
    return f"Available {dim_label.lower()} signals"


def _build_score_interpretation(dimension_key: str, score: float) -> str:
    rounded = max(1, min(10, round(score)))
    bands = DIMENSION_SCORE_BANDS.get(dimension_key, {})
    band_text = bands.get(rounded, "")
    return f"{rounded}/10 — {band_text}" if band_text else f"{rounded}/10"


def _build_analyst_summary(
    dimension_key: str,
    components: List[Dict[str, Any]],
    weakens: List[str],
    missing_evidence: List[Dict[str, str]],
) -> str:
    """2-3 sentence analyst summary using component labels (not reasoning) to avoid repetition."""
    parts: List[str] = []

    strong_labels = [c["label"].lower() for c in components if c["has_evidence"] and c["score"] >= 7.0]
    if strong_labels:
        if len(strong_labels) >= 2:
            parts.append(f"Conviction is primarily supported by {strong_labels[0]} and {strong_labels[1]} evidence.")
        else:
            parts.append(f"Conviction is primarily supported by {strong_labels[0]} evidence.")

    if weakens:
        parts.append(f"Key limitation: {weakens[0].rstrip('.')}.")
    elif missing_evidence:
        gaps = [m["label"].lower() for m in missing_evidence[:2]]
        parts.append(f"Assessment is limited by missing {' and '.join(gaps)} data.")

    if missing_evidence:
        strengthen_item = missing_evidence[0]["label"].lower()
        parts.append(f"Independent validation of {strengthen_item} would materially strengthen the case.")

    if not parts:
        parts.append("Assessment reflects available evidence. Further diligence would increase certainty.")

    return " ".join(parts)


def serialize_scoring_presentation(
    raw_scoring: Dict[str, Any],
    *,
    startup_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Transform raw scoring engine output into the investor-facing presentation DTO.

    Args:
        raw_scoring: Raw structured scoring output from the scoring engine.
        startup_context: Optional startup metadata (name, sector, product type)
                        for generating startup-specific diligence actions.
    """
    raw_overall_score = raw_scoring.get("overall_score")
    overall_score = (
        float(raw_overall_score) if raw_overall_score is not None else None
    )
    overall_confidence = raw_scoring.get("overall_confidence")
    if overall_confidence is not None:
        overall_confidence = float(overall_confidence)

    dimensions_output: List[Dict[str, Any]] = []
    dimension_keys = ("market", "product", "technical", "execution", "defensibility")

    for dim_key in dimension_keys:
        dim_data = raw_scoring.get(dim_key)
        if not isinstance(dim_data, dict):
            continue

        raw_dim_score = dim_data.get("score")
        dim_score = float(raw_dim_score) if raw_dim_score is not None else None
        dim_confidence = dim_data.get("confidence")
        if dim_confidence is not None:
            dim_confidence = float(dim_confidence)

        raw_components = dim_data.get("components", {})
        components_presentation = []
        for comp_name, comp_data in raw_components.items():
            if not isinstance(comp_data, dict):
                continue
            components_presentation.append(
                _build_component_presentation(comp_name, comp_data, dim_key)
            )

        components_presentation.sort(key=lambda c: (-1 if c["has_evidence"] else 1, -c["score"]))

        missing_evidence = _build_missing_evidence(components_presentation, dim_key)

        raw_weaknesses: List[str] = []
        criteria = dim_data.get("criteria", {})
        if isinstance(criteria, dict):
            for crit in criteria.values():
                if isinstance(crit, dict):
                    reasoning = crit.get("reasoning", "")
                    if reasoning and "Concerns:" in reasoning:
                        concern_part = reasoning.split("Concerns:")[-1].strip()
                        raw_weaknesses.append(concern_part)

        if dim_score is None or dim_data.get("unscored"):
            supports = []
            dim_label = CANONICAL_DIMENSIONS.get(dim_key, {}).get(
                "label", dim_key.title()
            )
            headline = f"{dim_label} is not scored: grounded evidence is insufficient."
        else:
            headline_draft = _build_headline(
                dim_key, dim_score, [], missing_evidence, components_presentation
            )
            supports = _build_supports(components_presentation, headline_draft)
            headline = _build_headline(
                dim_key,
                dim_score,
                supports,
                missing_evidence,
                components_presentation,
            )

        weakens = _build_weakens(components_presentation, missing_evidence, raw_weaknesses)
        diligence_actions = _build_diligence_actions(
            missing_evidence, weakens, dim_key, components_presentation,
        )
        score_interpretation = (
            "Not scored until grounded evidence is available."
            if dim_score is None
            else _build_score_interpretation(dim_key, dim_score)
        )
        analyst_summary = _build_analyst_summary(dim_key, components_presentation, weakens, missing_evidence)
        conf_info = _evidence_confidence(dim_confidence)

        dim_label = CANONICAL_DIMENSIONS.get(dim_key, {}).get("label", dim_key.title())

        dimensions_output.append({
            "id": dim_key,
            "label": dim_label,
            "score": None if dim_score is None else round(dim_score, 1),
            "band": "Not scored" if dim_score is None else _score_band(dim_score),
            "headline": headline,
            "score_interpretation": score_interpretation,
            "analyst_summary": analyst_summary,
            "supports": supports,
            "weakens": weakens,
            "missing_evidence": missing_evidence,
            "diligence_actions": diligence_actions,
            "confidence_label": conf_info["label"],
            "confidence_tooltip": conf_info["tooltip"],
            "components": components_presentation,
        })

    overall_conf_info = _evidence_confidence(overall_confidence)

    presentation = {
        "overall_score": None if overall_score is None else round(overall_score, 1),
        "overall_band": (
            "Not scored" if overall_score is None else _score_band(overall_score)
        ),
        "confidence_label": overall_conf_info["label"],
        "confidence_tooltip": overall_conf_info["tooltip"],
        "dimensions": dimensions_output,
    }

    scout_ctx = None
    reviewer_ctx = None
    if startup_context:
        scout_ctx = startup_context.get("scout") or {
            k: startup_context[k]
            for k in ("problem", "solution", "one_line", "why_now", "primary_thesis", "est_tam")
            if k in startup_context
        }
        reviewer_ctx = startup_context.get("reviewer_output") or startup_context.get("review")

    return attach_scoring_consistency_notes(
        raw_scoring,
        presentation,
        scout_output=scout_ctx,
        reviewer_output=reviewer_ctx,
    )
