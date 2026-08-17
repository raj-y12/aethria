"""Deterministic evidence-plan computation (spec §9.3). No model call —
compares the compiled policy's required claim types against what the
tenant currently has, matching evaluate_snapshot()'s own claim_type-in-list
check (evaluation_v2/service.py:364) so the same rule decides both what
"missing" means and what evaluate() will actually score."""

from __future__ import annotations

from evaluation_v2.models import EvaluationPolicy


def compute_missing_evidence(
    policy: EvaluationPolicy, current_claim_types: set[str],
) -> tuple[list[str], list[str]]:
    missing_evidence: list[str] = []
    search_questions: list[str] = []
    for rule in policy.criteria:
        if any(claim_type in current_claim_types for claim_type in rule.claim_types):
            continue
        missing_evidence.append(rule.criterion)
        wanted = ", ".join(rule.claim_types)
        search_questions.append(
            f"What evidence establishes {rule.criterion} for this company? "
            f"(any of: {wanted})"
        )
    return missing_evidence, search_questions
