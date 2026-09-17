"""Shadow-only semantic evaluation. Observability/calibration capability,
not a source of authority — see README.md for the full design and the
SHADOW invariant this package guarantees.

Small deliberate public surface:

- `evaluate`: typed in, typed out, never raises.
- `schedule_shadow_evaluation`: what authoritative callers actually use —
  fires `evaluate` as a background task and returns immediately.
- `SemanticEvaluationInput` / `SemanticEvaluationResult`: the typed IO shape.
- `SemanticEvaluationType`: the evaluation questions this package knows how
  to ask (`EVIDENCE_RELEVANCE`, `CLAIM_SUPPORT`, `RESEARCH_USEFULNESS`).
- `SemanticQuestion`: one question passed in `SemanticEvaluationInput.questions`.

Deliberately not exported: `SemanticEvaluationRecord` (persistence-only
shape; construct evaluations through `evaluate()`, not by hand),
`SemanticEvaluationRepository` (import directly if you need the read path
for offline comparison tooling), provider implementations (import
`semantic_evaluation.providers.mock.MockSemanticEvaluationProvider`
directly — there is no registry to route through yet).
"""
from __future__ import annotations

from semantic_evaluation.models import (
    SemanticEvaluationInput,
    SemanticEvaluationResult,
    SemanticEvaluationRolloutMode,
    SemanticEvaluationStatus,
    SemanticEvaluationType,
    SemanticQuestion,
)
from semantic_evaluation.service import evaluate, schedule_shadow_evaluation

__all__ = [
    "SemanticEvaluationInput",
    "SemanticEvaluationResult",
    "SemanticEvaluationRolloutMode",
    "SemanticEvaluationStatus",
    "SemanticEvaluationType",
    "SemanticQuestion",
    "evaluate",
    "schedule_shadow_evaluation",
]
