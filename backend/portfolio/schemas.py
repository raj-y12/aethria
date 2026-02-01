"""
Portfolio data schemas.
All portfolio data structures must follow these schemas.
"""
from typing import TypedDict, Optional, List, Dict, Any, Literal
from datetime import datetime


class StartupRecord(TypedDict):
    """Canonical startup record in startups.json"""
    id: str  # Stable UUID
    name: str
    one_line: str
    sector: str
    problem: str
    solution: str
    target_users: str
    why_now: str
    scout_type: str
    scout_confidence: float
    discovered_at: str  # ISO timestamp
    version: int  # Version number for this record
    metadata: Dict[str, Any]  # Additional metadata


class DecisionRecord(TypedDict):
    """Decision record in decisions.json"""
    id: str  # Stable UUID
    startup_id: str  # References StartupRecord.id
    decision: Literal["INVEST", "WATCH", "PASS"]
    confidence: int  # 1-10
    rationale: str
    next_action: str
    human_review_required: bool
    partner_agent_id: str  # e.g., "partner_v1"
    decided_at: str  # ISO timestamp
    version: int


class PortfolioRecord(TypedDict):
    """Accepted company in portfolio.json"""
    id: str  # Stable UUID
    startup_id: str  # References StartupRecord.id
    decision_id: str  # References DecisionRecord.id
    accepted_at: str  # ISO timestamp
    status: Literal["active", "archived", "exited"]
    key_risks: List[str]
    follow_up_triggers: List[str]
    execution_agent_id: str
    version: int
    metadata: Dict[str, Any]


class RejectionRecord(TypedDict):
    """Rejected company in rejections.json"""
    id: str  # Stable UUID
    startup_id: str  # References StartupRecord.id
    decision_id: str  # References DecisionRecord.id
    rejected_at: str  # ISO timestamp
    reason_code: str  # e.g., "LOW_SCORE", "CRITICAL_RISK", "WEAK_VERDICT"
    rationale: str
    key_risks: List[str]
    execution_agent_id: str
    version: int


class WatchlistRecord(TypedDict):
    """Watchlist company in watchlist.json"""
    id: str  # Stable UUID
    startup_id: str  # References StartupRecord.id
    decision_id: str  # References DecisionRecord.id
    added_at: str  # ISO timestamp
    last_checked_at: Optional[str]  # ISO timestamp
    check_interval_days: int  # Days between checks
    next_check_at: str  # ISO timestamp
    cached_summary: str  # Cached summary for diff comparison
    execution_agent_id: str
    version: int


class SignalRecord(TypedDict):
    """Signal update in signals.json"""
    id: str  # Stable UUID
    startup_id: str  # References StartupRecord.id
    signal_type: Literal["positive", "negative", "neutral"]
    strength: float  # 0.0-1.0
    description: str
    detected_at: str  # ISO timestamp
    affected_confidence: Optional[float]  # Updated confidence if applicable
    tracker_agent_id: str
    version: int


class AgentMetric(TypedDict):
    """Agent performance metric in agent_metrics.json"""
    agent_id: str  # e.g., "scout_market_driven", "reviewer_v1", "partner_v1"
    agent_type: Literal["scout", "reviewer", "partner"]
    metric_name: str  # e.g., "acceptance_rate", "rejection_reversal_rate"
    metric_value: float
    calculated_at: str  # ISO timestamp
    period_start: str  # ISO timestamp
    period_end: str  # ISO timestamp
    sample_size: int  # Number of decisions/outcomes in this period
    version: int


class SystemHealthRecord(TypedDict):
    """System health check record"""
    id: str  # Stable UUID
    check_type: Literal["duplicate_detection", "inactivity", "runaway_loop", "memory_bloat"]
    severity: Literal["low", "medium", "high", "critical"]
    description: str
    detected_at: str  # ISO timestamp
    resolved: bool
    resolution_action: Optional[str]
    version: int
