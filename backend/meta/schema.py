"""Data structures for Meta-Agent cycle outputs."""
from enum import Enum
from typing import Any, TypedDict, List, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    activation_status: str


class PromptMutationTargetState(str, Enum):
    """Terminal state for one mutation target."""

    PROPOSED = "proposed"
    REJECTED = "rejected"
    FAILED = "failed"


class PromptMutationTargetOutcome(BaseModel):
    """Lossless result of attempting one requested prompt mutation."""

    model_config = ConfigDict(frozen=True)

    agent_target: str = Field(min_length=1)
    state: PromptMutationTargetState
    code: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    detail: str = Field(min_length=1)
    proposal: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_proposal_payload(self) -> "PromptMutationTargetOutcome":
        if self.state is PromptMutationTargetState.PROPOSED:
            if not isinstance(self.proposal, dict):
                raise ValueError("proposed target outcomes require a proposal")
        elif self.proposal is not None:
            raise ValueError("non-proposed target outcomes cannot publish a proposal")
        return self


class PromptMutationBatchResult(BaseModel):
    """Typed accounting for every target passed to ``PromptMutator.apply``."""

    model_config = ConfigDict(frozen=True)

    outcomes: List[PromptMutationTargetOutcome] = Field(default_factory=list)

    @property
    def attempted(self) -> int:
        return len(self.outcomes)

    @property
    def succeeded(self) -> int:
        return sum(
            outcome.state is not PromptMutationTargetState.FAILED
            for outcome in self.outcomes
        )

    @property
    def failed(self) -> int:
        return sum(
            outcome.state is PromptMutationTargetState.FAILED
            for outcome in self.outcomes
        )

    @property
    def proposals(self) -> List[Dict[str, Any]]:
        return [
            dict(outcome.proposal)
            for outcome in self.outcomes
            if outcome.state is PromptMutationTargetState.PROPOSED
            and isinstance(outcome.proposal, dict)
        ]


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
    analysis_only: bool
    production_mutations_applied: int
    prompt_proposals: List[PromptMutation]
    prompt_target_outcomes: List[dict]
    mutations_applied: List[PromptMutation]
    weight_proposals: List[ScoutWeightUpdate]
    calibration_proposals: List[CalibrationMutation]
    weight_updates: List[ScoutWeightUpdate]
    calibration_changes: List[CalibrationMutation]
    no_action_reasons: List[str]
    next_cycle_at: str
