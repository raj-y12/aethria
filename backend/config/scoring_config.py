"""Configuration for deterministic structured scoring."""

from __future__ import annotations

from typing import Dict


DEFAULT_SCORE = 5.0
DEBUG_SCORING = True

# ── Evidence-confidence calibration (Issue 1: thin-evidence inflation) ────────────
#
# 1A — confidence discount: a component's normalized score regresses toward
# DEFAULT_SCORE as its evidence confidence falls. At/below `floor_conf` the score
# collapses to the baseline; at/above `full_conf` it is taken at face value. Tunable
# here (and later sweepable by a validation harness) rather than hardcoded.
EVIDENCE_DISCOUNT: Dict[str, float] = {"floor_conf": 0.2, "full_conf": 0.8}

# 1B — evidence-sufficiency gate: a dimension cannot exceed `cap` unless enough of its
# components are actually evidenced (`min_completeness`) at a high enough average
# confidence (`min_avg_conf`). Stops a handful of weak signals from aggregating into a
# "Strong" dimension score; the dimension is flagged `evidence_capped` for the memo.
EVIDENCE_GATE: Dict[str, float] = {"min_completeness": 0.4, "min_avg_conf": 0.35, "cap": 6.0}

# Master switch for the Issue-1 calibration. When False (default), scores are published
# exactly as today and the new values are emitted only in shadow for comparison; flip to
# True to publish the discounted/gated scores after validating the shadow diffs.
EVIDENCE_CALIBRATION_ENABLED = False

DIMENSION_WEIGHTS: Dict[str, Dict[str, float]] = {
    "market": {
        "tam": 0.30,
        "growth_rate": 0.20,
        "urgency": 0.15,
        "timing": 0.15,
        "competition": 0.20,
    },
    "execution": {
        "traction": 0.30,
        "growth_velocity": 0.20,
        "gtm_effectiveness": 0.20,
        "team_execution": 0.15,
        "operational_velocity": 0.15,
    },
    "product": {
        "value_prop": 0.25,
        "pain_alignment": 0.25,
        "differentiation": 0.20,
        "ux": 0.15,
        "retention": 0.15,
    },
    "technical": {
        "complexity": 0.25,
        "engineering_quality": 0.20,
        "scalability": 0.20,
        "data_advantage": 0.20,
        "architecture": 0.15,
    },
    "defensibility": {
        "network_effects": 0.25,
        "switching_costs": 0.20,
        "proprietary_data": 0.20,
        "barriers": 0.20,
        "brand": 0.15,
    },
}

# Per-dimension POLICY / display weights (all five dimensions). Consumed by
# policy_compiler when compiling a fund's policy and as a fallback when a fund has not
# set explicit scoringWeights. NOTE: this is NOT the weighting used to compute the
# headline overall score — that is OVERALL_DRIVER_WEIGHTS below. Defensibility appears
# here because the policy carries a weight for every scored dimension, but it does not
# drive the overall (see OVERALL_SCORE_DIMENSIONS).
OVERALL_DIMENSION_WEIGHTS: Dict[str, float] = {
    "market": 0.20,
    "execution": 0.20,
    "product": 0.20,
    "technical": 0.20,
    "defensibility": 0.20,
}

# Dimensions that contribute to the canonical overall score. Defensibility is a
# risk/moat MODIFIER, not a driver, so it is intentionally excluded here (see the
# decision log in docs/scoring-remediation-checklist.md). This keeps the engine's
# overall identical to utils.scoring.compute_overall_score (the 4-dim mean already
# used by the partner decision), resolving the A3/A4 divergence. Defensibility is
# still scored and surfaced separately as a moat signal.
OVERALL_SCORE_DIMENSIONS = ("market", "product", "technical", "execution")

