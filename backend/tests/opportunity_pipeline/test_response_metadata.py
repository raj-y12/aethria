from opportunity_pipeline import _evaluation_response_metadata


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


def test_response_reports_only_immutable_evaluation_fields():
    review, _ = _evaluation_response_metadata(_evaluation())
    assert review["evaluation_id"] == "eval-1"
    assert review["evidence_coverage"] == "sufficient"
    assert review["decision_drivers"] == ["verified demand"]


def test_response_preserves_recommendation_state():
    _, route = _evaluation_response_metadata(_evaluation("pass"))
    assert route["route"] == "pass"
    assert route["recommendation_id"] == "rec-1"


def test_unknown_or_missing_recommendation_fails_closed():
    evaluation = _evaluation("unexpected")
    evaluation["recommendation"]["missing_information"] = ["revenue"]
    review, route = _evaluation_response_metadata(evaluation)
    assert review["evidence_coverage"] == "insufficient"
    assert route["route"] == "insufficient_evidence"
