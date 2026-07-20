"""Complete, immutable Partner rules authority contract."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StringConstraints,
    model_validator,
)

from evaluation_v2.models import DecisionSafetyPolicy


NonEmptyString = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1),
]
Score = Annotated[StrictInt | StrictFloat, Field(ge=0, le=10)]
Probability = Annotated[StrictInt | StrictFloat, Field(ge=0, le=1)]
PositiveProbability = Annotated[StrictInt | StrictFloat, Field(gt=0, le=1)]
Conviction = Annotated[StrictInt, Field(ge=1, le=10)]


class StrictRulesModel(BaseModel):
    """Forbid silent schema drift and make loaded policy immutable."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
    )


class MandateFitRules(StrictRulesModel):
    comment: NonEmptyString | None = Field(default=None, alias="_comment")
    enabled: StrictBool
    strong_fit_min: Probability
    partial_fit_min: Probability
    weak_fit_min: Probability
    gate_invest_below: Probability
    held_recommendation: Literal["MONITOR", "PASS"]
    held_next_action: NonEmptyString
    low_confidence_max: Probability

    @model_validator(mode="after")
    def validate_fit_bands(self) -> "MandateFitRules":
        if not (
            self.gate_invest_below
            <= self.weak_fit_min
            < self.partial_fit_min
            < self.strong_fit_min
        ):
            raise ValueError(
                "mandate fit bands must satisfy gate <= weak < partial < strong"
            )
        return self


class QualityLabels(StrictRulesModel):
    strong: NonEmptyString = Field(alias="STRONG")
    medium: NonEmptyString = Field(alias="MEDIUM")
    weak: NonEmptyString = Field(alias="WEAK")

    def for_verdict(self, verdict: str) -> str:
        try:
            return {
                "STRONG": self.strong,
                "MEDIUM": self.medium,
                "WEAK": self.weak,
            }[verdict]
        except KeyError as exc:
            raise ValueError(f"Unsupported Partner verdict: {verdict!r}") from exc


class WeakVerdictRule(StrictRulesModel):
    decision: Literal["NO"]
    conviction_level: Conviction
    next_action: NonEmptyString
    human_review_required: StrictBool


class StrongVerdictRule(StrictRulesModel):
    min_avg_for_yes: Score
    decision_yes: Literal["YES"]
    conviction_level_yes: Conviction
    human_review_required_yes: StrictBool
    decision_below_strong_yes_bar: Literal["MAYBE", "NO"]
    conviction_level_below_strong_yes_bar: Conviction
    next_action_below_strong_yes_bar: NonEmptyString
    human_review_required_below_strong_yes_bar: StrictBool


class MediumVerdictRule(StrictRulesModel):
    min_avg_for_maybe: Score
    min_avg_for_borderline: Score
    decision_maybe: Literal["MAYBE", "NO"]
    conviction_level_maybe: Conviction
    conviction_level_borderline: Conviction
    decision_borderline_no_llm: Literal["MAYBE", "NO"]
    next_action_borderline: NonEmptyString


class VerdictRules(StrictRulesModel):
    weak: WeakVerdictRule = Field(alias="WEAK")
    strong: StrongVerdictRule = Field(alias="STRONG")
    medium: MediumVerdictRule = Field(alias="MEDIUM")


class BoundarySemantics(StrictRulesModel):
    advance: Literal["greater_than_or_equal"]
    passed: Literal["less_than"] = Field(alias="pass")


class ScoreThresholds(StrictRulesModel):
    min_avg_pass: Score
    min_avg_strong_yes: Score
    min_avg_medium_maybe: Score
    min_avg_borderline_low: Score
    max_avg_borderline_high: Score
    grey_zone_min: Score
    grey_zone_max: Score
    minimum_scored_weight: PositiveProbability
    boundary_semantics: BoundarySemantics

    @model_validator(mode="after")
    def validate_threshold_order(self) -> "ScoreThresholds":
        if not self.min_avg_pass < self.min_avg_strong_yes:
            raise ValueError("min_avg_pass must be below min_avg_strong_yes")
        if not (
            self.min_avg_pass
            <= self.min_avg_medium_maybe
            <= self.min_avg_strong_yes
        ):
            raise ValueError(
                "min_avg_medium_maybe must be between pass and advance thresholds"
            )
        if not (
            self.min_avg_pass
            <= self.min_avg_borderline_low
            < self.max_avg_borderline_high
            <= self.min_avg_strong_yes
        ):
            raise ValueError(
                "borderline thresholds must be ordered within pass and advance"
            )
        if not (
            self.min_avg_pass
            <= self.grey_zone_min
            <= self.grey_zone_max
            <= self.min_avg_strong_yes
        ):
            raise ValueError(
                "grey-zone thresholds must be ordered within pass and advance"
            )
        return self


