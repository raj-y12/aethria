"""Versioned per-type definitions: question wording + answer schema.

`evaluation_version` is the human-managed label bumped when a definition is
deliberately republished (mirrors `resources/config/partner_rules/v{N}.json`
versioning). `criteria_version` is `utils.prompt_version.hash_prompt()` over
the definition text (mirrors `REVIEWER_PROMPT_VERSION`/`PARTNER_PROMPT_VERSION`
in `investment_analysis/prompts.py`) — it changes automatically the moment
wording or labels drift, even if someone forgets to bump `evaluation_version`,
so two rows sharing an `evaluation_version` are still guaranteed comparable.

v1 treats question wording and answer labels as one atomic definition per
type. If they ever need to vary independently, split this into two hashed
fields then — there's no evidence that's needed yet.
"""
from __future__ import annotations

from dataclasses import dataclass

from semantic_evaluation.models import SemanticEvaluationType
from utils.prompt_version import hash_prompt


@dataclass(frozen=True)
class SemanticEvaluationDefinition:
    evaluation_version: str
    question_text: str
    labels: tuple[str, ...]

    @property
    def criteria_version(self) -> str:
        return hash_prompt(self.question_text + "|" + ",".join(self.labels))


DEFINITIONS: dict[SemanticEvaluationType, SemanticEvaluationDefinition] = {
    SemanticEvaluationType.EVIDENCE_RELEVANCE: SemanticEvaluationDefinition(
        evaluation_version="v1",
        question_text=(
            "Given this retrieved source and the company it was retrieved for, "
            "is the source actually about this company or claim?"
        ),
        labels=("relevant", "ambiguous", "irrelevant"),
    ),
    SemanticEvaluationType.CLAIM_SUPPORT: SemanticEvaluationDefinition(
        evaluation_version="v1",
        question_text=(
            "Given this evidence excerpt and this specific claim, does the "
            "excerpt support the claim?"
        ),
        labels=("supports", "ambiguous", "contradicts"),
    ),
    SemanticEvaluationType.RESEARCH_USEFULNESS: SemanticEvaluationDefinition(
        evaluation_version="v1",
        question_text=(
            "Given the current evidence snapshot and this open question, is "
            "additional targeted research likely to surface a materially "
            "different answer?"
        ),
        labels=("likely_useful", "uncertain", "unlikely_useful"),
    ),
}


def definition_for(evaluation_type: SemanticEvaluationType) -> SemanticEvaluationDefinition:
    try:
        return DEFINITIONS[evaluation_type]
    except KeyError:
        raise ValueError(f"No definition registered for {evaluation_type!r}") from None
