import importlib
import json
import subprocess
import sys
from pathlib import Path


def _golden_module():
    return importlib.import_module("evaluation.golden_set")


def test_golden_set_v1_contains_the_required_current_pipeline_cases():
    golden = _golden_module()
    corpus = golden.load_golden_set("v1")

    assert corpus.version == "v1"
    assert {case.case_id for case in corpus.cases} == {
        "strong_fit_strong_references",
        "strong_company_outside_mandate",
        "weak_company_polished_materials",
        "sparse_preseed_evidence",
        "conflicting_founder_traction",
        "ambiguous_identity",
        "unsupported_founder_narrative",
        "hard_pass_human_review",
        "repeat_unchanged_snapshot",
    }


def test_golden_set_v1_executes_without_network_or_model_calls():
    golden = _golden_module()

    result = golden.run_golden_set("v1")

    assert result["version"] == "v1"
    assert result["passed"] == 9
    assert result["failed"] == 0
    assert all(case["status"] == "passed" for case in result["cases"])


def test_golden_set_reports_the_exact_invariant_that_drifted(tmp_path):
    golden = _golden_module()
    source = golden.golden_set_path("v1")
    payload = json.loads(source.read_text())
    payload["cases"][0]["snapshot"]["partner"]["recommendation"] = "PASS"
    drifted = tmp_path / "v1.json"
    drifted.write_text(json.dumps(payload))

    result = golden.run_golden_set_path(drifted)

    assert result["passed"] == 8
    assert result["failed"] == 1
    failure = result["cases"][0]
    assert failure["case_id"] == "strong_fit_strong_references"
    assert "partner.recommendation" in failure["failures"]


def test_golden_set_requires_complete_evaluation_manifests(tmp_path):
    golden = _golden_module()
    payload = json.loads(golden.golden_set_path("v1").read_text())
    del payload["cases"][1]["snapshot"]["evaluation_manifest"]["policy_hash"]
    incomplete = tmp_path / "v1.json"
    incomplete.write_text(json.dumps(payload))

    result = golden.run_golden_set_path(incomplete)

    failure = result["cases"][1]
    assert failure["status"] == "failed"
    assert "evaluation_manifest.complete" in failure["failures"]


def test_golden_set_cli_returns_machine_readable_result():
    backend = Path(__file__).parents[1]
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run_golden_set.py",
            "--version",
            "v1",
            "--json",
        ],
        cwd=backend,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["version"] == "v1"
    assert result["failed"] == 0
