"""
Meta Agent Phase 2: shadow reviewer evaluation against a fixed startup set.
Compares the current Reviewer against frozen current-analysis baselines.
"""
from __future__ import annotations

import asyncio
import logging
import json
from hashlib import sha256
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from meta.prompt_gating import (
    REVIEWER_EVAL_AGENT_TARGETS,
    load_eval_startup_ids,
    load_prompt_library,
    save_last_eval_for_library_key,
)
from tenant_context import require_user_id
from investment_analysis.models import AnalysisResult
from investment_analysis.service import generate_review
from investment_analysis.validation import validate_assessments

logger = logging.getLogger(__name__)

def compare_assessments(baseline, candidate) -> Dict[str, Any]:
    """Compare validated support, never infer an investment verdict from scores."""
    before = {item.dimension.value: item for item in baseline.assessments}
    after = {item.dimension.value: item for item in candidate.assessments}
    lost = [dimension for dimension, item in before.items()
            if item.validated_score is not None
            and (dimension not in after or after[dimension].validated_score is None)]
    deltas = [abs(after[dimension].validated_score - item.validated_score)
              for dimension, item in before.items()
              if item.validated_score is not None and dimension in after
              and after[dimension].validated_score is not None]
    agreements = all(dimension in after and
                     (item.support_status, item.contradiction_status, item.score_status)
                     == (after[dimension].support_status, after[dimension].contradiction_status, after[dimension].score_status)
                     for dimension, item in before.items()) and set(before) == set(after)
    return {"regression": bool(lost), "lost_support_dimensions": lost,
            "support_match": agreements, "n_scored_dimensions": len(deltas),
            "mean_abs_delta": round(sum(deltas) / len(deltas), 3) if deltas else None}


def evaluation_passes(
    *,
    regression_count: int,
    mean_abs_delta: float,
    n_compared: int,
) -> Tuple[bool, str]:
    if n_compared <= 0:
        return False, "no_comparisons"
    if regression_count > 0:
        return False, "support_regression"
    try:
        max_delta = float(os.getenv("META_PROMPT_EVAL_MAX_MEAN_DELTA", "2.5"))
    except ValueError:
        max_delta = 2.5
    if mean_abs_delta > max_delta:
        return False, "mean_delta_exceeded"
    return True, "ok"


