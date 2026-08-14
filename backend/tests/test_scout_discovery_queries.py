"""Open-discovery retrieval queries are derived from the active fund thesis.

Retrieval used to run two hardcoded persona strings, so the mandate only reached
the LLM prompt and never the search itself.
"""
import pytest

from utils.scout_discovery_queries import (
    build_discovery_queries,
    build_discovery_recency_query,
    thesis_terms,
)

_THESIS = {
    "parsed_json": {
        "sectors": ["B2B SaaS", "Infrastructure", "Developer Tools"],
        "stage_focus": ["Seed", "Series A"],
        "geography": ["US", "Europe"],
        "exclusions": ["consumer social"],
    }
}

_BASELINE = [
    "market driven early-stage startup VC funding seed series traction news",
    "market driven startup customers pilots revenue growth founders team",
]


# --------------------------------------------------------------------------- #
# Fallback: unchanged behaviour without a mandate
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "thesis",
    [None, {}, {"parsed_json": None}, {"parsed_json": "nope"}, {"parsed_json": {}}],
)
def test_without_a_usable_thesis_the_original_queries_are_used(thesis):
    assert build_discovery_queries("market driven", thesis_ctx=thesis) == _BASELINE


def test_empty_mandate_lists_fall_back():
    thesis = {"parsed_json": {"sectors": [], "stage_focus": [], "geography": []}}
    assert build_discovery_queries("market driven", thesis_ctx=thesis) == _BASELINE


def test_terms_extraction_ignores_malformed_input():
    assert thesis_terms(None) == {}
    assert thesis_terms({"parsed_json": {"sectors": 5}}) == {}


# --------------------------------------------------------------------------- #
# Thesis-scoped queries
# --------------------------------------------------------------------------- #


def test_sectors_stages_and_geographies_reach_the_queries():
    queries = build_discovery_queries("market driven", thesis_ctx=_THESIS)
    joined = " || ".join(queries)
    assert '"B2B SaaS"' in joined
    assert "Seed" in joined and "Series A" in joined
    assert "US" in joined and "Europe" in joined


def test_a_persona_query_always_survives():
    """A narrow mandate must not starve the persona's point of view."""
    queries = build_discovery_queries("contrarian", thesis_ctx=_THESIS)
    assert any("contrarian" in q for q in queries)


def test_both_funding_and_traction_angles_are_covered():
    queries = build_discovery_queries("market driven", thesis_ctx=_THESIS, max_queries=6)
    joined = " || ".join(queries)
    assert "funding round raised" in joined
    assert "customers pilots revenue" in joined


def test_stage_and_geography_only_mandate_still_narrows():
    thesis = {"parsed_json": {"stage_focus": ["Pre-Seed"], "geography": ["Germany"]}}
    queries = build_discovery_queries("pain point", thesis_ctx=thesis)
    assert any("Pre-Seed" in q and "Germany" in q for q in queries)


def test_queries_are_deduped_and_capped(monkeypatch):
    monkeypatch.setenv("SCOUT_DISCOVERY_MAX_QUERIES", "2")
    queries = build_discovery_queries("market driven", thesis_ctx=_THESIS)
    assert len(queries) == 2
    assert len(set(queries)) == 2


def test_explicit_cap_overrides_the_env_default(monkeypatch):
    monkeypatch.setenv("SCOUT_DISCOVERY_MAX_QUERIES", "6")
    assert len(build_discovery_queries("market driven", thesis_ctx=_THESIS, max_queries=1)) == 1


def test_absurd_mandate_values_are_dropped():
    thesis = {"parsed_json": {"sectors": ["x" * 200, "Fintech"]}}
    joined = " || ".join(build_discovery_queries("market driven", thesis_ctx=thesis))
    assert "x" * 200 not in joined
    assert "Fintech" in joined


def test_sector_count_is_bounded():
    thesis = {"parsed_json": {"sectors": [f"Sector{i}" for i in range(10)]}}
    joined = " || ".join(build_discovery_queries("market driven", thesis_ctx=thesis))
    assert "Sector0" in joined
    assert "Sector5" not in joined


# --------------------------------------------------------------------------- #
# Recency query
# --------------------------------------------------------------------------- #


def test_recency_query_is_scoped_to_the_mandate_sector():
    assert "B2B SaaS" in build_discovery_recency_query("market driven", thesis_ctx=_THESIS)


def test_recency_query_falls_back_to_the_persona():
    assert "contrarian" in build_discovery_recency_query("contrarian", thesis_ctx=None)


def test_recency_query_keeps_its_event_keywords():
    query = build_discovery_recency_query("market driven", thesis_ctx=_THESIS)
    assert "funding round" in query and "acquisition" in query


# --------------------------------------------------------------------------- #
# Wiring
# --------------------------------------------------------------------------- #


def test_scout_sends_thesis_scoped_queries_to_retrieval(monkeypatch):
    from scout.base import Scout

    class DummyScout(Scout):
        pass

    captured = {}


    def fake_retrieve(**kwargs):
        captured.update(kwargs)
        return {
            "provider": "none",
            "retrieval_outcome": "no_results",
            "provider_diagnostics": [],
            "sources": [],
            "url_allowlist": set(),
        }

    monkeypatch.setattr("scout.base.retrieve_source_pack_merged", fake_retrieve)

    scout = DummyScout(
        scout_type="market_driven",
        system_prompt="test",
        api_key="test-key",
        tenant_user_id="user_test_123",
    )
    scout.set_fund_thesis(_THESIS)
    scout._call_llm_sync()

    joined = " || ".join(captured["queries"])
    assert '"B2B SaaS"' in joined
    assert "B2B SaaS" in captured["recency_query"]


def test_scout_without_a_thesis_keeps_the_original_queries(monkeypatch):
    from scout.base import Scout

    class DummyScout(Scout):
        pass

    captured = {}


    def fake_retrieve(**kwargs):
        captured.update(kwargs)
        return {
            "provider": "none",
            "retrieval_outcome": "no_results",
            "provider_diagnostics": [],
            "sources": [],
            "url_allowlist": set(),
        }

    monkeypatch.setattr("scout.base.retrieve_source_pack_merged", fake_retrieve)

    scout = DummyScout(
        scout_type="market_driven",
        system_prompt="test",
        api_key="test-key",
        tenant_user_id="user_test_123",
    )
    scout._call_llm_sync()

    assert captured["queries"] == _BASELINE
