"""Stable DealContextV1 digests for pipeline tracing."""
from utils.deal_context import (
    build_deal_context_v1,
    format_deal_context_digest_prompt_line,
    scout_digest_v1,
)


def test_scout_digest_v1_stable():
    scout = {
        "name": "Acme",
        "one_line": "Widgets",
        "sector": "SaaS",
        "problem": "x",
        "solution": "y",
        "target_users": "z",
        "why_now": "now",
    }
    d1 = scout_digest_v1(scout)
    d2 = scout_digest_v1(dict(scout))
    assert len(d1) == 16
    assert d1 == d2


def test_build_deal_context_v1_with_thesis_and_signals():
    scout = {"name": "Co", "one_line": "L", "sector": "S"}
    review = {"structured_signals": {"market": {"a": 1}}}
    thesis = {"version_id": "vid-9"}
    ctx = build_deal_context_v1(scout, review, thesis)
    assert ctx["version"] == "1"
    assert ctx["scout_digest"]
    assert ctx["thesis_version_id"] == "vid-9"
    assert ctx.get("structured_signals_digest")
    line = format_deal_context_digest_prompt_line(ctx)
    assert line.startswith("DEAL_CONTEXT_V1 ")
    assert "scout_digest=" in line
    assert "thesis_version_id=vid-9" in line
