"""Data structures for Meta-Agent cycle outputs."""
from typing import TypedDict, List, Dict, Optional


class PromptMutation(TypedDict, total=False):
    type: str                   # "prompt_proposal" when gated
    mutation_id: str
    mutation_type: str          # "scout_prompt" | "reviewer_prompt"
    agent_target: str           # e.g. "ContrarianScout", "SkepticalReviewer"
    library_key: str            # e.g. "MarketDrivenScout:hash"
    previous_prompt_hash: str
    new_prompt_hash: str
    reasoning: str
    signal_inputs: dict
    applied_at: str
    cycle_number: int
    promoted: bool


class ScoutWeightUpdate(TypedDict):
    scout_type: str             # MarketDrivenScout | BuilderTechnicalScout | PainPointScout | ContrarianScout
    previous_weight: float
    new_weight: float
    reasoning: str
    applied_at: str
    cycle_number: int


class CalibrationMutation(TypedDict):
    parameter: str              # e.g. "confidence_threshold", "reviewer_weak_threshold"
    previous_value: float
    new_value: float
    direction: str              # "tightened" | "loosened" | "reset_drift"
    reasoning: str
    triggered_by: str
    applied_at: str
    cycle_number: int


class MetaCycleReport(TypedDict, total=False):
    cycle_number: int
    ran_at: str
    signal_summary: dict
    prompt_proposals: List[PromptMutation]
    mutations_applied: List[PromptMutation]
    weight_updates: List[ScoutWeightUpdate]
    calibration_changes: List[CalibrationMutation]
    no_action_reasons: List[str]
    next_cycle_at: str
