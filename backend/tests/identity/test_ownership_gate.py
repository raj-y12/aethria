from identity.ownership_gate import check_ownership_conflict, detect_acquisition_signal


def test_detects_common_acquisition_phrasings():
    assert detect_acquisition_signal("Workvivo was acquired by Zoom in 2023.") is not None
    assert detect_acquisition_signal("The acquisition of Workvivo by Zoom closed last year.") is not None
    assert detect_acquisition_signal("Acme is now a wholly-owned subsidiary of BigCo.") is not None


def test_no_signal_in_ordinary_narrative():
    assert detect_acquisition_signal("Acme raised a Series B to expand into new markets.") is None
    assert detect_acquisition_signal("") is None
    assert detect_acquisition_signal(None) is None  # type: ignore[arg-type]


def test_check_ownership_conflict_blocks_when_evidence_mentions_acquisition():
    scout_output = {"one_line": "Employee engagement platform.", "why_now": "Was acquired by Zoom in 2023."}
    review_output = {"overall_summary": "Strong historical growth pre-acquisition."}

    result = check_ownership_conflict(scout_output, review_output)

    assert result is not None
    assert result["code"] == "ownership_conflict_detected"
    assert "acquired" in result["matched_text"].lower()


def test_check_ownership_conflict_clears_ordinary_companies():
    scout_output = {"one_line": "Employee engagement platform.", "why_now": "Growing fast."}
    review_output = {"overall_summary": "Strong team, healthy growth."}

    assert check_ownership_conflict(scout_output, review_output) is None


def test_operator_spinout_override_clears_the_gate():
    scout_output = {"why_now": "Was acquired by Zoom, then spun back out.", "ownership_verified_spinout": True}
    review_output = {}

    assert check_ownership_conflict(scout_output, review_output) is None
