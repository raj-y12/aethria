"""
Pydantic models for AETHRIA multi-stage startup intelligence.

Enforces strict validation and nested structure for Scout → Reviewer → Partner pipeline.
"""
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Optional, List, Literal, Any, Dict
from datetime import datetime
from utils.timeutil import utcnow, ensure_aware
from uuid import uuid4

RulingDecision = Literal["YES", "NO", "MAYBE"]


_EVALUATION_MODEL_STAGES = frozenset(("scout", "reviewer", "partner"))
_EVALUATION_CONSTRUCTION_PROMPTS = frozenset(
    (
        "scout.market_driven",
        "scout.builder_technical",
        "scout.pain_point",
        "scout.contrarian",
        "reviewer.DefaultReviewer",
        "reviewer.SkepticalReviewer",
        "reviewer.OpportunistReviewer",
        "partner.template",
    )
)
class _FrozenDict(dict):
    """JSON-serializable mapping that rejects post-validation mutation."""

    @staticmethod
    def _immutable(*_args: Any, **_kwargs: Any) -> None:
        raise TypeError("evaluation identity mappings are immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __ior__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable


def _require_exact_non_empty_string_map(
    values: Dict[str, str], *, expected: frozenset[str], field_name: str
) -> None:
    if set(values) != expected:
        raise ValueError(
            f"{field_name} must contain exactly {sorted(expected)!r}"
        )
    if any(not str(value or "").strip() for value in values.values()):
        raise ValueError(f"{field_name} values must be non-empty")


class EvaluationDependencyIdentity(BaseModel):
    """Complete immutable identity for dependencies consumed by one evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: str = Field(min_length=1)
    thesis_id: str = Field(min_length=1)
    thesis_version_id: str = Field(min_length=1)
    thesis_hash: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    policy_version_id: str = Field(min_length=1)
    policy_hash: str = Field(min_length=1)
    rubric_version: str = Field(min_length=1)
    partner_rules_id: str = Field(min_length=1)
    partner_rules_version: str = Field(min_length=1)
    partner_rules_hash: str = Field(min_length=1)
    scoring_runtime_version: str = Field(min_length=1)
    scoring_runtime_hash: str = Field(min_length=1)


class EvaluationModelIdentity(BaseModel):
    """Exact model provider and non-secret request configuration identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    configuration_id: str = Field(min_length=1)
    configuration_hash: str = Field(min_length=1)


class EvaluationManifestIdentity(BaseModel):
    """Construction-time identity later bound to execution prompt evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dependency_identity: EvaluationDependencyIdentity
    model_identities: Dict[str, EvaluationModelIdentity]
    construction_prompt_versions: Dict[str, str]

    @model_validator(mode="after")
    def validate_complete_identity(self) -> "EvaluationManifestIdentity":
        if set(self.model_identities) != _EVALUATION_MODEL_STAGES:
            raise ValueError(
                "model_identities must contain exactly scout, reviewer, and partner"
            )
        _require_exact_non_empty_string_map(
            self.construction_prompt_versions,
            expected=_EVALUATION_CONSTRUCTION_PROMPTS,
            field_name="construction_prompt_versions",
        )
        object.__setattr__(
            self, "model_identities", _FrozenDict(self.model_identities)
        )
        object.__setattr__(
            self,
            "construction_prompt_versions",
            _FrozenDict(self.construction_prompt_versions),
        )
        return self


EvaluationExecutionState = Literal["executed", "reused", "not_run"]


class EvaluationPromptIdentity(BaseModel):
    """Prompt provenance for one logical stage/persona invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_state: EvaluationExecutionState
    construction_prompt_key: Optional[str] = None
    construction_prompt_version: Optional[str] = None
    execution_prompt_version: Optional[str] = None

    @model_validator(mode="after")
    def validate_prompt_identity(self) -> "EvaluationPromptIdentity":
        construction_key = str(self.construction_prompt_key or "").strip()
        construction_version = str(
            self.construction_prompt_version or ""
        ).strip()
        execution_version = str(self.execution_prompt_version or "").strip()
        if self.execution_state == "not_run":
            if construction_key or construction_version or execution_version:
                raise ValueError("not_run prompt identities cannot record versions")
            return self
        if self.execution_state == "executed":
            if not construction_key or not construction_version or not execution_version:
                raise ValueError(
                    "executed prompt identities require construction and execution versions"
                )
            return self
        if not execution_version:
            raise ValueError("reused prompt identities require an execution version")
        if bool(construction_key) != bool(construction_version):
            raise ValueError(
                "reused prompt construction key and version must be supplied together"
            )
        return self


class EvaluationStageIdentity(BaseModel):
    """What a completed evaluation actually executed or reused for one stage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_state: EvaluationExecutionState
    source_pipeline_run_id: Optional[str] = None
    model_identity: Optional[EvaluationModelIdentity] = None
    prompt_identities: Dict[str, EvaluationPromptIdentity]

    @model_validator(mode="after")
    def validate_stage_identity(self) -> "EvaluationStageIdentity":
        source_run = str(self.source_pipeline_run_id or "").strip()
        prompt_states = {
            prompt.execution_state for prompt in self.prompt_identities.values()
        }
        if not self.prompt_identities:
            raise ValueError("stage prompt identities cannot be empty")
        if self.execution_state == "not_run":
            if source_run or self.model_identity is not None:
                raise ValueError("not_run stages cannot record a source or model")
            if prompt_states != {"not_run"}:
                raise ValueError("not_run stages can contain only not_run prompts")
        elif self.execution_state == "executed":
            if not source_run:
                raise ValueError("executed stages require a source pipeline run")
            if "reused" in prompt_states:
                raise ValueError("executed stages cannot contain reused prompts")
        else:
            if "executed" in prompt_states:
                raise ValueError("reused stages cannot contain executed prompts")
            if "reused" not in prompt_states:
                raise ValueError("reused stages require reused prompt evidence")
        object.__setattr__(
            self, "prompt_identities", _FrozenDict(self.prompt_identities)
        )
        return self


class EvaluationManifest(BaseModel):
    """Portable exact identity for one completed current-pipeline evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_version: Literal["evaluation-manifest-v3"] = "evaluation-manifest-v3"
    pipeline_run_id: str = Field(min_length=1)
    evaluation_path: Literal["manual_lookup", "autonomous_discovery", "rerun"]
    user_id: str = Field(min_length=1)
    thesis_id: str = Field(min_length=1)
    thesis_version_id: str = Field(min_length=1)
    thesis_hash: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    policy_version_id: str = Field(min_length=1)
    policy_hash: str = Field(min_length=1)
    rubric_version: str = Field(min_length=1)
    partner_rules_id: str = Field(min_length=1)
    partner_rules_version: str = Field(min_length=1)
    partner_rules_hash: str = Field(min_length=1)
    scoring_runtime_version: str = Field(min_length=1)
    scoring_runtime_hash: str = Field(min_length=1)
    stage_identities: Dict[str, EvaluationStageIdentity]
    created_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def validate_complete_manifest(self) -> "EvaluationManifest":
        if set(self.stage_identities) != _EVALUATION_MODEL_STAGES:
            raise ValueError(
                "stage_identities must contain exactly scout, reviewer, and partner"
            )
        expected_prompts = {
            "scout": {"discovery"},
            "reviewer": {
                "DefaultReviewer",
                "SkepticalReviewer",
                "OpportunistReviewer",
            },
            "partner": {"decision"},
        }
        for stage, prompts in expected_prompts.items():
            if set(self.stage_identities[stage].prompt_identities) != prompts:
                raise ValueError(
                    f"stage_identities.{stage}.prompt_identities must contain "
                    f"exactly {sorted(prompts)!r}"
                )
            stage_identity = self.stage_identities[stage]
            if (
                stage_identity.execution_state == "executed"
                and stage_identity.source_pipeline_run_id != self.pipeline_run_id
            ):
                raise ValueError(
                    f"executed {stage} identity must use this pipeline_run_id"
                )
        object.__setattr__(
            self, "stage_identities", _FrozenDict(self.stage_identities)
        )
        return self


class ScoreBandConfig(BaseModel):
    id: str
    min: float
    max: float
    label: str
    tone: Optional[str] = None


class ScoringWeightConfig(BaseModel):
    key: str
    label: str
    description: Optional[str] = None
    weight: float


class RubricCriterionConfig(BaseModel):
    id: str
    dimension: str
    name: str
    description: str = ""
    weight: float = 100
    positiveSignals: str = ""
    negativeSignals: str = ""
    missingDataBehavior: str = ""
    examples: Dict[str, str] = Field(default_factory=dict)


class FundMandateConfig(BaseModel):
    fundName: str = ""
    mandateName: str = ""
    preferredSectors: List[str] = Field(default_factory=list)
    excludedSectors: Any = Field(default_factory=list)
    excludedSectorList: List[str] = Field(default_factory=list)
    preferredStages: List[str] = Field(default_factory=list)
    geographyPreferences: List[str] = Field(default_factory=list)
    sectors: List[str] = Field(default_factory=list)
    customSectors: str = ""
    geographies: List[str] = Field(default_factory=list)
    customGeography: str = ""
    thesisText: str = ""
    businessModels: str = ""
    checkSizeMin: Optional[float] = None
    checkSizeMax: Optional[float] = None
    ownershipTarget: Optional[float] = None
    minimumTraction: str = ""


class FundThresholdConfig(BaseModel):
    autoPass: float = 39
    monitor: float = 59
    escalation: float = 75
    partnerReview: float = 60
    staleAfterHours: float = 48
    confidenceFloor: float = 0.55
    missingDataThreshold: float = 35


class RiskPolicyConfig(BaseModel):
    sensitivity: Literal["conservative", "balanced", "aggressive"] = "balanced"
    requireAcknowledgement: bool = True
    onlyGateHighSeverity: bool = True
    missingFounderPenalty: float = 8
    missingTractionPenalty: float = 7
    contradictionPenalty: float = 12
    weakSourcePenalty: float = 5


class MemoPreferenceConfig(BaseModel):
    style: Literal["concise", "standard", "detailed"] = "standard"
    deepDiveCollapsed: bool = True
    includeEvidenceExcerpts: bool = True
    includeMissingData: bool = True
    includeScoreReasoning: bool = True
    includeSourceConfidence: bool = True
    tone: Literal["partner", "analyst"] = "partner"


class FundConfig(BaseModel):
    versionLabel: str = "Fund Thesis v1"
    version: int = 1
    lastSavedAt: Optional[str] = None
    activePolicyVersionId: Optional[str] = None
    draftPolicyHash: Optional[str] = None
    publishedPolicyHash: Optional[str] = None
    lastPublishedAt: Optional[str] = None
    mandate: FundMandateConfig = Field(default_factory=FundMandateConfig)
    scoringWeights: List[ScoringWeightConfig] = Field(default_factory=list)
    scoreBands: List[ScoreBandConfig] = Field(default_factory=list)
    thresholds: FundThresholdConfig = Field(default_factory=FundThresholdConfig)
    risk: RiskPolicyConfig = Field(default_factory=RiskPolicyConfig)
    memo: MemoPreferenceConfig = Field(default_factory=MemoPreferenceConfig)
    rubric: List[RubricCriterionConfig] = Field(default_factory=list)


class UserPreferences(BaseModel):
    layoutPreferences: Dict[str, Any] = Field(default_factory=dict)
    savedFilters: List[Dict[str, Any]] = Field(default_factory=list)
    displayPreferences: Dict[str, Any] = Field(default_factory=dict)
    personalOverrides: Dict[str, Any] = Field(default_factory=dict)


class DecisionHistoryRecord(BaseModel):
    company_id: str
    previous_decision: Optional[RulingDecision] = None
    new_decision: RulingDecision
    timestamp: str
    rationale: Optional[str] = None
    confidence: Optional[float] = None
    score_snapshot: Optional[Dict[str, Any]] = None
    risk_acknowledged: Optional[bool] = None
    config_version: Optional[str] = None


class ConvictionState(BaseModel):
    current_ruling: Optional[Dict[str, Any]] = None
    decision_history: List[DecisionHistoryRecord] = Field(default_factory=list)
    ruling_rationale: Optional[str] = None
    risk_acknowledgements: List[Dict[str, Any]] = Field(default_factory=list)
    score_changes: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_changes: List[Dict[str, Any]] = Field(default_factory=list)
    escalation_events: List[Dict[str, Any]] = Field(default_factory=list)


class FundMemory(BaseModel):
    historical_decisions: List[DecisionHistoryRecord] = Field(default_factory=list)
    recurring_risk_patterns: List[Dict[str, Any]] = Field(default_factory=list)
    calibration_observations: List[Dict[str, Any]] = Field(default_factory=list)
    precedent_references: List[Dict[str, Any]] = Field(default_factory=list)
    mandate_drift_notes: List[Dict[str, Any]] = Field(default_factory=list)


class ScoutInfo(BaseModel):
    """Scout discovery information."""
    startup_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    one_line: str
    sector: str
    problem: str
    solution: str
    target_users: str
    why_now: str
    scout_type: Literal["market_driven", "builder_technical", "pain_point", "contrarian"]
    confidence_score: float = Field(ge=0.0, le=1.0)
    # Hypothesis framing from Scout stage.
    primary_thesis: Optional[str] = None
    key_assumptions: Optional[List[str]] = None
    biggest_unknown: Optional[str] = None
    funding_stage: Optional[Literal["Pre-Seed", "Seed", "Series A", "Series B", "Series C", "Series C+", "Unknown"]] = None
    location: Optional[str] = None  # HQ or primary operating city, e.g. "Paris, FR"
    est_tam: Optional[str] = None  # Total Addressable Market estimate
    founder_names: Optional[List[str]] = None  # Structured founder names grounded in retrieved evidence
    # Founder Resolver outcome (deterministic stage after company resolution).
    # Structured founder candidates with role, profile links, previous employment,
    # education, source evidence, conflicts, and per-field confidence.
    # resolution_status: FOUND | PARTIAL | LOW_CONFIDENCE | NOT_FOUND.
    founder_resolution: Optional[Dict[str, Any]] = None
    # Firmographic facts (employees, revenue, founded year, prior rounds) read
    # verbatim out of retrieved evidence by `utils.traction_extraction`. None
    # means nothing matched — never a guess. Exists because this text was being
    # collected and then declared missing by the reviewer.
    traction_facts: Optional[Dict[str, str]] = None
    # Optional provenance for enriched fields (e.g. est_tam, funding_stage, references): scout | reviewer_extraction | gap_retrieval | reviewer_text_infer
    field_provenance: Optional[Dict[str, str]] = None
    # High-level references / source notes for how this opportunity was discovered.
    # E.g. reports, trends, example companies, or general domain knowledge notes.
    references: Optional[List[str]] = None
    source_evidence: Optional[List[Dict[str, str]]] = None
    origin_type: Optional[str] = None
    lookup_input_type: Optional[str] = None
    lookup_query: Optional[str] = None
    lookup_website: Optional[str] = None
    # Stable id for on-demand lookups: same value from POST /api/startups/lookup → scout row → UI pending match.
    lookup_id: Optional[str] = None
    # Operator-supplied private background from a post-hoc re-review (raw text plus
    # fetched content of any links it named). Untrusted; surfaced to the reviewer
    # prompt as unverified evidence — never merged into the scout narrative fields.
    operator_context: Optional[str] = None
    # Company Resolver outcome (stage 1 of on-demand lookups).
    # resolution_status: FOUND | PARTIAL | LOW_CONFIDENCE | NEEDS_REVIEW | NOT_FOUND.
    # Weak evidence is surfaced (PARTIAL/NEEDS_REVIEW) instead of dropping the company.
    resolution_status: Optional[Literal["FOUND", "PARTIAL", "LOW_CONFIDENCE", "NEEDS_REVIEW", "NOT_FOUND"]] = None
    # Full CompanyResolution payload (canonical name, website, linkedin/crunchbase URLs,
    # founder names, confidence, alternatives, evidence sources, missing fields, stage log).
    company_resolution: Optional[Dict[str, Any]] = None
    discovered_at: datetime = Field(default_factory=utcnow)
    # Hash of the system prompt used by the Scout when this discovery was created.
    prompt_version: Optional[str] = None


class SingleReview(BaseModel):
    """
    Per-reviewer evaluation snapshot.
    Used by ReviewerEngine for multi-persona consensus and surfaced to the memo.
    """
    reviewer_type: Literal["DefaultReviewer", "SkepticalReviewer", "OpportunistReviewer"]
    market_score: Optional[float] = Field(default=None, ge=0, le=10)
    product_score: Optional[float] = Field(default=None, ge=0, le=10)
    technical_score: Optional[float] = Field(default=None, ge=0, le=10)
    execution_score: Optional[float] = Field(default=None, ge=0, le=10)
    defensibility_score: Optional[float] = Field(default=None, ge=0, le=10)
    overall_summary: str
    key_risks: List[str]
    verdict: Literal["STRONG", "MEDIUM", "WEAK"]
    diligence_red_flags: List[str] = Field(default_factory=list)
    assumption_feedback: List[str] = Field(default_factory=list)
    team_analysis: Optional[List[str]] = None
    competition_analysis: Optional[List[str]] = None
    business_model_analysis: Optional[List[str]] = None
    investment_thesis: Optional[List[str]] = None
    risk_mitigation: Optional[List[str]] = None
    score_reasoning: Optional[Dict[str, str]] = None
    score_source: Optional[str] = None
    improvement_to_9: Optional[List[str]] = None
    market_reasoning: Optional[List[str]] = None
    market_weaknesses: Optional[List[str]] = None
    market_confidence: Optional[Literal["low", "medium", "high"]] = None
    product_reasoning: Optional[List[str]] = None
    product_weaknesses: Optional[List[str]] = None
    product_confidence: Optional[Literal["low", "medium", "high"]] = None
    technical_reasoning: Optional[List[str]] = None
    technical_weaknesses: Optional[List[str]] = None
    technical_confidence: Optional[Literal["low", "medium", "high"]] = None
    execution_reasoning: Optional[List[str]] = None
    execution_weaknesses: Optional[List[str]] = None
    execution_confidence: Optional[Literal["low", "medium", "high"]] = None
    defensibility_reasoning: Optional[List[str]] = None
    defensibility_weaknesses: Optional[List[str]] = None
    defensibility_confidence: Optional[Literal["low", "medium", "high"]] = None
    # Optional hash of the prompt used by this reviewer instance.
    prompt_version: Optional[str] = None
    structured_scoring: Optional[Dict[str, Any]] = None
    # Normalized extraction payload (auditable input to deterministic scoring).
    structured_signals: Optional[Dict[str, Any]] = None


class AethriaView(BaseModel):
    """Single synthesized committee-facing view derived from persisted review artifacts (template v1)."""
    headline: str = ""
    thesis_fit_line: str = ""
    tension_summary: str = ""
    focal_question: str = ""


class ReviewInfo(BaseModel):
    """Reviewer evaluation information."""
    market_score: Optional[float] = Field(default=None, ge=0, le=10)
    product_score: Optional[float] = Field(default=None, ge=0, le=10)
    technical_score: Optional[float] = Field(default=None, ge=0, le=10)
    execution_score: Optional[float] = Field(default=None, ge=0, le=10)
    defensibility_score: Optional[float] = Field(default=None, ge=0, le=10)  # Calculated by reviewer
    overall_summary: str
    key_risks: List[str]
    verdict: Literal["STRONG", "MEDIUM", "WEAK"]
    diligence_red_flags: List[str] = Field(default_factory=list)  # Missing data flags
    assumption_feedback: List[str] = Field(default_factory=list)  # Comments on Scout assumptions; critical unknowns
    reviewer_agent_id: Optional[str] = None
    reviewed_at: datetime = Field(default_factory=utcnow)
    # VC qualitative fields (optional; use [MISSING] when info absent)
    team_analysis: Optional[List[str]] = None  # Founders, roles, experience, unfair advantage
    competition_analysis: Optional[List[str]] = None  # Competitors, market position, differentiation
    business_model_analysis: Optional[List[str]] = None  # Monetization, pricing, unit economics
    investment_thesis: Optional[List[str]] = None  # Bullet points why to invest + core assumptions
    risk_mitigation: Optional[List[str]] = None  # Actionable strategies per diligence_red_flags
    score_reasoning: Optional[Dict[str, str]] = None  # Per-dimension concise reasoning, e.g. {"market_score": "...", "product_score": "..."}
    score_source: Optional[str] = None
    improvement_to_9: Optional[List[str]] = None
    market_reasoning: Optional[List[str]] = None
    market_weaknesses: Optional[List[str]] = None
    market_confidence: Optional[Literal["low", "medium", "high"]] = None
    product_reasoning: Optional[List[str]] = None
    product_weaknesses: Optional[List[str]] = None
    product_confidence: Optional[Literal["low", "medium", "high"]] = None
    technical_reasoning: Optional[List[str]] = None
    technical_weaknesses: Optional[List[str]] = None
    technical_confidence: Optional[Literal["low", "medium", "high"]] = None
    execution_reasoning: Optional[List[str]] = None
    execution_weaknesses: Optional[List[str]] = None
    execution_confidence: Optional[Literal["low", "medium", "high"]] = None
    defensibility_reasoning: Optional[List[str]] = None
    defensibility_weaknesses: Optional[List[str]] = None
    defensibility_confidence: Optional[Literal["low", "medium", "high"]] = None
    overall_score: Optional[float] = None
    overall_label: Optional[str] = None
    market_score_label: Optional[str] = None
    product_score_label: Optional[str] = None
    technical_score_label: Optional[str] = None
    execution_score_label: Optional[str] = None
    defensibility_score_label: Optional[str] = None
    # Multi-reviewer fields (Meta-Agent aware)
    reviews: Optional[List[SingleReview]] = None
    consensus_verdict: Optional[Literal["STRONG", "MEDIUM", "WEAK"]] = None
    # Blended-score verdict (ReviewerEngine); partner prefers this when present
    derived_verdict: Optional[Literal["STRONG", "MEDIUM", "WEAK"]] = None
    reviewer_disagreement: Optional[bool] = None
    score_variance: Optional[Dict[str, float]] = None
    # Fund thesis alignment (Reviewer consensus row; set when pipeline runs with active thesis)
    fund_thesis_version_id: Optional[str] = None
    thesis_alignment_score: Optional[float] = None  # 0–1
    # no_active_thesis | present | missing_under_active_thesis — lets Partner
    # distinguish "no mandate to gate against" from "mandate active but LLM
    # alignment came back None/malformed", which must fail closed, not open.
    thesis_alignment_state: Optional[str] = None
    thesis_matches_fund: Optional[bool] = None
    thesis_fit_points: Optional[List[str]] = None
    thesis_deviation_points: Optional[List[str]] = None
    thesis_alignment_confidence: Optional[float] = None  # 0–1
    # Resource-backed thesis lens alignment (non-blocking; does not drive rubric scores)
    fund_thesis_alignment_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    # Confidence-adjusted score: S_bar × (1 − reviewer_delta/10); penalises high disagreement
    confidence_adjusted_score: Optional[float] = None
    structured_scoring: Optional[Dict[str, Any]] = None
    # Primary-row normalized structured_signals (DefaultReviewer when present).
    structured_signals: Optional[Dict[str, Any]] = None
    # Resolution layer notes when personas diverge materially.
    resolution_notes: Optional[List[str]] = None
    disagreement_summary: Optional[str] = None
    # Unified narrative from template (no extra LLM in v1).
    aethria_view: Optional[AethriaView] = None


class PartnerSnapshot(BaseModel):
    """Snapshot fields embedded in PartnerInfo."""
    one_liner: str
    stage: Optional[str] = None
    key_signal: Optional[str] = None


class PartnerInfo(BaseModel):
    """Partner decision information — strict JSON output schema."""
    thesis: str
    why_this_matters: str
    snapshot: PartnerSnapshot
    market_insight: str
    product_edge: str
    traction_signals: Optional[str] = None
    risks: List[str]
    recommendation: Literal["INVEST", "PASS", "MONITOR"]
    decision_rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
    next_action: str
    human_review_required: bool = False
    # Metadata set by engine — not from LLM output
    partner_agent_id: Optional[str] = None
    partnered_at: datetime = Field(default_factory=utcnow)
    llm_fallback_reason: Optional[str] = None
    prompt_version: Optional[str] = None
    decision_drivers: Optional[List[str]] = None
    # Mandate-fit gate — company quality and fund fit as separate judgments
    company_quality: Optional[float] = None          # 0-10, conviction-bearing avg score
    fund_fit: Optional[float] = None                 # 0-10, thesis alignment
    fund_fit_label: Optional[str] = None             # Strong fit | Partial fit | Weak fit | Outside thesis
    fund_fit_confidence: Optional[float] = None      # 0-1
    mandate_gate: Optional[str] = None               # clear | weak_fit | outside_thesis | held | alignment_missing | ownership_conflict | no_mandate
    ownership_conflict: Optional[Dict[str, Any]] = None  # set when mandate_gate == ownership_conflict
    mandate_override_required: Optional[bool] = None # strong company held off-thesis, needs IC exception


class Financials(BaseModel):
    """Financial and traction information."""
    traction_metrics: Optional[str] = None  # e.g., "ARR: $2M, 50 customers"
    funding_history: Optional[str] = None  # e.g., "Seed: $1M (2023), Series A: $5M (2024)"
    valuation_est: Optional[str] = None  # e.g., "$10M post-money"
    ip_status: Optional[str] = None  # e.g., "2 patents pending, 1 granted"
    
    # Missing data tracking
    revenue_missing: bool = False
    funding_missing: bool = False
    valuation_missing: bool = False


class Startup(BaseModel):
    """
    Complete startup record with all stages of intelligence.
    
    Supports Scout → Reviewer → Partner pipeline with nested information blocks.
    """
    # Core identity
    startup_id: str = Field(default_factory=lambda: str(uuid4()))
    
    # Stage 1: Scout discovery
    scout_info: ScoutInfo
    
    # Stage 2: Reviewer evaluation (optional)
    review_info: Optional[ReviewInfo] = None
    
    # Stage 3: Partner decision (optional)
    partner_info: Optional[PartnerInfo] = None

    # Persisted display memo (Supabase); set only after partner + full markdown write
    investment_memo_markdown: Optional[str] = None

    # Current human override/ruling, retained for existing API compatibility.
    human_resolution: Optional[Dict[str, Any]] = None

    # Institutional conviction architecture, currently scoped to the authenticated user.
    conviction_state: Optional[ConvictionState] = None

    # When the item entered an unresolved state: initial processing, failed/incomplete
    # processing, pending human review, or unresolved escalation.
    unresolved_at: Optional[datetime] = None

    # Queue awareness: newly discovered companies remain visible until opened
    # or ruled on by the user.
    first_seen_at: Optional[datetime] = None
    last_seen_by_user_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    queue_reason: Optional[str] = None
    priority_reason: Optional[str] = None

    # Structured cross-stage audit trail for Scout -> Reviewer -> Partner handoffs.
    agent_trace: Optional[Dict[str, Any]] = None
    
    # Financials (can be populated at any stage)
    financials: Financials = Field(default_factory=Financials)
    
    # Metadata
    version: int = 1
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    def update_timestamp(self):
        """Update the updated_at timestamp."""
        self.updated_at = utcnow()
    
    def to_dict(self) -> dict:
        """Convert to dict with ISO timestamp strings."""
        data = self.model_dump(mode='json')  # Pydantic handles datetime serialization
        return data
    
    @classmethod
    def _normalize_timestamp(cls, value: Any) -> Optional[datetime]:
        """Convert ISO string or datetime to a tz-aware UTC datetime; None stays None.

        Legacy rows persisted before the tz-aware standardization stored ISO
        strings without an offset; ``ensure_aware`` (via ``parse_iso``) coerces
        those to UTC so they never collide with aware ``utcnow()`` values in a
        comparison.
        """
        if value is None:
            return None
        if isinstance(value, datetime):
            return ensure_aware(value)
        if isinstance(value, str):
            try:
                return ensure_aware(datetime.fromisoformat(value.replace("Z", "+00:00")))
            except ValueError:
                return None
        return None

    @classmethod
    def from_dict(cls, data: dict) -> 'Startup':
        """Create Startup from dict. Handles ISO timestamp strings and null timestamps (uses now() for required datetimes)."""
        data = dict(data)
        # Normalize top-level timestamps
        for key in (
            "created_at",
            "updated_at",
            "unresolved_at",
            "first_seen_at",
            "last_seen_by_user_at",
            "acknowledged_at",
        ):
            if key in data:
                v = cls._normalize_timestamp(data[key])
                data[key] = v if v is not None else (
                    utcnow() if key in ("created_at", "updated_at") else None
                )
        # Nested: scout_info.discovered_at
        if "scout_info" in data and isinstance(data["scout_info"], dict):
            si = dict(data["scout_info"])
            if "discovered_at" in si:
                v = cls._normalize_timestamp(si["discovered_at"])
                si["discovered_at"] = v if v is not None else utcnow()
            data["scout_info"] = si
        # Nested: review_info.reviewed_at
        if "review_info" in data and data["review_info"] and isinstance(data["review_info"], dict):
            ri = dict(data["review_info"])
            if "reviewed_at" in ri:
                v = cls._normalize_timestamp(ri["reviewed_at"])
                ri["reviewed_at"] = v if v is not None else utcnow()
            data["review_info"] = ri
        # Nested: partner_info.partnered_at
        if "partner_info" in data and data["partner_info"] and isinstance(data["partner_info"], dict):
            pi = dict(data["partner_info"])
            if "partnered_at" in pi:
                v = cls._normalize_timestamp(pi["partnered_at"])
                pi["partnered_at"] = v if v is not None else utcnow()
            data["partner_info"] = pi
        return cls.model_validate(data)
