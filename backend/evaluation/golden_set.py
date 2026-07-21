"""Offline golden-set runner for versioned current-pipeline invariants."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GoldenCase(BaseModel):
    case_id: str
    description: str
    snapshot: Dict[str, Any]
    expected: Dict[str, Any]


class GoldenCorpus(BaseModel):
    version: str
    description: str
    extends_version: Optional[str] = Field(default=None, alias="extends")
    cases: List[GoldenCase] = Field(min_length=1)


def golden_set_path(version: str) -> Path:
    normalized = str(version or "").strip().lower()
    if normalized not in {"v1", "v2", "v3", "v4", "v5", "v6", "v7"}:
        raise ValueError(f"Unknown golden-set version: {version!r}")
    return Path(__file__).resolve().parents[2] / "resources" / "evaluation" / "golden_set" / f"{normalized}.json"


def load_golden_set(version: str) -> GoldenCorpus:
    corpus = GoldenCorpus.model_validate_json(golden_set_path(version).read_text())
    if corpus.extends_version:
        parent = load_golden_set(corpus.extends_version)
        duplicate_ids = {case.case_id for case in parent.cases} & {
            case.case_id for case in corpus.cases
        }
        if duplicate_ids:
            raise ValueError(
                f"Golden-set extension duplicates case ids: {sorted(duplicate_ids)}"
            )
        return GoldenCorpus(
            version=corpus.version,
            description=corpus.description,
            cases=[*parent.cases, *corpus.cases],
        )
    return corpus


def _get(payload: Dict[str, Any], dotted: str) -> Any:
    current: Any = payload
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _manifest_complete(manifest: Any) -> bool:
    if not isinstance(manifest, dict):
        return False
    manifest_version = str(manifest.get("manifest_version") or "").strip()
    if manifest_version == "evaluation-manifest-v2":
        try:
            from models import EvaluationManifest

            EvaluationManifest.model_validate(manifest)
        except Exception:
            return False
        return True
    if manifest_version != "evaluation-manifest-v1":
        return False
    required_scalar = (
        "manifest_version",
        "pipeline_run_id",
        "evaluation_path",
        "policy_version_id",
        "policy_hash",
        "rubric_version",
        "partner_rules_version",
        "partner_rules_hash",
        "created_at",
    )
    if any(not str(manifest.get(key) or "").strip() for key in required_scalar):
        return False
    models = manifest.get("models")
    prompts = manifest.get("prompt_versions")
    if not isinstance(models, dict) or not isinstance(prompts, dict):
        return False
    if any(not str(models.get(key) or "").strip() for key in ("scout", "reviewer", "partner")):
        return False
    required_prompts = (
        "scout",
        "reviewer.DefaultReviewer",
        "reviewer.SkepticalReviewer",
        "reviewer.OpportunistReviewer",
        "partner",
    )
    return all(str(prompts.get(key) or "").strip() for key in required_prompts)


def _evaluate_case(case: GoldenCase) -> List[str]:
    failures: List[str] = []
    institutional_markers = {
        "claim_standard",
        "evidence_contract",
        "evaluation_contract",
        "ruling_contract",
        "workflow_contract",
        "monitoring_contract",
        "fund_intelligence",
        "channel_contract",
        "outcome_contract",
    }
    if institutional_markers & set(case.expected):
        def compare(actual: Any, expected: Any, prefix: str = "") -> None:
            if isinstance(expected, dict):
                if not isinstance(actual, dict):
                    failures.append(prefix or "snapshot")
                    return
                for key, value in expected.items():
                    compare(actual.get(key), value, f"{prefix}.{key}".strip("."))
                return
            if actual != expected:
                failures.append(prefix)

        compare(case.snapshot, case.expected)
        return failures
    if "identity" in case.expected:
        phase2_fields = (
            "source_observation.preserved",
            "source_observation.channel",
            "source_observation.count",
            "identity.status",
            "identity.canonical_company_id",
            "identity.company_count",
            "opportunity.opportunity_id",
            "opportunity.count",
            "opportunity.created",
            "opportunity.blocks_evaluation",
            "projection.legacy_startup_linked",
            "evaluation.started",
        )
        for dotted in phase2_fields:
            if _get(case.snapshot, dotted) != _get(case.expected, dotted):
                failures.append(dotted)
        return failures

    exact_fields = (
        "resolver.outcome",
        "reference_validation.valid",
        "review.market_score",
        "review.product_score",
        "review.technical_score",
        "review.execution_score",
        "review.defensibility_score",
        "partner.recommendation",
        "partner.human_review_required",
    )
    for dotted in exact_fields:
        if _get(case.snapshot, dotted) != _get(case.expected, dotted):
            failures.append(dotted)

    actual_confidence = _get(case.snapshot, "partner.confidence")
    expected_confidence = _get(case.expected, "partner.confidence")
    if not isinstance(expected_confidence, dict):
        failures.append("partner.confidence")
    else:
        try:
            confidence = float(actual_confidence)
            lower = float(expected_confidence["min"])
            upper = float(expected_confidence["max"])
            if not lower <= confidence <= upper:
                failures.append("partner.confidence")
        except (KeyError, TypeError, ValueError):
            failures.append("partner.confidence")

    if case.expected.get("evaluation_manifest", {}).get("complete") is True:
        if not _manifest_complete(case.snapshot.get("evaluation_manifest")):
            failures.append("evaluation_manifest.complete")
    return failures


def run_corpus(corpus: GoldenCorpus) -> Dict[str, Any]:
    cases = []
    for case in corpus.cases:
        failures = _evaluate_case(case)
        cases.append(
            {
                "case_id": case.case_id,
                "status": "failed" if failures else "passed",
                "failures": failures,
            }
        )
    failed = sum(item["status"] == "failed" for item in cases)
    return {
        "version": corpus.version,
        "passed": len(cases) - failed,
        "failed": failed,
        "cases": cases,
    }


def run_golden_set(version: str) -> Dict[str, Any]:
    return run_corpus(load_golden_set(version))


def run_golden_set_path(path: Path) -> Dict[str, Any]:
    return run_corpus(GoldenCorpus.model_validate_json(Path(path).read_text()))
