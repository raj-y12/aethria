"""Deterministic provider for tests and for `SEMANTIC_EVALUATION_PROVIDER=mock`
(the default). Carries zero real cost and no external dependency, so it is
the only provider this first implementation pass wires end-to-end — proving
the abstraction and the SHADOW invariant before any paid provider exists.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from semantic_evaluation.models import (
    ChoiceProbability,
    SemanticEvaluationInput,
    SemanticEvaluationResult,
    SemanticEvaluationStatus,
)


class MockSemanticEvaluationProvider:
    """Returns a fixed, caller-supplied result. Can also simulate a slow or
    failing provider so `service.py`'s TIMEOUT/PROVIDER_ERROR handling is
    exercised without a real provider ever needing to misbehave in a test.
    """

    name = "mock"

    def __init__(
        self,
        *,
        distribution: Optional[list[ChoiceProbability]] = None,
        selected_answer: Optional[str] = None,
        confidence: Optional[float] = None,
        delay_seconds: float = 0.0,
        raise_error: Optional[BaseException] = None,
    ) -> None:
        self.distribution = distribution if distribution is not None else [
            ChoiceProbability(label="relevant", probability=1.0),
        ]
        self.selected_answer = selected_answer or (
            self.distribution[0].label if self.distribution else None
        )
        self.confidence = confidence if confidence is not None else (
            self.distribution[0].probability if self.distribution else None
        )
        self.delay_seconds = delay_seconds
        self.raise_error = raise_error
        self.call_count = 0

    async def evaluate(self, evaluation_input: SemanticEvaluationInput) -> SemanticEvaluationResult:
        self.call_count += 1
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        if self.raise_error is not None:
            raise self.raise_error
        return SemanticEvaluationResult(
            status=SemanticEvaluationStatus.SUCCESS,
            selected_answer=self.selected_answer,
            confidence=self.confidence,
            distribution=self.distribution,
            provider=self.name,
            model="mock-v1",
            provider_model_version=None,
            tokens=0,
            estimated_cost_usd=0.0,
        )
