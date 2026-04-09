import pytest

from partner.schema import validate_partner_output


def _valid_payload():
    return {
        "decision": "MAYBE",
        "conviction_level": 5,
        "rationale": "Balanced profile with score dispersion; requires human diligence.",
        "next_action": "1) Validate customer pull\n2) Review team execution signal",
        "human_review_required": True,
        "assumption_risks": [],
    }


def test_validate_partner_output_accepts_valid_payload():
    out = validate_partner_output(_valid_payload())
    assert out["decision"] == "MAYBE"
    assert out["conviction_level"] == 5


def test_validate_partner_output_rejects_empty_rationale():
    payload = _valid_payload()
    payload["rationale"] = "   "
    with pytest.raises(ValueError, match="rationale must be a non-empty string"):
        validate_partner_output(payload)


def test_validate_partner_output_rejects_empty_next_action():
    payload = _valid_payload()
    payload["next_action"] = ""
    with pytest.raises(ValueError, match="next_action must be a non-empty string"):
        validate_partner_output(payload)


def test_validate_partner_output_rejects_out_of_bounds_conviction():
    payload = _valid_payload()
    payload["conviction_level"] = 11
    with pytest.raises(ValueError, match="must be between 1 and 10"):
        validate_partner_output(payload)