async def run_prompt_evaluation(
    *,
    user_id: str,
    agent_target: str,
    library_key: str,
    load_baseline,
    policy,
    generate,
    reviewer_model: str | None = None,
    startup_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run shadow reviews for candidate prompt in library_key (reviewer agents only).
    """
    user_id = require_user_id(user_id, context="prompt_evaluation")
    if agent_target not in REVIEWER_EVAL_AGENT_TARGETS:
        return {"ok": False, "error": "agent_target must be a reviewer persona", "rows": []}

    library = load_prompt_library(user_id)
    ent = library.get(library_key) if isinstance(library, dict) else None
    if not isinstance(ent, dict) or not str(ent.get("prompt") or "").strip():
        return {"ok": False, "error": "library_key not found or empty prompt", "rows": []}

    if library_key.split(":", 1)[0] != agent_target:
        return {"ok": False, "error": "library_key does not belong to agent_target", "rows": []}
    candidate_prompt = str(ent["prompt"])

    ids = [str(x).strip() for x in (startup_ids if startup_ids is not None else load_eval_startup_ids(user_id)) if str(x).strip()]
    try:
        max_n = int(os.getenv("META_PROMPT_EVAL_MAX_STARTUPS", "20"))
    except ValueError:
        max_n = 20
    truncated = False
    if len(ids) > max_n:
        ids = ids[:max_n]
        truncated = True

    if not ids:
        return {"ok": False, "error": "no startup_ids (configure eval set or pass startup_ids)", "rows": []}

    sem = asyncio.Semaphore(max(1, int(os.getenv("META_PROMPT_EVAL_CONCURRENCY", "3"))))

    async def one(sid: str) -> Dict[str, Any]:
        row: Dict[str, Any] = {"startup_id": sid, "status": "ok"}
        async with sem:
            try:
                record = await load_baseline(sid)
                if record is None:
                    row["status"] = "no_baseline"
                    return row
                evaluation = record["evaluation"]
                raw = (evaluation.get("judgment_audit") or {}).get("investment_analysis")
                if not raw:
                    row["status"] = "no_current_analysis_baseline"
                    return row
                baseline = AnalysisResult.model_validate(raw)
                if baseline.reviewer.lineage.user_id != user_id:
                    raise ValueError("baseline tenant mismatch")
                versions = baseline.reviewer.policy_versions
                if (versions.policy_hash != policy.policy_hash
                        or versions.policy_version != policy.policy_version_id
                        or versions.rubric_version != policy.rubric_version
                        or versions.partner_rules_version != policy.partner_rules_version):
                    row["status"] = "baseline_policy_changed"
                    return row
                snapshot = evaluation["claim_snapshot"]
                digest = sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                if digest != baseline.reviewer.lineage.evidence_snapshot_hash:
                    raise ValueError("baseline snapshot mismatch")
                clocks = {claim.get("evaluation_at_snapshot") for claim in snapshot}
                if len(clocks) != 1 or None in clocks:
                    row["status"] = "baseline_clock_unavailable"
                    return row
                evaluation_at = datetime.fromisoformat(str(clocks.pop()).replace("Z", "+00:00"))
                _, review, admitted, _ = await generate_review(
                    user_id=user_id, lineage=baseline.reviewer.lineage,
                    identity=baseline.reviewer.identity, snapshot=snapshot, policy=policy,
                    context=baseline.context_snapshot, generate=generate,
                    reviewer_model=reviewer_model, prompt=candidate_prompt)
                validated, _ = validate_assessments(user_id=user_id, review=review,
                    snapshot=admitted, policy=policy, evaluation_at=evaluation_at)
                row.update(compare_assessments(baseline.validation, validated))
                row["baseline_evaluation_id"] = str(evaluation["evaluation_id"])
                if not row["n_scored_dimensions"] and not row["regression"]:
                    row["status"] = "no_scored_comparisons"
            except Exception as e:
                logger.warning("eval row failed for %s: %s", sid, getattr(e, "code", type(e).__name__))
                row["status"] = "error"
                row["error"] = getattr(e, "code", "review_failed")
        return row

    rows = await asyncio.gather(*[one(sid) for sid in ids])

    compared = [r for r in rows if r.get("status") == "ok"]
    regressions = sum(1 for r in compared if r.get("regression"))
    agreements = sum(1 for r in compared if r.get("support_match"))
    n_compared = len(compared)
    mean_delta = (
        round(sum(float(r.get("mean_abs_delta") or 0) for r in compared) / n_compared, 4)
        if n_compared
        else 0.0
    )

    passed, pass_reason = evaluation_passes(
        regression_count=regressions,
        mean_abs_delta=mean_delta,
        n_compared=n_compared,
    )

    if len(compared) != len(rows):
        passed, pass_reason = False, "incomplete_comparisons"

    save_last_eval_for_library_key(
        user_id,
        library_key,
        passed=passed,
        regression_count=regressions,
        agreement_count=agreements,
        n=n_compared,
        mean_abs_delta=mean_delta,
    )

    return {
        "ok": True,
        "library_key": library_key,
        "agent_target": agent_target,
        "truncated": truncated,
        "max_startups": max_n,
        "summary": {
            "n_requested": len(ids),
            "n_compared": n_compared,
            "regression_count": regressions,
            "support_agreements": agreements,
            "mean_abs_score_delta": mean_delta,
            "passed": passed,
            "pass_reason": pass_reason,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        },
        "rows": rows,
    }
