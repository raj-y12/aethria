import json

from evaluation.golden_set import load_golden_set, run_golden_set, run_golden_set_path


def test_v7_extends_identity_through_outcome_governance():
    corpus = load_golden_set("v7")
    result = run_golden_set("v7")
    assert len(corpus.cases) == 27
    assert result["failed"] == 0
    assert {case.case_id for case in corpus.cases} >= {
        "identity_cross_channel_dedup",
        "evidence_blocks_unsupported_founder_label",
        "failed_refresh_keeps_current_recommendation",
        "fund_intelligence_cannot_self_activate",
        "later_financing_is_not_proof_of_bad_pass",
    }


def test_v7_detects_governance_regression(tmp_path):
    corpus = load_golden_set("v7").model_dump(mode="json")
    target = next(case for case in corpus["cases"] if case["case_id"] == "fund_intelligence_cannot_self_activate")
    target["snapshot"]["fund_intelligence"]["automatic_activation"] = True
    path = tmp_path / "bad-v7.json"
    path.write_text(json.dumps(corpus))
    result = run_golden_set_path(path)
    failed = next(case for case in result["cases"] if case["case_id"] == target["case_id"])
    assert "fund_intelligence.automatic_activation" in failed["failures"]
