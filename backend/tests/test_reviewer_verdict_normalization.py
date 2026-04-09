import pytest

from reviewer.schema import validate_reviewer_output


def _base_review_payload():
    return {
        "market_score": 7,
        "product_score": 6,
        "technical_score": 6,
        "execution_score": 5,
        "overall_summary": "Promising but incomplete.",
        "key_risks": ["Execution risk due to missing team details."],
        "verdict": "MEDIUM",
    }


def test_promising_alias_normalizes_to_medium():
    payload = _base_review_payload()
    payload["verdict"] = "PROMISING"
    out = validate_reviewer_output(payload)
    assert out["verdict"] == "MEDIUM"


def test_invalid_verdict_still_rejected():
    payload = _base_review_payload()
    payload["verdict"] = "GREAT"
    with pytest.raises(ValueError, match="verdict must be one of"):
        validate_reviewer_output(payload)
