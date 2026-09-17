import pytest

from semantic_evaluation.models import (
    SemanticEvaluationInput,
    SemanticEvaluationStatus,
    SemanticEvaluationType,
    SemanticQuestion,
)
from semantic_evaluation.providers.mock import MockSemanticEvaluationProvider
from semantic_evaluation.service import evaluate, reset_rate_limit_window, schedule_shadow_evaluation


@pytest.fixture(autouse=True)
def _isolated_rate_limit_window():
    reset_rate_limit_window()
    yield
    reset_rate_limit_window()


class _FakeRepository:
    def __init__(self):
        self.records = []

    async def record(self, entry):
        self.records.append(entry)


def _input(**overrides):
    defaults = dict(
        evaluation_type=SemanticEvaluationType.CLAIM_SUPPORT,
        state={"claim": "Acme raised a Series A", "evidence_excerpt": "Acme closed a $10M Series A."},
        questions=[SemanticQuestion(question_id="q1", text="does the excerpt support the claim?")],
    )
    defaults.update(overrides)
    return SemanticEvaluationInput(**defaults)


@pytest.mark.asyncio
async def test_disabled_short_circuits_without_calling_provider_or_persisting(monkeypatch):
    monkeypatch.setenv("SEMANTIC_EVALUATION_ENABLED", "false")
    provider = MockSemanticEvaluationProvider()
    repo = _FakeRepository()
    result = await evaluate(_input(), user_id="u1", provider=provider, repository=repo)
    assert result.status == SemanticEvaluationStatus.DISABLED
    assert provider.call_count == 0
    assert repo.records == []


@pytest.mark.asyncio
async def test_success_persists_full_record_with_distribution(monkeypatch):
    monkeypatch.setenv("SEMANTIC_EVALUATION_ENABLED", "true")
    provider = MockSemanticEvaluationProvider()
    repo = _FakeRepository()
    result = await evaluate(_input(), user_id="u1", provider=provider, repository=repo)
    assert result.status == SemanticEvaluationStatus.SUCCESS
    assert len(repo.records) == 1
    record = repo.records[0]
    assert record.evaluation_type == SemanticEvaluationType.CLAIM_SUPPORT
    assert record.evaluation_version == "v1"
    assert record.criteria_version
    assert record.rollout_mode.value == "shadow"
    assert record.provider == "mock"
    assert record.status == SemanticEvaluationStatus.SUCCESS
    assert record.input_digest
    assert record.distribution  # full distribution, not just a confidence scalar


@pytest.mark.asyncio
async def test_timeout_status_when_provider_exceeds_configured_timeout(monkeypatch):
    monkeypatch.setenv("SEMANTIC_EVALUATION_ENABLED", "true")
    monkeypatch.setenv("SEMANTIC_EVALUATION_TIMEOUT_SECONDS", "0.05")
    provider = MockSemanticEvaluationProvider(delay_seconds=1.0)
    repo = _FakeRepository()
    result = await evaluate(_input(), user_id="u1", provider=provider, repository=repo)
    assert result.status == SemanticEvaluationStatus.TIMEOUT
    assert len(repo.records) == 1
    assert repo.records[0].status == SemanticEvaluationStatus.TIMEOUT


@pytest.mark.asyncio
async def test_provider_error_status_when_provider_raises(monkeypatch):
    monkeypatch.setenv("SEMANTIC_EVALUATION_ENABLED", "true")
    provider = MockSemanticEvaluationProvider(raise_error=RuntimeError("boom"))
    repo = _FakeRepository()
    result = await evaluate(_input(), user_id="u1", provider=provider, repository=repo)
    assert result.status == SemanticEvaluationStatus.PROVIDER_ERROR
    assert "boom" in (result.error or "")
    assert repo.records[0].status == SemanticEvaluationStatus.PROVIDER_ERROR


@pytest.mark.asyncio
async def test_unknown_provider_name_yields_provider_error(monkeypatch):
    monkeypatch.setenv("SEMANTIC_EVALUATION_ENABLED", "true")
    monkeypatch.setenv("SEMANTIC_EVALUATION_PROVIDER", "jev")  # not implemented yet
    repo = _FakeRepository()
    result = await evaluate(_input(), user_id="u1", repository=repo)
    assert result.status == SemanticEvaluationStatus.PROVIDER_ERROR
    assert "jev" in (result.error or "")


@pytest.mark.asyncio
async def test_budget_skipped_once_the_in_process_rate_cap_is_exceeded(monkeypatch):
    monkeypatch.setenv("SEMANTIC_EVALUATION_ENABLED", "true")
    monkeypatch.setenv("SEMANTIC_EVALUATION_MAX_CALLS_PER_MINUTE", "1")
    repo = _FakeRepository()
    first = await evaluate(_input(), user_id="u1", provider=MockSemanticEvaluationProvider(), repository=repo)
    second = await evaluate(_input(), user_id="u1", provider=MockSemanticEvaluationProvider(), repository=repo)
    assert first.status == SemanticEvaluationStatus.SUCCESS
    assert second.status == SemanticEvaluationStatus.BUDGET_SKIPPED
    assert len(repo.records) == 2


@pytest.mark.asyncio
async def test_never_raises_even_when_repository_persistence_fails(monkeypatch):
    monkeypatch.setenv("SEMANTIC_EVALUATION_ENABLED", "true")

    class _BrokenRepository:
        async def record(self, entry):
            raise ConnectionError("db unavailable")

    result = await evaluate(_input(), user_id="u1", provider=MockSemanticEvaluationProvider(), repository=_BrokenRepository())
    assert result.status == SemanticEvaluationStatus.SUCCESS  # the evaluation itself still succeeded


@pytest.mark.asyncio
async def test_identical_input_produces_identical_digest(monkeypatch):
    monkeypatch.setenv("SEMANTIC_EVALUATION_ENABLED", "true")
    repo = _FakeRepository()
    await evaluate(_input(), user_id="u1", provider=MockSemanticEvaluationProvider(), repository=repo)
    await evaluate(_input(), user_id="u1", provider=MockSemanticEvaluationProvider(), repository=repo)
    assert repo.records[0].input_digest == repo.records[1].input_digest


@pytest.mark.asyncio
async def test_schedule_shadow_evaluation_returns_immediately_and_is_awaitable(monkeypatch):
    monkeypatch.setenv("SEMANTIC_EVALUATION_ENABLED", "true")
    provider = MockSemanticEvaluationProvider(delay_seconds=0.05)
    repo = _FakeRepository()
    task = schedule_shadow_evaluation(_input(), user_id="u1", provider=provider, repository=repo)
    assert not task.done()  # dispatch did not block on the provider call
    result = await task
    assert result.status == SemanticEvaluationStatus.SUCCESS
    assert len(repo.records) == 1


@pytest.mark.asyncio
async def test_schedule_shadow_evaluation_never_lets_a_provider_exception_escape(monkeypatch):
    monkeypatch.setenv("SEMANTIC_EVALUATION_ENABLED", "true")
    task = schedule_shadow_evaluation(
        _input(), user_id="u1", provider=MockSemanticEvaluationProvider(raise_error=RuntimeError("boom")),
    )
    result = await task  # must not raise
    assert result.status == SemanticEvaluationStatus.PROVIDER_ERROR
