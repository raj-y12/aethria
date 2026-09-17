"""Provider-neutral semantic evaluation interface.

Mirrors `research/search_providers.py`'s `SearchProvider` Protocol: a small
structural contract, no shared base class to inherit, so a provider is just
any object with this shape. `service.py` is the only caller; it wraps every
call with a timeout and a catch-all, so a provider implementation is free to
raise on genuine failure — it never needs to know about
`SemanticEvaluationStatus` itself.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from semantic_evaluation.models import SemanticEvaluationInput, SemanticEvaluationResult


@runtime_checkable
class SemanticEvaluationProvider(Protocol):
    name: str

    async def evaluate(self, evaluation_input: SemanticEvaluationInput) -> SemanticEvaluationResult:
        """Return a SUCCESS result, or raise. Never return a non-SUCCESS status
        yourself — that translation (TIMEOUT/PROVIDER_ERROR/BUDGET_SKIPPED/
        DISABLED) is `service.py`'s job, so every provider behaves the same
        way under failure."""
        ...
