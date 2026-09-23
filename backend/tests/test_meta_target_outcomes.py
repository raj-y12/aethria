"""Meta prompt targets must retain truthful terminal outcomes."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from meta.agent import MetaAgent
from meta.mutator import PromptMutator
from meta.schema import (
    PromptMutationBatchResult,
    PromptMutationTargetOutcome,
    PromptMutationTargetState,
)
from pipeline_execution import StageExecutionState


def _target(name: str) -> dict:
    return {
        "agent_target": name,
        "mutation_type": "scout_prompt",
        "trigger": "round-four regression",
        "signal": {},
    }


def _proposal(name: str) -> dict:
    return {
        "type": "prompt_proposal",
        "mutation_id": f"proposal-{name}",
        "mutation_type": "scout_prompt",
        "agent_target": name,
        "library_key": f"{name}:hash",
        "previous_prompt_hash": "old",
        "new_prompt_hash": "new",
        "reasoning": "test",
        "signal_inputs": {},
        "applied_at": "2026-07-21T00:00:00+00:00",
        "cycle_number": 1,
        "promoted": False,
        "activation_status": "pending_operator_promotion",
    }


def test_meta_does_not_propose_prompts_for_retired_reviewer_personas() -> None:
    mutator = PromptMutator(
        {"reviewer_health": {"verdict_distribution": {"STRONG": 9, "WEAK": 1},
                             "calibration_warning": True}},
        cycle_number=1,
        user_id="meta-target-user",
    )
    try:
        assert mutator.decide() == []
    finally:
        mutator.close()


def test_prompt_mutator_returns_one_typed_outcome_per_target(monkeypatch) -> None:
    mutator = PromptMutator({}, cycle_number=1, user_id="meta-target-user")
    calls = iter([_proposal("MarketDrivenScout"), RuntimeError("LLM unavailable")])

    def apply_one(*_args):
        result = next(calls)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(mutator, "_apply_one", apply_one)

    batch = mutator.apply(
        [_target("MarketDrivenScout"), _target("ContrarianScout")], None
    )

    assert isinstance(batch, PromptMutationBatchResult)
    assert batch.attempted == 2
    assert batch.succeeded == 1
    assert batch.failed == 1
    assert batch.proposals == [_proposal("MarketDrivenScout")]
    assert [outcome.state for outcome in batch.outcomes] == [
        PromptMutationTargetState.PROPOSED,
        PromptMutationTargetState.FAILED,
    ]
    assert batch.outcomes[1].agent_target == "ContrarianScout"
    mutator.close()


def test_prompt_mutator_reports_persistence_failure_as_failed_target(monkeypatch) -> None:
    mutator = PromptMutator(
        {"pipeline_health": {}}, cycle_number=1, user_id="meta-persistence-user"
    )
    monkeypatch.setattr(
        mutator,
        "_get_current_prompt",
        lambda *_args: "existing prompt " * 40,
    )
    monkeypatch.setattr(
        mutator,
        "_call_llm",
        lambda *_args, **_kwargs: ("rewritten prompt " * 40, "reason"),
    )

    with patch(
        "meta.mutator._append_to_json_list",
        side_effect=RuntimeError("mutation store unavailable"),
    ):
        batch = mutator.apply([_target("MarketDrivenScout")], None)

    assert batch.attempted == 1
    assert batch.succeeded == 0
    assert batch.failed == 1
    assert batch.proposals == []
    assert batch.outcomes[0].state is PromptMutationTargetState.FAILED
    assert batch.outcomes[0].code == "prompt_proposal_persistence_failed"
    mutator.close()


def test_prompt_mutator_reports_llm_failure_as_failed_target(monkeypatch) -> None:
    mutator = PromptMutator(
        {"pipeline_health": {}}, cycle_number=1, user_id="meta-llm-user"
    )
    monkeypatch.setattr(
        mutator,
        "_get_current_prompt",
        lambda *_args: "existing prompt " * 40,
    )
    monkeypatch.setattr(
        mutator,
        "_call_llm",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("LLM unavailable")),
    )

    batch = mutator.apply([_target("MarketDrivenScout")], None)

    assert batch.failed == 1
    assert batch.outcomes[0].state is PromptMutationTargetState.FAILED
    assert batch.outcomes[0].code == "prompt_llm_failed"
    mutator.close()


def test_meta_cycle_aggregates_partial_target_failure_and_keeps_report(
    monkeypatch,
) -> None:
    agent = MetaAgent(user_id="meta-aggregate-user")
    monkeypatch.setattr("meta.agent.claim_due_jobs", lambda *_args, **_kwargs: {"meta"})
    report = {
        "cycle_number": 1,
        "prompt_proposals": [_proposal("MarketDrivenScout")],
        "prompt_target_outcomes": [
            PromptMutationTargetOutcome(
                agent_target="MarketDrivenScout",
                state=PromptMutationTargetState.PROPOSED,
                code="prompt_proposal_persisted",
                detail="Prompt proposal persisted.",
                proposal=_proposal("MarketDrivenScout"),
            ).model_dump(mode="json"),
            PromptMutationTargetOutcome(
                agent_target="ContrarianScout",
                state=PromptMutationTargetState.FAILED,
                code="prompt_llm_failed",
                detail="Prompt mutation LLM failed.",
            ).model_dump(mode="json"),
        ],
    }
    monkeypatch.setattr(agent, "_run_cycle_sync", lambda: report)

    result = asyncio.run(agent.run_cycle(force=True))

    assert result.outcome.state is StageExecutionState.FAILED
    assert result.outcome.code == "meta_target_failures"
    assert result.outcome.attempted == 2
    assert result.outcome.succeeded == 1
    assert result.outcome.failed == 1
    assert result.report == report


def test_meta_cycle_does_not_report_all_target_failure_as_clean_completion(
    monkeypatch,
) -> None:
    agent = MetaAgent(user_id="meta-all-failed-user")
    monkeypatch.setattr("meta.agent.claim_due_jobs", lambda *_args, **_kwargs: {"meta"})
    report = {
        "cycle_number": 1,
        "prompt_proposals": [],
        "prompt_target_outcomes": [
            PromptMutationTargetOutcome(
                agent_target="MarketDrivenScout",
                state=PromptMutationTargetState.FAILED,
                code="prompt_proposal_persistence_failed",
                detail="Prompt proposal persistence failed.",
            ).model_dump(mode="json")
        ],
    }
    monkeypatch.setattr(agent, "_run_cycle_sync", lambda: report)

    result = asyncio.run(agent.run_cycle(force=True))

    assert result.outcome.state is StageExecutionState.FAILED
    assert result.outcome.attempted == 1
    assert result.outcome.succeeded == 0
    assert result.outcome.failed == 1
    assert result.report == report