# Weighting the engine actually applies to the overall score. Defined over the driver
# dimensions ONLY and summing to 1.0, so each weight reads as its true contribution
# (0.25 = 25% of the headline). Previously the engine reused OVERALL_DIMENSION_WEIGHTS
# (0.20 each incl. a dead 0.20 for the excluded defensibility) and silently renormalized
# the four drivers to 0.25 — numerically identical, but the config lied about the actual
# weights. Keep these four in sync with OVERALL_SCORE_DIMENSIONS.
OVERALL_DRIVER_WEIGHTS: Dict[str, float] = {
    "market": 0.25,
    "product": 0.25,
    "technical": 0.25,
    "execution": 0.25,
}

# ── Component evidence classification (P3.3 / P3.4) — single source of truth ──────
#
# Every one of the 25 components is classified exactly once. This drives two things:
#   1. the reviewer prompt's evidence-anchored vs qualitative framing (reviewer/base.py)
#   2. the `qualitative` flag the scoring engine stamps on each component, so the memo
#      can distinguish an evidence-backed 8 from a qualitative 8 (audit P3.4).
# Keys are "<dimension>.<component>".
#
# - FACT_DERIVED: a label chosen against checkable evidence conditions (anchored).
# - VALUE: scored from a numeric figure by threshold (tam, growth, retention, velocity).
# - QUALITATIVE: judgment call with no objective anchor.
FACT_DERIVED_COMPONENTS: tuple[str, ...] = (
    "execution.team_execution",
    "execution.traction",
    "execution.gtm_effectiveness",
    "market.competition",
    "product.pain_alignment",
    "technical.complexity",
    "technical.scalability",
    "technical.data_advantage",
    "defensibility.network_effects",
    "defensibility.switching_costs",
    "defensibility.proprietary_data",
    "defensibility.barriers",
)

VALUE_COMPONENTS: tuple[str, ...] = (
    "market.tam",
    "market.growth_rate",
    "execution.growth_velocity",
    "product.retention",
)

QUALITATIVE_COMPONENTS: tuple[str, ...] = (
    "market.urgency",
    "market.timing",
    "execution.operational_velocity",
    "product.value_prop",
    "product.differentiation",
    "product.ux",
    "technical.engineering_quality",
    "technical.architecture",
    "defensibility.brand",
)

THRESHOLDS = {
    "tam_usd": {
        "xl": 10_000_000_000,
        "large": 3_000_000_000,
        "mid": 1_000_000_000,
        "small": 300_000_000,
    },
    "growth_pct": {"hyper": 40.0, "strong": 25.0, "healthy": 12.0, "slow": 5.0},
}

# ── Sector-relative TAM benchmarks (P6.3) ─────────────────────────────────────────
#
# An identical TAM is not equally impressive across sectors — $1B is a large market for
# vertical dev-tools but small for fintech. Each sector keyword group overrides the
# default `tam_usd` thresholds; `resolve_tam_thresholds(sector)` picks the first group
# whose keyword appears in the sector string, else the default. The absolute 1–10 scale
# is preserved (decision log: absolute anchors, sector-calibrated bands), and the chosen
# benchmark is surfaced on the memo so the comparison is transparent.
SECTOR_TAM_THRESHOLDS: Dict[str, Dict[str, Any]] = {
    "fintech": {
        "keywords": ("fintech", "financial", "payments", "banking", "insurance", "insurtech"),
        "label": "Fintech (capital-heavy; large markets expected)",
        "thresholds": {"xl": 20_000_000_000, "large": 5_000_000_000, "mid": 1_500_000_000, "small": 500_000_000},
    },
    "ai_health": {
        "keywords": ("healthcare", "health", "biotech", "bio", "medical", "pharma", "ai", "ml", "artificial intelligence"),
        "label": "AI / Healthcare (large TAM, long horizon)",
        "thresholds": {"xl": 15_000_000_000, "large": 4_000_000_000, "mid": 1_000_000_000, "small": 300_000_000},
    },
    "devtools": {
        "keywords": ("developer", "devtools", "dev tools", "infrastructure", "open source", "api", "database", "observability"),
        "label": "Dev-tools / Infra (smaller but high-margin TAM)",
        "thresholds": {"xl": 5_000_000_000, "large": 1_500_000_000, "mid": 500_000_000, "small": 150_000_000},
    },
}

