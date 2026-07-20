"""Executable safety certification over the canonical decision contracts."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import pytest

from decisions.models import HumanRulingDecision
from decisions.service import classify_override
from evaluation_v2.models import EvaluationPolicy
from evaluation_v2.policy import evaluation_policy_from_compiled
from evaluation_v2.service import evaluate_snapshot
from utils.partner_codes import legacy_ruling_from_institutional


@dataclass(frozen=True)
class SafetyCase:
    name: str
    kind: Literal["evaluation", "override", "projection"]
    expected_state: str | None = None
    expected_human_review: bool | None = None
    expected_missing_information: str | None = None
    expected_override: str | None = None
    expected_projection: dict[str, str | None] | None = None


CASES = [
    SafetyCase(
        "ungrounded_high_score", "evaluation", expected_state="insufficient_evidence"
    ),
    SafetyCase(
        "model_inferred_high_score", "evaluation", expected_state="insufficient_evidence"
    ),
    SafetyCase(
        "required_dimension_missing",
        "evaluation",
        expected_state="insufficient_evidence",
    ),
    SafetyCase(
        "grounded_critical_risk_with_high_scores", "evaluation", expected_state="pass"
    ),
    SafetyCase(
        "grounded_hard_exclusion_with_high_scores", "evaluation", expected_state="pass"
    ),
    SafetyCase(
        "grounded_complete_high_scores", "evaluation", expected_state="advance"
    ),
    SafetyCase("zero_claim_confidence", "evaluation", expected_state="insufficient_evidence"),
    SafetyCase("below_minimum_claim_confidence", "evaluation", expected_state="insufficient_evidence"),
    SafetyCase("minimum_claim_confidence_boundary", "evaluation", expected_state="monitor"),
    SafetyCase("high_claim_confidence", "evaluation", expected_state="advance"),
    SafetyCase(
        "exact_false_critical_risk",
        "evaluation",
        expected_state="advance",
        expected_human_review=False,
    ),
    SafetyCase(
        "malformed_critical_risk",
        "evaluation",
        expected_state="advance",
        expected_human_review=True,
        expected_missing_information="critical risk",
    ),
    SafetyCase("expired_evidence", "evaluation", expected_state="insufficient_evidence"),
    SafetyCase("undated_evidence", "evaluation", expected_state="insufficient_evidence"),
    SafetyCase("stale_evidence", "evaluation", expected_state="monitor"),
    SafetyCase("low_quality_evidence", "evaluation", expected_state="monitor"),
    SafetyCase("advance_then_invest", "override", expected_override=None),
    SafetyCase(
        "advance_ruling_projection",
        "projection",
        expected_projection={"value": "MAYBE", "compatibility_reason": "advance"},
    ),
]


EVALUATION_AT = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def _support(evidence_id: str, **overrides: Any) -> dict[str, object]:
    link = {
        "evidence_item_id": evidence_id,
        "relationship": "supports",
        "support_strength": 0.9,
        "verification_state": "verified",
        "source_quality": 0.9,
        "trust_class": "independent",
        "untrusted_input": True,
        "prompt_injection_detected": False,
        "evidence_effective_at": "2026-07-01T00:00:00+00:00",
        "evidence_expires_at": "2026-08-01T00:00:00+00:00",
        "artifact_effective_at": "2026-07-01T00:00:00+00:00",
        "retrieved_at": "2026-07-01T01:00:00+00:00",
    }
    link.update(overrides)
    return link


def _claim(
    claim_id: str,
    claim_type: str,
    *,
    score: float | None = None,
    assertion_class: str = "externally_verified",
    grounded: bool = True,
    value: Any = None,
    confidence: float = 0.9,
    support_overrides: dict[str, Any] | None = None,
) -> dict[str, object]:
    normalized: dict[str, object] = {}
    if score is not None:
        normalized["criterion_score"] = score
    if value is not None:
        normalized["value"] = value
    relationships = (
        [_support(f"evidence-{claim_id}", **(support_overrides or {}))]
        if grounded
        else []
    )
    return {
        "claim_id": claim_id,
        "claim_type": claim_type,
        "normalized_value": normalized,
        "unit": None,
        "period": None,
        "display_text": claim_type.replace("_", " "),
        "status_at_snapshot": "current",
        "assertion_class_at_snapshot": assertion_class,
        "operator_attribution_at_snapshot": None,
        "confidence_at_snapshot": confidence,
        "evaluation_at_snapshot": EVALUATION_AT.isoformat(),
        "supporting_evidence_ids": [
            link["evidence_item_id"] for link in relationships
        ],
        "contradicting_evidence_ids": [],
        "evidence_relationships": relationships,
    }


def _snapshot_for(name: str) -> list[dict[str, object]]:
    market = _claim("market", "market", score=9)
    execution = _claim("execution", "execution", score=9)
    if name == "ungrounded_high_score":
        return [
            _claim("market", "market", score=9, grounded=False),
            _claim("execution", "execution", score=9, grounded=False),
        ]
    if name == "model_inferred_high_score":
        return [
            _claim("market", "market", score=9, assertion_class="model_inferred"),
            _claim("execution", "execution", score=9, assertion_class="model_inferred"),
        ]
    if name == "required_dimension_missing":
        return [market]
    if name == "grounded_critical_risk_with_high_scores":
        return [market, execution, _claim("risk", "critical_risk", value=True)]
    if name == "grounded_hard_exclusion_with_high_scores":
        return [
            market,
            execution,
            _claim("exclusion", "mandate_exclusion", value=True),
        ]
    if name == "grounded_complete_high_scores":
        return [market, execution]
    if name in {
        "zero_claim_confidence",
        "below_minimum_claim_confidence",
        "minimum_claim_confidence_boundary",
        "high_claim_confidence",
    }:
        confidence = {
            "zero_claim_confidence": 0,
            "below_minimum_claim_confidence": 0.49,
            "minimum_claim_confidence_boundary": 0.5,
            "high_claim_confidence": 0.9,
        }[name]
        return [
            _claim("market", "market", score=9, confidence=confidence),
            _claim("execution", "execution", score=9, confidence=confidence),
        ]
    if name == "exact_false_critical_risk":
        return [market, execution, _claim("risk", "critical_risk", value=False)]
    if name == "malformed_critical_risk":
        return [market, execution, _claim("risk", "critical_risk", value="false")]
    if name in {"expired_evidence", "undated_evidence", "stale_evidence", "low_quality_evidence"}:
        overrides = {
            "expired_evidence": {"evidence_expires_at": "2026-07-19T00:00:00+00:00"},
            "undated_evidence": {
                "evidence_effective_at": None,
                "evidence_expires_at": None,
                "artifact_effective_at": None,
                "retrieved_at": None,
            },
            "stale_evidence": {
                "evidence_effective_at": "2025-01-01T00:00:00+00:00",
                "evidence_expires_at": None,
                "artifact_effective_at": "2025-01-01T00:00:00+00:00",
                "retrieved_at": "2025-01-01T00:00:00+00:00",
            },
            "low_quality_evidence": {"source_quality": 0.5},
        }[name]
        return [
            _claim("market", "market", score=9, support_overrides=overrides),
            _claim("execution", "execution", score=9, support_overrides=overrides),
        ]
    raise AssertionError(f"No evaluation snapshot for {name}")


def _safety_policy() -> EvaluationPolicy:
    partner_rules_path = (
        Path(__file__).resolve().parents[3]
        / "resources/config/partner_rules/v3.json"
    )
    partner_rules = json.loads(partner_rules_path.read_text())
    return evaluation_policy_from_compiled(
        {
            "policy_version_id": "policy-safety-v1",
            "policy_hash": "policy-safety-hash",
            "dimensions": {
                "market": {
                    "weight": 0.6,
                    "criteria": [{"id": "market", "source_components": []}],
                },
                "execution": {
                    "weight": 0.4,
                    "criteria": [{"id": "execution", "source_components": []}],
                },
            },
        },
        partner_rules=partner_rules,
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_decision_safety_case(case: SafetyCase) -> None:
    if case.kind == "evaluation":
        result = evaluate_snapshot(
            _snapshot_for(case.name), _safety_policy(), evaluation_at=EVALUATION_AT
        )
        assert result.recommendation.state.value == case.expected_state
        if case.expected_human_review is not None:
            assert (
                result.recommendation.human_review_required
                is case.expected_human_review
            )
        if case.expected_missing_information is not None:
            assert case.expected_missing_information in (
                item.lower() for item in result.recommendation.missing_information
            )
    elif case.kind == "override":
        assert classify_override(
            recommendation="advance",
            ruling=HumanRulingDecision.INVEST,
            requested=None,
        ) == case.expected_override
    else:
        projection = legacy_ruling_from_institutional("advance")
        assert projection.model_dump() == case.expected_projection
