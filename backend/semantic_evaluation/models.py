"""Typed contracts for shadow semantic evaluation.

Provider-neutral by design: nothing here or in `service.py`/`repository.py`
mentions Jev. Provider-specific naming stays inside `providers/jev.py` (not
yet implemented) and is translated into these shapes at the provider
boundary, the same way `research/search_providers.py` normalises Exa/
Firecrawl payloads into `ProviderSearchResults` before anything downstream
sees them.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pipeline_contracts.models import Contract


class SemanticEvaluationType(str, Enum):
    """The evaluation questions this package currently knows how to ask.

    Each member owns exactly one versioned definition in `definitions.py`.
    Add a member only when its definition also exists — an enum value with
    no definition is a broken evaluation, not a placeholder.
    """

    EVIDENCE_RELEVANCE = "evidence_relevance"
    CLAIM_SUPPORT = "claim_support"
    RESEARCH_USEFULNESS = "research_usefulness"


class SemanticEvaluationRolloutMode(str, Enum):
    """Deliberately only the stages this capability has actually earned.

    Do not add ADVISORY/AUTHORITATIVE members speculatively — add one only
    when promotion criteria (see README.md) have genuinely been met for at
    least one evaluation type, and even then gate it per-type, not globally.
    """

    DISABLED = "disabled"
    SHADOW = "shadow"


class SemanticEvaluationStatus(str, Enum):
    """Every outcome `service.evaluate()` can return. Never an exception.

    SUCCESS         — provider returned a validated result.
    TIMEOUT         — provider call exceeded SEMANTIC_EVALUATION_TIMEOUT_SECONDS.
    PROVIDER_ERROR  — provider raised or returned something unusable.
    BUDGET_SKIPPED  — the in-process rate cap was exceeded; provider never called.
    DISABLED        — SEMANTIC_EVALUATION_ENABLED is false; provider never called.
    """

    SUCCESS = "success"
    TIMEOUT = "timeout"
    PROVIDER_ERROR = "provider_error"
    BUDGET_SKIPPED = "budget_skipped"
    DISABLED = "disabled"


class SemanticQuestion(Contract):
    question_id: str
    text: str


class SemanticEvaluationInput(Contract):
    """What a caller hands to `service.evaluate()`.

    `state` is the already-sanitized payload the provider reasons over —
    callers own keeping it small and non-sensitive; this package does not
    inspect or persist it verbatim (see `input_digest` on the record).
    """

    evaluation_type: SemanticEvaluationType
    state: dict[str, Any]
    questions: list[SemanticQuestion]
    claim_ids: list[str] = []
    source_ids: list[str] = []
    pipeline_run_id: Optional[str] = None
    workflow_run_id: Optional[str] = None
    startup_id: Optional[str] = None
    opportunity_id: Optional[str] = None


class ChoiceProbability(Contract):
    label: str
    probability: float


class SemanticEvaluationResult(Contract):
    """What a provider returns, and what `evaluate()` always returns —
    regardless of outcome. Callers never need a try/except for this.
    """

    status: SemanticEvaluationStatus
    selected_answer: Optional[str] = None
    confidence: Optional[float] = None
    distribution: list[ChoiceProbability] = []
    provider: Optional[str] = None
    model: Optional[str] = None
    provider_model_version: Optional[str] = None
    latency_ms: Optional[float] = None
    tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    error: Optional[str] = None


class SemanticEvaluationRecord(Contract):
    """The full row persisted for every non-DISABLED evaluate() call.

    Persists identifiers and a digest of the input, not the raw state —
    `claim_ids`/`source_ids` are what let a human reconstruct what was
    actually judged six weeks later without storing potentially sensitive
    or oversized content a second time.
    """

    evaluation_id: str
    user_id: str
    pipeline_run_id: Optional[str] = None
    workflow_run_id: Optional[str] = None
    startup_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    evaluation_type: SemanticEvaluationType
    evaluation_version: str
    criteria_version: str
    rollout_mode: SemanticEvaluationRolloutMode
    provider: str
    model: Optional[str] = None
    provider_model_version: Optional[str] = None
    status: SemanticEvaluationStatus
    input_digest: str
    claim_ids: list[str] = []
    source_ids: list[str] = []
    selected_answer: Optional[str] = None
    confidence: Optional[float] = None
    distribution: list[ChoiceProbability] = []
    latency_ms: Optional[float] = None
    tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    error: Optional[str] = None
