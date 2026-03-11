"""
Pydantic models for AETHRIA multi-stage startup intelligence.

Enforces strict validation and nested structure for Scout → Reviewer → Partner pipeline.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Any, Dict
from datetime import datetime
from uuid import uuid4


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
    funding_stage: Optional[Literal["Pre-Seed", "Seed", "Series A", "Series B", "Series C+", "Unknown"]] = None
    est_tam: Optional[str] = None  # Total Addressable Market estimate
    # High-level references / source notes for how this opportunity was discovered.
    # E.g. reports, trends, example companies, or general domain knowledge notes.
    references: Optional[List[str]] = None
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
    # Optional hash of the prompt used by this reviewer instance.
    prompt_version: Optional[str] = None


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
    # Multi-reviewer fields (Meta-Agent aware)
    reviews: Optional[List[SingleReview]] = None
    consensus_verdict: Optional[Literal["STRONG", "MEDIUM", "WEAK"]] = None
    reviewer_disagreement: Optional[bool] = None
    score_variance: Optional[Dict[str, float]] = None


class PartnerInfo(BaseModel):
    """Partner decision information."""
    decision: Literal["YES", "NO", "MAYBE"]
    rationale: str
    next_action: str  # e.g., "Request Cap Table", "Technical Code Review", "Pass - Market too crowded"
    conviction_level: int = Field(ge=1, le=10)  # 1-10 conviction
    human_review_required: bool = False
    partner_agent_id: Optional[str] = None
    partnered_at: datetime = Field(default_factory=datetime.now)
    # Optional LLM fallback metadata and portfolio/memo snapshots
    llm_fallback_reason: Optional[str] = None
    memo_at_decision: Optional[str] = None
    portfolio_context_at_decision: Optional[Dict[str, Any]] = None
    prompt_version: Optional[str] = None


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
