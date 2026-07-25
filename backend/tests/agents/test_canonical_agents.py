from agents.canonical import DeterministicPartner, EvidenceReviewer


def _evaluation(state="advance"):
    return {
        "evaluation_id": "eval-1", "recommendation_id": "rec-1",
        "criteria": [{"criterion": "market", "score": 7}],
        "recommendation": {
            "state": state, "confidence": 0.72,
            "decision_drivers": ["verified demand"],
            "principal_risks": ["retention"],
            "missing_information": [], "human_review_required": True,
        },
    }


def test_evidence_reviewer_reports_only_immutable_evaluation_fields():
    review = EvidenceReviewer().review(_evaluation())
    assert review.evaluation_id == "eval-1"
    assert review.evidence_coverage == "sufficient"
    assert review.decision_drivers == ["verified demand"]


def test_deterministic_partner_preserves_recommendation_state():
    review = EvidenceReviewer().review(_evaluation("pass"))
    route = DeterministicPartner().route(_evaluation("pass"), review)
    assert route.route == "pass"
    assert route.recommendation_id == "rec-1"


def test_unknown_or_missing_recommendation_fails_closed():
    evaluation = _evaluation("unexpected")
    evaluation["recommendation"]["missing_information"] = ["revenue"]
    review = EvidenceReviewer().review(evaluation)
    route = DeterministicPartner().route(evaluation, review)
    assert review.evidence_coverage == "insufficient"
    assert route.route == "insufficient_evidence"
