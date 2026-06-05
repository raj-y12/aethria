"""The anti-hallucination contract for extracted financials.

Every test here encodes a way the scout LLM could fabricate or mis-attribute a
financial figure, and asserts the deterministic gate drops it. A regression in any
of these is a trust failure, so they are intentionally strict.
"""

from utils.financials_grounding import ground_financials, verify_proposal, _build_sources_by_url


def _pack(*sources):
    urls = {s["url"] for s in sources}
    return {"sources": list(sources), "url_allowlist": urls}


SRC = {
    "source_id": "S1",
    "title": "TechCrunch",
    "url": "https://techcrunch.com/acme-raises",
    "snippet": "Acme raised a $5M Series A in 2024 led by Sequoia. The round valued Acme at $20M post-money.",
}


# ─────────────────────────── grounded values are kept ───────────────────────────

def test_grounded_value_is_kept():
    out = ground_financials(
        {"financials": {
            "funding_history": {
                "value": "$5M Series A (2024)",
                "quote": "Acme raised a $5M Series A in 2024 led by Sequoia.",
                "source_url": "https://techcrunch.com/acme-raises",
            },
        }},
        _pack(SRC),
    )
    assert out["funding_history"] == "$5M Series A (2024)"
    assert out["funding_missing"] is False


def test_money_scale_synonyms_match_canonically():
    # value says "$5 million", source/quote says "$5M" — same magnitude must verify.
    out = ground_financials(
        {"financials": {
            "valuation_est": {
                "value": "$20 million post-money",
                "quote": "The round valued Acme at $20M post-money.",
                "source_url": "https://techcrunch.com/acme-raises",
            },
        }},
        _pack(SRC),
    )
    assert out["valuation_est"] == "$20 million post-money"
    assert out["valuation_missing"] is False


def test_non_numeric_value_grounded_by_wording():
    src = {**SRC, "snippet": "The startup holds two patents pending for its core process."}
    out = ground_financials(
        {"financials": {
            "ip_status": {
                "value": "patents pending",
                "quote": "The startup holds two patents pending for its core process.",
                "source_url": SRC["url"],
            },
        }},
        _pack(src),
    )
    assert out["ip_status"] == "patents pending"


# ─────────────────────────── hallucinations are dropped ─────────────────────────

def test_fabricated_quote_is_dropped():
    # The quote never appears in any source snippet → drop.
    out = ground_financials(
        {"financials": {
            "valuation_est": {
                "value": "$80M post-money",
                "quote": "Acme reached a $80M valuation in its latest round.",
                "source_url": SRC["url"],
            },
        }},
        _pack(SRC),
    )
    assert out["valuation_est"] is None
    assert out["valuation_missing"] is True


def test_figure_not_in_quote_is_dropped():
    # Quote is real, but the model attached a different number than the quote supports.
    out = ground_financials(
        {"financials": {
            "funding_history": {
                "value": "$50M Series A (2024)",  # quote says $5M, not $50M
                "quote": "Acme raised a $5M Series A in 2024 led by Sequoia.",
                "source_url": SRC["url"],
            },
        }},
        _pack(SRC),
    )
    assert out["funding_history"] is None
    assert out["funding_missing"] is True


def test_non_allowlisted_source_is_dropped():
    out = ground_financials(
        {"financials": {
            "valuation_est": {
                "value": "$20M post-money",
                "quote": "The round valued Acme at $20M post-money.",
                "source_url": "https://random-blog.example/rumor",  # not in allowlist
            },
        }},
        _pack(SRC),
    )
    assert out["valuation_est"] is None
    assert out["valuation_missing"] is True


def test_url_in_allowlist_but_quote_from_other_source_is_dropped():
    # Two allowlisted sources; the figure lives in S2 but is cited against S1.
    s2 = {"source_id": "S2", "title": "Blog", "url": "https://other.com/x",
          "snippet": "Unrelated coverage with no funding figures."}
    out = ground_financials(
        {"financials": {
            "valuation_est": {
                "value": "$20M post-money",
                "quote": "The round valued Acme at $20M post-money.",
                "source_url": "https://other.com/x",  # quote isn't in this source
            },
        }},
        _pack(SRC, s2),
    )
    assert out["valuation_est"] is None


def test_missing_or_malformed_proposals_drop_cleanly():
    for bad in (None, {}, "just a string", {"value": "$5M"}, {"value": "", "quote": "x", "source_url": "y"}):
        assert verify_proposal(bad, {"techcrunch.com/acme-raises": "..."}) is None


def test_no_financials_key_marks_all_missing():
    out = ground_financials({"name": "Acme"}, _pack(SRC))
    assert out["funding_history"] is None and out["funding_missing"] is True
    assert out["valuation_est"] is None and out["valuation_missing"] is True
    assert out["traction_metrics"] is None and out["revenue_missing"] is True
    assert out["ip_status"] is None  # ip has no missing flag


def test_trivially_short_quote_is_rejected():
    out = ground_financials(
        {"financials": {
            "traction_metrics": {"value": "$2M ARR", "quote": "$2M", "source_url": SRC["url"]},
        }},
        _pack(SRC),
    )
    # An 8-char-minimum guards against a 1-token "quote" that trivially substring-matches.
    assert out["traction_metrics"] is None


def test_url_normalization_tolerates_www_and_trailing_slash():
    src = {**SRC, "url": "https://www.techcrunch.com/acme-raises/"}
    out = ground_financials(
        {"financials": {
            "funding_history": {
                "value": "$5M Series A",
                "quote": "Acme raised a $5M Series A in 2024 led by Sequoia.",
                "source_url": "http://techcrunch.com/acme-raises",  # different scheme/www/slash
            },
        }},
        _pack(src),
    )
    assert out["funding_history"] == "$5M Series A"


def test_sources_by_url_excludes_non_allowlisted():
    pack = {
        "sources": [SRC, {"source_id": "S2", "title": "x", "url": "https://evil.com", "snippet": "fake $99M"}],
        "url_allowlist": {SRC["url"]},  # evil.com not allowlisted
    }
    by_url = _build_sources_by_url(pack)
    assert "techcrunch.com/acme-raises" in by_url
    assert "evil.com" not in by_url