_DEFAULT_TAM_BENCHMARK = {"label": "General (default benchmark)", "thresholds": THRESHOLDS["tam_usd"]}


def resolve_tam_benchmark(sector: Any) -> Dict[str, Any]:
    """Return {'label', 'thresholds'} for a sector string (P6.3). Falls back to the
    general default when the sector is empty or matches no keyword group."""
    text = str(sector or "").strip().lower()
    if text:
        for group in SECTOR_TAM_THRESHOLDS.values():
            if any(kw in text for kw in group["keywords"]):
                return {"label": group["label"], "thresholds": group["thresholds"]}
    return dict(_DEFAULT_TAM_BENCHMARK)


# ── Stage cohorts (P6.1) ──────────────────────────────────────────────────────────
#
# Scores stay absolute, but the memo states the stage cohort so maturity-dependent
# criteria are read in context ("Execution 7 — strong for Seed"). `resolve_stage_cohort`
# maps a free-text scout funding_stage to a canonical cohort + display label.
STAGE_COHORTS: Dict[str, Dict[str, Any]] = {
    "pre_seed": {"label": "Pre-seed", "keywords": ("pre-seed", "pre seed", "preseed", "idea", "prototype")},
    "seed": {"label": "Seed", "keywords": ("seed", "angel")},
    "series_a": {"label": "Series A", "keywords": ("series a", "series-a", "a round")},
    "series_b_plus": {"label": "Series B+", "keywords": ("series b", "series c", "series d", "growth", "late stage", "pre-ipo")},
}


def resolve_stage_cohort(funding_stage: Any) -> Dict[str, str]:
    """Map a free-text funding stage to a canonical cohort (P6.1). Unknown → 'unknown'."""
    text = str(funding_stage or "").strip().lower()
    if text:
        # Check the most specific cohorts first so "series b" doesn't match "seed"-style
        # substrings; iteration order here is pre_seed→seed→series_a→series_b_plus, and
        # "seed" only matches the seed group (no "series" overlap).
        for cohort, meta in STAGE_COHORTS.items():
            if any(kw in text for kw in meta["keywords"]):
                return {"cohort": cohort, "label": meta["label"]}
    return {"cohort": "unknown", "label": "Stage unknown"}

# ─── Canonical Framework (Aethria-owned, not user-editable) ───────────────────

CANONICAL_DIMENSION_KEYS = ("market", "product", "technical", "execution", "defensibility")

CANONICAL_DIMENSIONS = {
    "market": {
        "key": "market",
        "label": "Market",
        "description": "Market size, growth trajectory, competitive density, and urgency of the problem being solved.",
        "components": ["tam", "growth_rate", "urgency", "timing", "competition"],
    },
    "product": {
        "key": "product",
        "label": "Product",
        "description": "Strength of the value proposition, user pull, workflow fit, differentiation, and retention potential.",
        "components": ["value_prop", "pain_alignment", "differentiation", "ux", "retention"],
    },
    "technical": {
        "key": "technical",
        "label": "Technical",
        "description": "Technical depth, architecture maturity, engineering quality, scalability ceiling, and data advantage.",
        "components": ["complexity", "engineering_quality", "scalability", "data_advantage", "architecture"],
    },
    "execution": {
        "key": "execution",
        "label": "Execution",
        "description": "Traction evidence, growth velocity, go-to-market effectiveness, team caliber, and operational speed.",
        "components": ["traction", "growth_velocity", "gtm_effectiveness", "team_execution", "operational_velocity"],
    },
    "defensibility": {
        "key": "defensibility",
        "label": "Defensibility",
        "description": "Network effects, switching costs, proprietary data position, barriers to entry, and brand strength.",
        "components": ["network_effects", "switching_costs", "proprietary_data", "barriers", "brand"],
    },
}

