"""Fail-closed historical replay previews for Fund Learning hypotheses."""

from __future__ import annotations

from typing import Any


REPLAYABLE_FAMILIES: frozenset[str] = frozenset()


def build_replay_preview(hypothesis: dict[str, Any]) -> dict[str, Any]:
    """Return a counterfactual preview without inventing a policy action."""
    case_ids = sorted({
        str(case_id)
        for key in ("supporting_case_ids", "contradictory_case_ids")
        for case_id in hypothesis.get(key) or []
    })
    family = str(hypothesis.get("hypothesis_family") or "")
    replayable = family in REPLAYABLE_FAMILIES and bool(hypothesis.get("replay_rule"))
    if replayable:
        raise RuntimeError("No replay rule is currently implemented")
    return {
        "hypothesis_id": hypothesis.get("hypothesis_id"),
        "hypothesis_family": family,
        "affected_segment": hypothesis.get("segment") or {},
        "replay_status": "not_replayable",
        "historical_cases_evaluated": [],
        "cases_changed": [],
        "cases_unchanged": [],
        "cases_indeterminate": case_ids,
        "case_results": [],
        "original_recommendations": [],
        "simulated_recommendations": [],
        "mandate_versions": hypothesis.get("mandate_versions") or [],
        "policy_versions": hypothesis.get("policy_versions") or [],
        "time_window": hypothesis.get("time_window") or {"from": None, "to": None},
        "limitations": [
            "The hypothesis describes observed behavior but does not define a deterministic policy delta, threshold, or criterion transformation.",
            "No historical recommendation or ruling was simulated.",
            "A replay cannot be produced without an explicit governed counterfactual rule.",
        ],
        "outcome_context_used_for_replay": False,
    }
