"""Meta Agent Phase 2: evaluator metrics and reviewer preview wiring."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from meta.evaluator import (
    evaluation_passes,
    extract_baseline_for_persona,
    mean_abs_score_delta,
    verdict_downgraded,
)
from reviewer.engine import ReviewerEngine


def test_verdict_downgraded():
    assert verdict_downgraded("STRONG", "WEAK") is True
    assert verdict_downgraded("STRONG", "MEDIUM") is True
    assert verdict_downgraded("MEDIUM", "MEDIUM") is False
    assert verdict_downgraded("WEAK", "STRONG") is False


def test_mean_abs_score_delta():
    b = {"market_score": 6, "product_score": 6, "technical_score": 7, "execution_score": 5, "defensibility_score": 6}
    c = {"market_score": 8, "product_score": 6, "technical_score": 7, "execution_score": 5, "defensibility_score": 6}
    assert mean_abs_score_delta(b, c) == 0.4


def test_evaluation_passes():
    ok, reason = evaluation_passes(regression_count=0, mean_abs_delta=1.0, n_compared=3)
    assert ok and reason == "ok"
    ok, reason = evaluation_passes(regression_count=1, mean_abs_delta=0.0, n_compared=3)
    assert not ok and reason == "verdict_regression"
    ok, reason = evaluation_passes(regression_count=0, mean_abs_delta=0.0, n_compared=0)
    assert not ok and reason == "no_comparisons"


def test_extract_baseline_for_persona():
    sr = MagicMock()
    sr.reviewer_type = "SkepticalReviewer"
    sr.verdict = "MEDIUM"
    sr.market_score = 6
    sr.product_score = 6
    sr.technical_score = 6
    sr.execution_score = 6
    sr.defensibility_score = 7

    ri = MagicMock()
    ri.reviews = [sr]
    startup = MagicMock()
    startup.review_info = ri

    base = extract_baseline_for_persona(startup, "SkepticalReviewer")
    assert base["verdict"] == "MEDIUM"
    assert base["defensibility_score"] == 7
    assert extract_baseline_for_persona(startup, "DefaultReviewer") is None


@pytest.mark.asyncio
async def test_preview_persona_review_restores_prompt():
    api_key = "sk-test"
    storage = MagicMock()
    engine = ReviewerEngine(
        api_key=api_key,
        storage=storage,
        tenant_user_id="user-eval-test",
        model="gpt-4o-mini",
    )
    before = engine.reviewer.SYSTEM_PROMPT
    scout_output = {"name": "Co", "one_line": "x", "sector": "s", "problem": "p", "solution": "sol", "target_users": "u", "why_now": "n", "confidence": 0.8}

    fake_out = {
        "market_score": 5,
        "product_score": 5,
        "technical_score": 5,
        "execution_score": 5,
        "defensibility_score": 5,
        "overall_summary": "ok",
        "key_risks": [],
        "verdict": "MEDIUM",
        "diligence_red_flags": [],
        "assumption_feedback": [],
    }

    with patch.object(engine.reviewer, "review", new_callable=AsyncMock, return_value=fake_out):
        out = await engine.preview_persona_review("DefaultReviewer", scout_output, "CANDIDATE PROMPT TEXT")

    assert out is not None
    assert out.get("verdict") == "MEDIUM"
    assert engine.reviewer.SYSTEM_PROMPT == before
