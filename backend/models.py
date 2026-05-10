"""
Pydantic models for AETHRIA multi-stage startup intelligence.

Enforces strict validation and nested structure for Scout → Reviewer → Partner pipeline.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Any, Dict
from datetime import datetime
from uuid import uuid4

RulingDecision = Literal["YES", "NO", "MAYBE"]


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
    est_tam: Optional[str] = None  # Total Addressable Market estimate
    # Optional provenance for enriched fields (e.g. est_tam, funding_stage, references): scout | reviewer_extraction | gap_retrieval | reviewer_text_infer
    field_provenance: Optional[Dict[str, str]] = None
    # High-level references / source notes for how this opportunity was discovered.
    # E.g. reports, trends, example companies, or general domain knowledge notes.
    references: Optional[List[str]] = None
    origin_type: Optional[str] = None
    lookup_input_type: Optional[str] = None
    lookup_query: Optional[str] = None
    lookup_website: Optional[str] = None
    # Stable id for on-demand lookups: same value from POST /api/startups/lookup → scout row → UI pending match.
    lookup_id: Optional[str] = None
    discovered_at: datetime = Field(default_factory=datetime.now)
    # Hash of the system prompt used by the Scout when this discovery was created.
    prompt_version: Optional[str] = None


class SingleReview(BaseModel):
    """
    Per-reviewer evaluation snapshot.
    Used by ReviewerEngine for multi-persona consensus and surfaced to the memo.
    """
    reviewer_type: Literal["DefaultReviewer", "SkepticalReviewer", "OpportunistReviewer"]
    market_score: int = Field(ge=1, le=10)
    product_score: int = Field(ge=1, le=10)
    technical_score: int = Field(ge=1, le=10)
    execution_score: int = Field(ge=1, le=10)
    defensibility_score: Optional[int] = Field(default=None, ge=1, le=10)
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
    market_score: int = Field(ge=1, le=10)
    product_score: int = Field(ge=1, le=10)
    technical_score: int = Field(ge=1, le=10)
    execution_score: int = Field(ge=1, le=10)
    defensibility_score: Optional[int] = Field(default=None, ge=1, le=10)  # Calculated by reviewer
    overall_summary: str
    key_risks: List[str]
    verdict: Literal["STRONG", "MEDIUM", "WEAK"]
    diligence_red_flags: List[str] = Field(default_factory=list)  # Missing data flags
    assumption_feedback: List[str] = Field(default_factory=list)  # Comments on Scout assumptions; critical unknowns
    reviewer_agent_id: Optional[str] = None
    reviewed_at: datetime = Field(default_factory=datetime.now)
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
    thesis_matches_fund: Optional[bool] = None
    thesis_fit_points: Optional[List[str]] = None
    thesis_deviation_points: Optional[List[str]] = None
    thesis_alignment_confidence: Optional[float] = None  # 0–1
    # Resource-backed thesis lens alignment (non-blocking; does not drive rubric scores)
    fund_thesis_alignment_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    # Weighted skepticism defensibility (1.5x SkepticalReviewer weight); raw float for downstream use
    weighted_defensibility_score: Optional[float] = None
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
    partnered_at: datetime = Field(default_factory=datetime.now)
    llm_fallback_reason: Optional[str] = None
    prompt_version: Optional[str] = None
    decision_drivers: Optional[List[str]] = None


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
    
    # Financials (can be populated at any stage)
    financials: Financials = Field(default_factory=Financials)
    
    # Metadata
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def update_timestamp(self):
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()
    
    def to_dict(self) -> dict:
        """Convert to dict with ISO timestamp strings."""
        data = self.model_dump(mode='json')  # Pydantic handles datetime serialization
        return data
    
    @classmethod
    def _normalize_timestamp(cls, value: Any) -> Optional[datetime]:
        """Convert ISO string or datetime to datetime; None stays None for optional fields."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    @classmethod
    def from_dict(cls, data: dict) -> 'Startup':
        """Create Startup from dict. Handles ISO timestamp strings and null timestamps (uses now() for required datetimes)."""
        data = dict(data)
        # Normalize top-level timestamps
        for key in ("created_at", "updated_at"):
            if key in data:
                v = cls._normalize_timestamp(data[key])
                data[key] = v if v is not None else datetime.now()
        # Nested: scout_info.discovered_at
        if "scout_info" in data and isinstance(data["scout_info"], dict):
            si = dict(data["scout_info"])
            if "discovered_at" in si:
                v = cls._normalize_timestamp(si["discovered_at"])
                si["discovered_at"] = v if v is not None else datetime.now()
            data["scout_info"] = si
        # Nested: review_info.reviewed_at
        if "review_info" in data and data["review_info"] and isinstance(data["review_info"], dict):
            ri = dict(data["review_info"])
            if "reviewed_at" in ri:
                v = cls._normalize_timestamp(ri["reviewed_at"])
                ri["reviewed_at"] = v if v is not None else datetime.now()
            data["review_info"] = ri
        # Nested: partner_info.partnered_at
        if "partner_info" in data and data["partner_info"] and isinstance(data["partner_info"], dict):
            pi = dict(data["partner_info"])
            if "partnered_at" in pi:
                v = cls._normalize_timestamp(pi["partnered_at"])
                pi["partnered_at"] = v if v is not None else datetime.now()
            data["partner_info"] = pi
        return cls.model_validate(data)
