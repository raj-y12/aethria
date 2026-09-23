"""Deterministic evidence-plan computation. No model call.

Compare the compiled policy's required claim types with the tenant's current
claims. Presence is a retrieval-planning signal, not proof that validation can
score a Reviewer proposal supported by those claims.
"""

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