CANONICAL_SCORE_BANDS = {
    "1-2": {
        "range": [1, 2],
        "label": "Structurally Weak",
        "description": "Fundamental weaknesses that are unlikely to be overcome. Not a viable venture opportunity.",
    },
    "3-4": {
        "range": [3, 4],
        "label": "Below Threshold",
        "description": "Potential business but unlikely to produce venture-scale outcomes. Significant gaps remain.",
    },
    "5-6": {
        "range": [5, 6],
        "label": "Promising, Incomplete",
        "description": "Promising opportunity with incomplete validation. Further diligence could materially change the assessment.",
    },
    "7-8": {
        "range": [7, 8],
        "label": "Strong",
        "description": "Strong venture-scale opportunity supported by evidence. Key signals are present and validated.",
    },
    "9-10": {
        "range": [9, 10],
        "label": "Exceptional",
        "description": "Exceptional opportunity with multiple reinforcing signals. Rare conviction level.",
    },
}

DIMENSION_SCORE_BANDS = {
    "market": {
        1: "No identifiable market. Problem is not validated or budget does not exist.",
        2: "Extremely niche market with no growth trajectory. Insufficient for venture returns.",
        3: "Small addressable market or declining category. Growth rate below replacement.",
        4: "Addressable market exists but TAM under $1B or growth is flat. Competitive density is high.",
        5: "Market is real and growing but TAM validation is incomplete. Budget exists but urgency is unclear.",
        6: "Growing market with validated demand. TAM appears sufficient but independent verification is missing.",
        7: "Large, expanding market with clear buyer urgency. Multiple data points support TAM above $3B.",
        8: "Strong market with verified TAM, healthy growth rate, and clear category tailwinds.",
        9: "Exceptional market with verified TAM above $10B, strong growth, and urgent buyer need.",
        10: "Generational market opportunity. Category-defining tailwinds with massive, verified TAM.",
    },
    "product": {
        1: "No product insight. Solution does not address a real workflow or need.",
        2: "Product exists but has no differentiation and no evidence of user pull.",
        3: "Product addresses a real problem but value proposition is unclear. No retention evidence.",
        4: "Functional product with some user interest but weak differentiation from alternatives.",
        5: "Product solves a real problem with some user pull. Differentiation is emerging but unproven.",
        6: "Clear value proposition with early user traction. Differentiation is present but competitive moat is thin.",
        7: "Strong product-market signal with demonstrated user pull and clear differentiation.",
        8: "Compelling product with strong retention signals and defensible differentiation.",
        9: "Exceptional product insight with deep user love, high retention, and unique workflow integration.",
        10: "Category-defining product. Users cannot imagine returning to the previous solution.",
    },
    "technical": {
        1: "No technical depth. Implementation is trivial and easily replicated.",
        2: "Minimal technical complexity. No architecture advantage or engineering differentiation.",
        3: "Basic implementation with limited scalability. Technical debt is likely high.",
        4: "Functional but unremarkable technical approach. Scalability concerns exist.",
        5: "Competent engineering with some technical depth. Scalability path is plausible but unproven.",
        6: "Solid technical foundation with clear scalability path. Some engineering differentiation.",
        7: "Strong technical implementation with proven scalability and meaningful engineering edge.",
        8: "Excellent engineering quality with defensible technical architecture and data advantage.",
        9: "Deep technical moat with proprietary systems, strong data advantage, and elite engineering.",
        10: "World-class technical achievement. Architecture creates compounding advantage over time.",
    },
    "execution": {
        1: "No evidence of execution capability. Team background is unknown or misaligned.",
        2: "Team exists but has no relevant domain experience and no traction evidence.",
        3: "Some team credibility but no meaningful traction. Execution speed is unclear.",
        4: "Team has relevant background but traction is minimal. Go-to-market is untested.",
        5: "Credible team with early traction signals. Execution velocity is moderate.",
        6: "Strong team with demonstrated early traction. Go-to-market channels are identified.",
        7: "Proven execution with meaningful traction metrics and strong operational velocity.",
        8: "Exceptional execution with rapid growth, proven GTM, and high-caliber team.",
        9: "Elite team with exceptional traction trajectory and repeatable go-to-market engine.",
        10: "World-class founders with breakthrough traction. Execution is a compounding advantage.",
    },
    "defensibility": {
        1: "No defensibility. Any competitor could replicate the offering immediately.",
        2: "Minimal barriers to entry. No switching costs, network effects, or data advantage.",
        3: "Some barriers exist but they are easily overcome. Switching costs are low.",
        4: "Emerging defensibility through early data or distribution but moat is thin.",
        5: "Moderate defensibility with some switching costs or early network effects.",
        6: "Clear defensibility path with meaningful switching costs or growing data advantage.",
        7: "Strong moat with multiple defensibility layers. Switching costs are significant.",
        8: "Deep moat with strong network effects, high switching costs, and proprietary data.",
        9: "Exceptional defensibility with compounding network effects and deep platform lock-in.",
        10: "Near-impregnable competitive position. Multiple reinforcing moats create winner-take-most dynamics.",
    },
}

