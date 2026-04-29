"""
Meta Agent Phase 2: shadow reviewer evaluation against a fixed startup set.
Compares candidate prompt output to persisted per-persona SingleReview baselines.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from meta.prompt_gating import (
    REVIEWER_EVAL_AGENT_TARGETS,
    load_eval_startup_ids,
    load_prompt_library,
    save_last_eval_for_library_key,
)
from reviewer.engine import ReviewerEngine

logger = logging.getLogger(__name__)

VERDICT_RANK = {"WEAK": 0, "MEDIUM": 1, "STRONG": 2}

_DIMS = ("market_score", "product_score", "technical_score", "execution_score", "defensibility_score")


def verdict_downgraded(baseline_verdict: str, candidate_verdict: str) -> bool:
    b = VERDICT_RANK.get(str(baseline_verdict or "").upper(), 1)
    c = VERDICT_RANK.get(str(candidate_verdict or "").upper(), 1)
    return c < b


def mean_abs_score_delta(baseline: Dict[str, Any], candidate: Dict[str, Any]) -> float:
    deltas: List[float] = []
    for d in _DIMS:
        bv = baseline.get(d)
        cv = candidate.get(d)
        if bv is None or cv is None:
            continue
        try:
            deltas.append(abs(float(cv) - float(bv)))
        except (TypeError, ValueError):
            continue
    if not deltas:
        return 0.0
    return round(sum(deltas) / len(deltas), 3)


def extract_baseline_for_persona(startup, agent_target: str) -> Optional[Dict[str, Any]]:
    ri = getattr(startup, "review_info", None)
    if ri is None:
        return None
    reviews = getattr(ri, "reviews", None) or []
    for sr in reviews:
        if getattr(sr, "reviewer_type", None) == agent_target:
            out: Dict[str, Any] = {
                "verdict": sr.verdict,
                "market_score": sr.market_score,
                "product_score": sr.product_score,
                "technical_score": sr.technical_score,
                "execution_score": sr.execution_score,
            }
            if sr.defensibility_score is not None:
                out["defensibility_score"] = sr.defensibility_score
            return out
    return None


def evaluation_passes(
    *,
    regression_count: int,
    mean_abs_delta: float,
    n_compared: int,
) -> Tuple[bool, str]:
    if n_compared <= 0:
        return False, "no_comparisons"
    if regression_count > 0:
        return False, "verdict_regression"
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
    storage,
    reviewer_engine: ReviewerEngine,
    startup_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run shadow reviews for candidate prompt in library_key (reviewer agents only).
    """
    if agent_target not in REVIEWER_EVAL_AGENT_TARGETS:
        return {"ok": False, "error": "agent_target must be a reviewer persona", "rows": []}

    library = load_prompt_library(user_id)
    ent = library.get(library_key) if isinstance(library, dict) else None
    if not isinstance(ent, dict) or not str(ent.get("prompt") or "").strip():
        return {"ok": False, "error": "library_key not found or empty prompt", "rows": []}

    candidate_prompt = str(ent["prompt"])

    ids = [str(x).strip() for x in (startup_ids or load_eval_startup_ids(user_id)) if str(x).strip()]
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

    reviewer_engine._sync_thesis_to_reviewers()

    sem = asyncio.Semaphore(max(1, int(os.getenv("META_PROMPT_EVAL_CONCURRENCY", "3"))))

    async def one(sid: str) -> Dict[str, Any]:
        row: Dict[str, Any] = {"startup_id": sid, "status": "ok"}
        async with sem:
            try:
                startup = storage.get_startup(sid)
                if startup is None:
                    row["status"] = "missing_startup"
                    return row
                baseline = extract_baseline_for_persona(startup, agent_target)
                if baseline is None:
                    row["status"] = "no_baseline"
                    return row
                scout_output = ReviewerEngine._build_scout_output_payload(startup)
                cand = await reviewer_engine.preview_persona_review(
                    agent_target, scout_output, candidate_prompt
                )
                if cand is None:
                    row["status"] = "review_failed"
                    return row
                bv = str(baseline.get("verdict") or "")
                cv = str(cand.get("verdict") or cand.get("derived_verdict") or "")
                row["baseline_verdict"] = bv
                row["candidate_verdict"] = cv
                row["verdict_match"] = bv.upper() == cv.upper()
                row["regression"] = verdict_downgraded(bv, cv)
                row["mean_abs_delta"] = mean_abs_score_delta(baseline, cand)
            except Exception as e:
                logger.warning("eval row error %s: %s", sid, e)
                row["status"] = "error"
                row["error"] = str(e)[:200]
        return row

    rows = await asyncio.gather(*[one(sid) for sid in ids])

    compared = [r for r in rows if r.get("status") == "ok"]
    regressions = sum(1 for r in compared if r.get("regression"))
    agreements = sum(1 for r in compared if r.get("verdict_match"))
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
            "verdict_agreements": agreements,
            "mean_abs_score_delta": mean_delta,
            "passed": passed,
            "pass_reason": pass_reason,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        },
        "rows": rows,
    }
