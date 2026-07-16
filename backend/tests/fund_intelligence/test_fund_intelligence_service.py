from fund_intelligence.models import LearningAttribution, PolicyProposalStatus
from fund_intelligence.service import build_override_pattern, can_publish, override_attribution


def test_override_patterns_disclose_sample_and_remain_descriptive_below_threshold():
    pattern = build_override_pattern(
        override_type="policy_disagreement",
        signal_ids=["s1", "s2", "s3"],
        opportunity_ids=["o1", "o2", "o3"],
        minimum_sample_size=5,
    )
    assert pattern.sample_size == 3
    assert pattern.ready_for_proposal is False
    assert pattern.limitations
    assert pattern.proposed_patch["mode"] == "descriptive_only"


def test_override_attribution_is_explicit_not_model_failure_by_default():
    assert override_attribution("policy_disagreement") is LearningAttribution.POLICY_CRITERION_DISAGREEMENT
    assert override_attribution("missing_private_evidence") is LearningAttribution.PRIVATE_INFORMATION_EXCEPTION


def test_only_accepted_draft_can_reach_explicit_publish_path():
    assert can_publish(PolicyProposalStatus.ACCEPTED, "draft") is True
    assert can_publish(PolicyProposalStatus.READY_FOR_REVIEW, "draft") is False
    assert can_publish(PolicyProposalStatus.ACCEPTED, "published") is False
