"""Immutable evidence hashing survives retirement of historical execution."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from evaluation_v2.service import materiality_digest, snapshot_claims

EVALUATION_AT = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def _claims():
    return [
        {
            "claim_id": "claim-market",
            "claim_type": "market",
            "normalized_value": {"criterion_score": 8.0},
            "display_text": "Market growth is supported by two independent sources.",
            "assertion_class": "externally_verified",
            "status": "current",
            "confidence": 0.9,
        },
        {
            "claim_id": "claim-execution",
            "claim_type": "execution",
            "normalized_value": {"criterion_score": 7.0},
            "display_text": "Three shipped product iterations are documented.",
            "assertion_class": "externally_verified",
            "status": "current",
            "confidence": 0.8,
        },
    ]



def _verified_link(claim_id, **overrides):
    link = {
        "claim_id": claim_id,
        "evidence_item_id": f"evidence-{claim_id}",
        "relationship": "supports",
        "support_strength": 0.9,
        "verification_state": "verified",
        "source_quality": 0.8,
        "trust_class": "independent",
        "untrusted_input": False,
        "prompt_injection_detected": False,
        "evidence_effective_at": "2026-07-01T00:00:00+00:00",
        "evidence_expires_at": "2026-08-01T00:00:00+00:00",
        "artifact_effective_at": "2026-07-01T00:00:00+00:00",
        "retrieved_at": "2026-07-01T01:00:00+00:00",
    }
    link.update(overrides)
    return link



def test_snapshot_hash_depends_on_values_not_future_live_status():
    original, original_hash = snapshot_claims(_claims(), links=[])
    changed = _claims()
    changed[0]["status"] = "contradicted"
    _, changed_hash = snapshot_claims(changed, links=[])

    assert original[0]["status_at_snapshot"] == "current"
    assert original_hash != changed_hash



def test_snapshot_hash_changes_when_grounding_metadata_changes():
    links = [_verified_link("claim-market")]
    _, original_hash = snapshot_claims(_claims(), links)
    changed_links = [_verified_link("claim-market", source_quality=0.2)]
    _, changed_hash = snapshot_claims(_claims(), changed_links)

    assert original_hash != changed_hash



def test_snapshot_hash_captures_freshness_inputs_and_evaluation_timestamp():
    links = [_verified_link("claim-market")]
    _, original = snapshot_claims(_claims(), links, evaluation_at=EVALUATION_AT)
    _, changed_date = snapshot_claims(
        _claims(),
        [_verified_link("claim-market", retrieved_at="2026-07-02T00:00:00+00:00")],
        evaluation_at=EVALUATION_AT,
    )
    _, changed_clock = snapshot_claims(
        _claims(),
        links,
        evaluation_at=datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc),
    )

    assert original != changed_date
    assert original != changed_clock



def test_materiality_digest_is_clock_independent_for_identical_enriched_rows():
    claims = _claims()
    links = [_verified_link("claim-market"), _verified_link("claim-execution")]
    first_snapshot, first_clocked_hash = snapshot_claims(
        claims, links, evaluation_at=EVALUATION_AT
    )
    second_snapshot, second_clocked_hash = snapshot_claims(
        claims,
        links,
        evaluation_at=datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc),
    )

    assert first_clocked_hash != second_clocked_hash
    assert materiality_digest(first_snapshot) == materiality_digest(second_snapshot)



@pytest.mark.parametrize(
    ("target", "field", "value"),
    [
        ("claim", "normalized_value", {"criterion_score": 6.5}),
        ("claim", "confidence", 0.55),
        ("claim", "status", "contradicted"),
        ("claim", "assertion_class", "operator_attested"),
        ("link", "relationship", "contradicts"),
        ("link", "support_strength", 0.4),
        ("link", "verification_state", "rejected"),
        ("link", "source_quality", 0.3),
        ("link", "trust_class", "founder"),
        ("link", "untrusted_input", True),
        ("link", "prompt_injection_detected", True),
        ("link", "evidence_effective_at", "2026-07-02T00:00:00+00:00"),
        ("link", "evidence_expires_at", "2026-07-31T00:00:00+00:00"),
        ("link", "artifact_effective_at", "2026-06-30T00:00:00+00:00"),
        ("link", "retrieved_at", "2026-07-02T01:00:00+00:00"),
    ],
)
def test_materiality_digest_changes_for_every_decision_bearing_content_field(
    target, field, value
):
    claims = _claims()
    links = [_verified_link("claim-market"), _verified_link("claim-execution")]
    baseline, _ = snapshot_claims(claims, links, evaluation_at=EVALUATION_AT)
    changed_claims = deepcopy(claims)
    changed_links = deepcopy(links)
    collection = changed_claims if target == "claim" else changed_links
    collection[0][field] = value
    changed, _ = snapshot_claims(
        changed_claims, changed_links, evaluation_at=EVALUATION_AT
    )

    assert materiality_digest(baseline) != materiality_digest(changed)