MISSING_EVIDENCE_ITEMS = {
    "market": [
        "Verified TAM estimate from independent source",
        "Market growth rate with cited data",
        "Competitive landscape mapping",
        "Customer budget validation",
        "Category growth trajectory",
    ],
    "product": [
        "User retention or engagement metrics",
        "Customer interviews or NPS data",
        "Competitive feature comparison",
        "Pricing validation with buyers",
        "Product usage frequency data",
    ],
    "technical": [
        "Architecture scalability evidence",
        "Technical team background verification",
        "Infrastructure cost trajectory",
        "Security and reliability track record",
        "Technical differentiation specifics",
    ],
    "execution": [
        "Revenue or ARR figures",
        "Customer count and growth rate",
        "Founder background verification",
        "Go-to-market channel performance",
        "Operational velocity indicators",
    ],
    "defensibility": [
        "Network effect quantification",
        "Switching cost analysis",
        "Proprietary data asset inventory",
        "Patent or IP status",
        "Distribution advantage evidence",
    ],
}

CONFIDENCE_INTERPRETATIONS = {
    "high": {
        "threshold": 0.7,
        "label": "High",
        "interpretation": "Evidence is sufficient to support the assigned score with reasonable certainty.",
    },
    "medium": {
        "threshold": 0.45,
        "label": "Medium",
        "interpretation": "Evidence supports the general direction but key data points are missing. Score could shift materially with additional diligence.",
    },
    "low": {
        "threshold": 0.0,
        "label": "Low",
        "interpretation": "Evidence is insufficient to support a strong conclusion. Additional diligence could materially change the outcome in either direction.",
    },
}


def get_confidence_level(confidence: float) -> str:
    """Return 'high', 'medium', or 'low' for a confidence value."""
    if confidence >= CONFIDENCE_INTERPRETATIONS["high"]["threshold"]:
        return "high"
    if confidence >= CONFIDENCE_INTERPRETATIONS["medium"]["threshold"]:
        return "medium"
    return "low"


def get_score_band_description(dimension: str, score: float) -> str:
    """Return the dimension-specific description for a score value."""
    bands = DIMENSION_SCORE_BANDS.get(dimension, {})
    rounded = max(1, min(10, round(score)))
    return bands.get(rounded, CANONICAL_SCORE_BANDS.get(f"{rounded}-{rounded}", {}).get("description", ""))


def get_missing_evidence_for_dimension(dimension: str) -> list:
    """Return the canonical missing evidence items for a dimension."""
    return list(MISSING_EVIDENCE_ITEMS.get(dimension, []))
