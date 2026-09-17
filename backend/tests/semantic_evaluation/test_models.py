import pytest
from pydantic import ValidationError

from semantic_evaluation.models import (
    ChoiceProbability,
    SemanticEvaluationInput,
    SemanticEvaluationRecord,
    SemanticEvaluationRolloutMode,
    SemanticEvaluationStatus,
    SemanticEvaluationType,
    SemanticQuestion,
)


def test_input_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        SemanticEvaluationInput(
            evaluation_type=SemanticEvaluationType.CLAIM_SUPPORT,
            state={}, questions=[], not_a_real_field=True,
        )


def test_distribution_is_preserved_not_reduced_to_confidence():
    distribution = [
        ChoiceProbability(label="relevant", probability=0.71),
        ChoiceProbability(label="ambiguous", probability=0.21),
        ChoiceProbability(label="irrelevant", probability=0.08),
    ]
    record = SemanticEvaluationRecord(
        evaluation_id="e1", user_id="u1", evaluation_type=SemanticEvaluationType.EVIDENCE_RELEVANCE,
        evaluation_version="v1", criteria_version="abc123", rollout_mode=SemanticEvaluationRolloutMode.SHADOW,
        provider="mock", status=SemanticEvaluationStatus.SUCCESS, input_digest="d",
        selected_answer="relevant", confidence=0.71, distribution=distribution,
    )
    assert [item.probability for item in record.distribution] == [0.71, 0.21, 0.08]
    assert sum(item.probability for item in record.distribution) == pytest.approx(1.0)


def test_rollout_mode_has_no_speculative_stages():
    # Only what has actually been earned. Adding ADVISORY/AUTHORITATIVE
    # members is a deliberate promotion decision, not a default to add here.
    assert {mode.value for mode in SemanticEvaluationRolloutMode} == {"disabled", "shadow"}


def test_evaluation_type_members_are_exactly_the_first_three_shadow_evals():
    assert {t.value for t in SemanticEvaluationType} == {
        "evidence_relevance", "claim_support", "research_usefulness",
    }


def test_question_requires_id_and_text():
    q = SemanticQuestion(question_id="q1", text="does it?")
    assert q.question_id == "q1"
    assert q.text == "does it?"
