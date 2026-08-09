"""Deterministic counterfactual rule proposals; never production policy changes."""

from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from typing import Any, Iterable


_ALLOWED_RULES = {
    "scoring_weight_adjustment": "scoringWeights",
    "escalation_threshold_adjustment": "thresholds",
    "reviewer_guidance": "review_guidance",
}
_PRODUCTION_DIMENSIONS = {"market", "product", "technical", "execution", "defensibility"}


def _common(hypothesis: dict[str, Any], *, status: str, exact_rule: dict[str, Any] | None, assumptions: list[str]) -> dict[str, Any]:
    proposal = {
        "source_hypothesis_id": hypothesis.get("hypothesis_id"),
        "source_hypothesis_family": hypothesis.get("hypothesis_family"),
        "proposal_status": status,
        "replay_compatibility": "machine_rule_complete" if exact_rule else "not_ready",
        "adaptation_type": (exact_rule or {}).get("adaptation_type"),
        "target_segment": hypothesis.get("segment") or {},
        "exact_rule": deepcopy(exact_rule) if exact_rule else None,
        "parameters": {
            key: value for key, value in (exact_rule or {}).items()
            if key in {"delta", "threshold", "dimension", "policy_path"}
        },
        "supporting_case_ids": sorted(set(str(value) for value in hypothesis.get("supporting_case_ids") or [])),
        "contradictory_case_ids": sorted(set(str(value) for value in hypothesis.get("contradictory_case_ids") or [])),
        "sample_size": hypothesis.get("sample_size"),
        "sufficiency": hypothesis.get("sufficiency"),
        "descriptive_confidence": hypothesis.get("descriptive_confidence"),
        "mandate_versions": sorted(set(str(value) for value in hypothesis.get("mandate_versions") or [])),
        "policy_versions": sorted(set(str(value) for value in hypothesis.get("policy_versions") or [])),
        "time_window": hypothesis.get("time_window") or {"from": None, "to": None},
        "assumptions_required": sorted(set(assumptions)),
        "limitations": [
            "This is an Aethria-generated counterfactual proposal, not observed fund policy.",
            "The proposal is not published and does not change production behavior.",
            "Later outcome observations are excluded from the proposal basis.",
        ],
        "provenance": {
            "owner": "aethria",
            "basis": "explicit_structured_rule" if exact_rule else "insufficient_observation_semantics",
            "llm_used": False,
        },
    }
    identity = json.dumps(proposal, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    proposal["proposal_id"] = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return proposal


def _validated_rule(hypothesis: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    raw = hypothesis.get("counterfactual_rule")
    if not isinstance(raw, dict):
        return None, [
            "A concrete policy target and deterministic rule are required.",
            "Criterion-level or decision-threshold semantics are required before replay.",
        ]
    adaptation_type = str(raw.get("adaptation_type") or "")
    policy_path = str(raw.get("policy_path") or "")
    if adaptation_type not in _ALLOWED_RULES:
        return None, ["The adaptation type is not representable by the existing governed-policy model."]
    if not policy_path.startswith(_ALLOWED_RULES[adaptation_type]):
        return None, ["The rule target is not representable by the existing governed-policy model."]
    sources = raw.get("parameter_sources")
    if not isinstance(sources, list) or str(hypothesis.get("hypothesis_id")) not in {str(value) for value in sources}:
        return None, ["Numeric or threshold parameters must trace to the source hypothesis."]
    if adaptation_type == "scoring_weight_adjustment":
        if str(raw.get("dimension")) not in _PRODUCTION_DIMENSIONS:
            return None, ["A scoring-weight proposal requires an existing production dimension."]
    delta = raw.get("delta")
    if not isinstance(delta, (int, float)) or isinstance(delta, bool) or not math.isfinite(float(delta)) or float(delta) == 0 or abs(float(delta)) > 10:
        return None, ["A bounded numeric delta traceable to the source hypothesis is required."]
    allowed = {"adaptation_type", "policy_path", "dimension", "delta", "parameter_sources"}
    if set(raw) - allowed:
        return None, ["The rule contains unsupported fields."]
    return dict(raw), []


def build_counterfactual_proposals(hypotheses: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for hypothesis in hypotheses:
        if not hypothesis.get("hypothesis_id"):
            continue
        rule, assumptions = _validated_rule(hypothesis)
        proposal = _common(
            hypothesis,
            status="draft_counterfactual" if rule else "insufficient_basis",
            exact_rule=rule,
            assumptions=assumptions,
        )
        proposals.append(proposal)
    proposals.sort(key=lambda item: str(item["proposal_id"]))
    return proposals
