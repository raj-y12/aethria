"""Pure learning attribution and proposal-threshold rules."""

from __future__ import annotations

from typing import Sequence

from fund_intelligence.models import (
    LearningAttribution,
    OverridePattern,
    PolicyProposalStatus,
    PolicyVersionStatus,
)


_ATTRIBUTION = {
    "evidence_correction": LearningAttribution.CLAIM_VERIFICATION_ERROR,
    "missing_private_evidence": LearningAttribution.PRIVATE_INFORMATION_EXCEPTION,
    "policy_disagreement": LearningAttribution.POLICY_CRITERION_DISAGREEMENT,
    "confidence_disagreement": LearningAttribution.WEIGHT_THRESHOLD_DISAGREEMENT,
    "founder_judgment": LearningAttribution.HUMAN_STRATEGIC_EXCEPTION,
    "market_judgment": LearningAttribution.HUMAN_STRATEGIC_EXCEPTION,
    "timing": LearningAttribution.HUMAN_STRATEGIC_EXCEPTION,
    "strategic_exception": LearningAttribution.HUMAN_STRATEGIC_EXCEPTION,
    "relationship_context": LearningAttribution.PRIVATE_INFORMATION_EXCEPTION,
}


def override_attribution(override_type: str) -> LearningAttribution:
    return _ATTRIBUTION.get(str(override_type), LearningAttribution.UNCLASSIFIED)


def build_override_pattern(
    *,
    override_type: str,
    signal_ids: Sequence[str],
    opportunity_ids: Sequence[str],
    minimum_sample_size: int,
) -> OverridePattern:
    sample = len(signal_ids)
    required = max(1, int(minimum_sample_size))
    ready = sample >= required and override_attribution(override_type) is not LearningAttribution.UNCLASSIFIED
    limitations = [
        "Overrides describe GP preference and do not establish investment causality.",
        "The sample may be correlated by sector, stage, sourcing channel, or market period.",
    ]
    if sample < required:
        limitations.insert(0, f"Only {sample} observations; configured proposal threshold is {required}.")
    return OverridePattern(
        override_type=override_type,
        attribution=override_attribution(override_type),
        sample_size=sample,
        opportunity_count=len(set(opportunity_ids)),
        supporting_signal_ids=list(signal_ids),
        limitations=limitations,
        proposed_patch={
            "target": "review_guidance",
            "override_type": override_type,
            "mode": "proposal" if ready else "descriptive_only",
            "instruction": "Review this attributed pattern before editing the scoring policy.",
        },
        ready_for_proposal=ready,
    )


def can_publish(
    proposal_status: PolicyProposalStatus | str,
    policy_version_status: PolicyVersionStatus | str,
) -> bool:
    proposal = PolicyProposalStatus(proposal_status)
    version = PolicyVersionStatus(policy_version_status)
    return proposal in {
        PolicyProposalStatus.ACCEPTED,
        PolicyProposalStatus.EDITED_AND_ACCEPTED,
    } and version is PolicyVersionStatus.DRAFT
