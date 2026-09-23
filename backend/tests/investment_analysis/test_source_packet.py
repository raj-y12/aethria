from evaluation_v2.service import snapshot_claims
from investment_analysis.service import factual_packet
from tests.evaluation_v2.historical_fixtures import _inputs, CLOCK
import pytest


def test_reviewer_snapshot_retains_original_excerpt_and_source_without_legacy_scores():
    claims, links, _ = _inputs("A_strong_verified")
    links[0].update(artifact_id="source-artifact", source_uri="https://source.example/report",
                    display_excerpt="The source reports annual revenue of $4 million.")
    snapshot, digest = snapshot_claims(claims, links, evaluation_at=CLOCK)
    packet = factual_packet(snapshot)
    # Snapshot ordering is by claim ID; locate the market claim explicitly.
    source = next(claim for claim in packet if claim["claim_type"] == "market")["evidence_relationships"][0]
    assert source["display_excerpt"] == links[0]["display_excerpt"]
    assert source["source_uri"] == links[0]["source_uri"]
    assert source["artifact_id"] == "source-artifact"
    assert "criterion_score" not in str(packet)
    links[0]["display_excerpt"] = "Corrected source excerpt."
    assert snapshot_claims(claims, links, evaluation_at=CLOCK)[1] != digest


@pytest.mark.parametrize("source_id", ["source-artifact", "another-fund-source"])
def test_reasoning_source_reference_must_belong_to_cited_claim(source_id):
    from investment_analysis.models import ReviewerDraft
    from investment_analysis.service import _bind_review
    from pipeline_contracts.models import Lineage, Identity, PolicyVersions

    draft = ReviewerDraft(overall_assessment="Test", investment_case=[{
        "type": "INFERENCE", "text": "Revenue suggests customer demand.",
        "references": {"claim_ids": ["claim-1"], "source_ids": [source_id]},
    }])
    args = dict(draft=draft, lineage=Lineage(user_id="fund-a"), identity=Identity(),
                policy=PolicyVersions(), model=None, snapshot=[{
                    "claim_id": "claim-1", "supporting_evidence_ids": ["item-1"],
                    "evidence_relationships": [{"evidence_item_id": "item-1", "artifact_id": "source-artifact"}],
                }])
    if source_id == "another-fund-source":
        with pytest.raises(ValueError, match="source"):
            _bind_review(**args)
    else:
        assert _bind_review(**args).investment_case[0].references.source_ids == [source_id]


def test_reviewer_source_uri_is_canonicalized_to_artifact_id():
    from investment_analysis.models import ReviewerDraft
    from investment_analysis.service import _bind_review
    from pipeline_contracts.models import Lineage, Identity, PolicyVersions

    draft = ReviewerDraft(overall_assessment="Test", investment_case=[{
        "type": "INFERENCE", "text": "Revenue suggests customer demand.",
        "references": {"claim_ids": ["claim-1"], "source_ids": ["https://source.example/report"]},
    }])
    result = _bind_review(
        draft=draft, lineage=Lineage(user_id="fund-a"), identity=Identity(), policy=PolicyVersions(), model=None,
        snapshot=[{
            "claim_id": "claim-1", "supporting_evidence_ids": ["item-1"],
            "evidence_relationships": [{"evidence_item_id": "item-1", "artifact_id": "source-artifact", "source_uri": "https://source.example/report"}],
        }],
    )
    assert result.investment_case[0].references.source_ids == ["source-artifact"]


def test_reviewer_evidence_alias_is_canonicalized_to_evidence_item_id():
    from investment_analysis.models import ReviewerDraft
    from investment_analysis.service import _bind_review
    from pipeline_contracts.models import Lineage, Identity, PolicyVersions

    draft = ReviewerDraft(overall_assessment="Test", investment_case=[{
        "type": "INFERENCE", "text": "Revenue suggests customer demand.",
        "references": {"claim_ids": ["claim-1"], "evidence_item_ids": ["source-artifact"]},
    }])
    result = _bind_review(
        draft=draft, lineage=Lineage(user_id="fund-a"), identity=Identity(), policy=PolicyVersions(), model=None,
        snapshot=[{
            "claim_id": "claim-1", "supporting_evidence_ids": ["item-1"],
            "evidence_relationships": [{"evidence_item_id": "item-1", "artifact_id": "source-artifact"}],
        }],
    )
    assert result.investment_case[0].references.evidence_item_ids == ["item-1"]