class ContradictoryScores(StrictRulesModel):
    min_gap: Annotated[StrictInt | StrictFloat, Field(gt=0, le=10)]
    high_threshold: Score
    low_threshold: Score

    @model_validator(mode="after")
    def validate_threshold_order(self) -> "ContradictoryScores":
        if self.high_threshold <= self.low_threshold:
            raise ValueError("high_threshold must be above low_threshold")
        return self


class NextActions(StrictRulesModel):
    critical_risks: NonEmptyString
    low_scores: NonEmptyString
    default_no: NonEmptyString
    request_cap_table: NonEmptyString
    request_cap_table_and_review: NonEmptyString
    monitor: NonEmptyString
    human_review_monitor: NonEmptyString
    human_review_contradictions: NonEmptyString


class LLMFallbackTriggers(StrictRulesModel):
    contradictory_scores: StrictBool
    medium_borderline_avg: StrictBool
    medium_borderline_edge_window: Annotated[
        StrictInt | StrictFloat, Field(ge=0.05, le=1)
    ]
    low_score_near_threshold: StrictBool
    low_score_near_threshold_window: Annotated[
        StrictInt | StrictFloat, Field(ge=0.05, le=0.6)
    ]
    missing_assumptions_affecting_decision: StrictBool
    missing_critical_qualitative: StrictBool
    reviewer_disagreement: StrictBool
    grey_zone_deep_dive: StrictBool


class PartnerRules(StrictRulesModel):
    """Every active field in the versioned Partner policy document."""

    version: NonEmptyString
    description: NonEmptyString
    mandate_fit: MandateFitRules
    quality_labels: QualityLabels
    verdict_rules: VerdictRules
    score_thresholds: ScoreThresholds
    critical_risk_keywords: tuple[NonEmptyString, ...] = Field(min_length=1)
    contradictory_scores: ContradictoryScores
    red_flag_keywords: tuple[NonEmptyString, ...] = Field(min_length=1)
    next_actions: NextActions
    llm_fallback_triggers: LLMFallbackTriggers
    missing_qualitative_keywords: tuple[NonEmptyString, ...] = Field(min_length=1)
    assumption_risk_keywords: tuple[NonEmptyString, ...] = Field(min_length=1)
    decision_safety: DecisionSafetyPolicy

    @model_validator(mode="after")
    def validate_cross_section_invariants(self) -> "PartnerRules":
        thresholds = self.score_thresholds
        verdicts = self.verdict_rules
        if verdicts.strong.min_avg_for_yes != thresholds.min_avg_strong_yes:
            raise ValueError(
                "verdict_rules.STRONG.min_avg_for_yes must match "
                "score_thresholds.min_avg_strong_yes"
            )
        if verdicts.medium.min_avg_for_maybe != thresholds.min_avg_medium_maybe:
            raise ValueError(
                "verdict_rules.MEDIUM.min_avg_for_maybe must match "
                "score_thresholds.min_avg_medium_maybe"
            )
        if (
            verdicts.medium.min_avg_for_borderline
            != thresholds.min_avg_borderline_low
        ):
            raise ValueError(
                "verdict_rules.MEDIUM.min_avg_for_borderline must match "
                "score_thresholds.min_avg_borderline_low"
            )
        borderline_width = (
            thresholds.max_avg_borderline_high
            - thresholds.min_avg_borderline_low
        )
        if (
            self.llm_fallback_triggers.medium_borderline_edge_window
            > borderline_width
        ):
            raise ValueError(
                "medium_borderline_edge_window cannot exceed the borderline band"
            )

        advance_threshold = thresholds.min_avg_strong_yes
        safety = self.decision_safety
        score_caps = (
            safety.claim_confidence.score_cap_below_full_confidence,
            safety.freshness.stale_score_cap,
            safety.source_quality.score_cap_below_full_quality,
        )
        if any(cap >= advance_threshold for cap in score_caps):
            raise ValueError(
                "every weak-evidence score cap must be below min_avg_strong_yes"
            )
        if (
            safety.source_quality.full_confidence_at
            < safety.evidence_eligibility.min_source_quality
        ):
            raise ValueError(
                "source_quality.full_confidence_at must be at least min_source_quality"
            )
        return self


def parse_partner_rules(document: PartnerRules | dict[str, Any]) -> PartnerRules:
    """Parse once at the authority boundary, preserving an existing typed object."""
    if isinstance(document, PartnerRules):
        return document
    return PartnerRules.model_validate(document)


def partner_rules_document(rules: PartnerRules) -> dict[str, Any]:
    """Canonical JSON-shaped representation used for hashing and prompts."""
    return rules.model_dump(mode="json", by_alias=True, exclude_none=True)
