import json

from evaluation.golden_set import load_golden_set, run_golden_set, run_golden_set_path


def test_v2_extends_nine_v1_cases_with_identity_invariants():
    corpus = load_golden_set("v2")
    result = run_golden_set("v2")

    assert corpus.version == "v2"
    assert len(corpus.cases) >= 15
    assert {case.case_id for case in corpus.cases} >= {
        "strong_fit_strong_references",
        "identity_cross_channel_dedup",
        "identity_same_name_distinct_domains",
        "identity_ambiguity_blocks_evaluation",
        "identity_repeat_idempotency",
    }
    assert result["failed"] == 0


def test_v2_detects_identity_regression_without_changing_v1(tmp_path):
    corpus = load_golden_set("v2").model_dump(mode="json")
    target = next(
        case
        for case in corpus["cases"]
        if case["case_id"] == "identity_ambiguity_blocks_evaluation"
    )
    target["snapshot"]["opportunity"]["blocks_evaluation"] = False
    path = tmp_path / "bad-v2.json"
    path.write_text(json.dumps(corpus))

    result = run_golden_set_path(path)

    failed = next(
        case
        for case in result["cases"]
        if case["case_id"] == "identity_ambiguity_blocks_evaluation"
    )
    assert "opportunity.blocks_evaluation" in failed["failures"]
    assert run_golden_set("v1")["failed"] == 0
