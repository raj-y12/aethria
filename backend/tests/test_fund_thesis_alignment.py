"""Rule-based thesis alignment and embedding helpers (no OpenAI)."""
from fund_thesis import (
    ActiveThesis,
    _review_thesis_fields,
    rule_based_thesis_alignment,
    thesis_context_has_embeddings,
    thesis_has_embeddings,
)


def test_thesis_has_embeddings_empty():
    t = ActiveThesis(
        thesis_id="a",
        version_id="b",
        version_number=1,
        raw_text="x",
        parsed_json={},
        embedding=[],
        embedding_model="none",
    )
    assert thesis_has_embeddings(t) is False
    ctx = t.as_engine_context()
    assert ctx["embedding_model"] == "none"
    assert ctx["alignment_mode"] == "rule_based"
    assert thesis_context_has_embeddings(ctx) is False


def test_thesis_has_embeddings_nonempty():
    t = ActiveThesis(
        thesis_id="a",
        version_id="b",
        version_number=1,
        raw_text="x",
        parsed_json={},
        embedding=[0.1, 0.2],
        embedding_model="text-embedding-3-small",
    )
    assert thesis_has_embeddings(t) is True
    ctx = t.as_engine_context()
    assert ctx["alignment_mode"] == "embedding"
    assert thesis_context_has_embeddings(ctx) is True


def test_rule_based_alignment_b2b_saas_seed():
    pj = {
        "sectors": ["b2b saas"],
        "stage_focus": ["seed"],
        "geography": ["us"],
        "exclusions": ["consumer social"],
        "preferences": ["technical founders"],
    }
    scout = {
        "name": "Acme",
        "one_line": "B2B SaaS for ops; technical founders",
        "sector": "B2B SaaS",
        "problem": "x",
        "solution": "y",
        "target_users": "US enterprises",
        "why_now": "regulation",
        "funding_stage": "Seed",
    }
    out = rule_based_thesis_alignment(scout, pj)
    assert "thesis_alignment_score" in out
    assert 0.0 <= out["thesis_alignment_score"] <= 1.0
    assert out["thesis_matches_fund"] is True
    assert out["thesis_alignment_confidence"] == 0.25
    assert out["thesis_fit_points"]
    assert out["thesis_deviation_points"]


def test_rule_based_exclusion_penalty():
    pj = {
        "sectors": ["infra"],
        "stage_focus": ["series a"],
        "geography": ["europe"],
        "exclusions": ["speculative crypto"],
        "preferences": [],
    }
    scout = {
        "name": "CoinThing",
        "one_line": "speculative crypto trading",
        "sector": "Crypto",
        "problem": "p",
        "solution": "s",
        "target_users": "t",
        "why_now": "w",
        "funding_stage": "Seed",
    }
    out = rule_based_thesis_alignment(scout, pj)
    assert out["thesis_alignment_score"] < 0.6
    assert out["thesis_matches_fund"] is False


def test_review_thesis_fields_fund_alignment_fallback():
    ri = {
        "fund_thesis_alignment_score": 0.82,
        "fund_thesis_version_id": "version-abc",
    }
    score, matches, vid = _review_thesis_fields(ri)
    assert score == 0.82
    assert matches is None
    assert vid == "version-abc"


def test_review_thesis_fields_prefers_primary_score():
    ri = {
        "thesis_alignment_score": 0.55,
        "fund_thesis_alignment_score": 0.9,
        "fund_thesis_version_id": "v1",
    }
    score, _, _ = _review_thesis_fields(ri)
    assert score == 0.55
