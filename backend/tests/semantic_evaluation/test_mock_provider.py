import pytest

from semantic_evaluation.models import ChoiceProbability, SemanticEvaluationInput, SemanticEvaluationStatus, SemanticEvaluationType, SemanticQuestion
from semantic_evaluation.providers.mock import MockSemanticEvaluationProvider


def _input():
    return SemanticEvaluationInput(
        evaluation_type=SemanticEvaluationType.CLAIM_SUPPORT,
        state={"claim": "x", "evidence_excerpt": "y"},
        questions=[SemanticQuestion(question_id="q1", text="does it support?")],
    )


@pytest.mark.asyncio
async def test_mock_returns_success_with_configured_distribution():
    provider = MockSemanticEvaluationProvider(
        distribution=[ChoiceProbability(label="supports", probability=0.09), ChoiceProbability(label="contradicts", probability=0.91)],
        selected_answer="contradicts", confidence=0.91,
    )
    result = await provider.evaluate(_input())
    assert result.status == SemanticEvaluationStatus.SUCCESS
    assert result.selected_answer == "contradicts"
    assert result.confidence == 0.91
    assert [item.label for item in result.distribution] == ["supports", "contradicts"]
    assert provider.call_count == 1


@pytest.mark.asyncio
async def test_mock_can_simulate_a_raised_error():
    provider = MockSemanticEvaluationProvider(raise_error=RuntimeError("provider down"))
    with pytest.raises(RuntimeError, match="provider down"):
        await provider.evaluate(_input())


@pytest.mark.asyncio
async def test_mock_delay_is_awaitable_and_measurable():
    import time
    provider = MockSemanticEvaluationProvider(delay_seconds=0.05)
    started = time.monotonic()
    result = await provider.evaluate(_input())
    assert time.monotonic() - started >= 0.05
    assert result.status == SemanticEvaluationStatus.SUCCESS
