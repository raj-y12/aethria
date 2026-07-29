"""Founder resolution reads company team/about pages in full.

A company's own /team page usually names the founders outright, but a search
snippet truncates it to a sentence or two — so "readily available" team details
were being missed even though the page was already in the source pack.
"""
from typing import Any, Dict, List

import pytest

from resolver.founder_resolver import resolve_founders

_FULL_TEAM_PAGE = (
    "Meet the team behind Acme. Ada Byron, Co-founder & CEO, previously worked at "
    "Stripe. She studied at Imperial College London. "
    "Grace Hopper, Co-founder & CTO, was formerly at DeepMind."
)

_TRUNCATED_SNIPPET = "Meet the team behind Acme. We are a small team of..."


def _search(sources: List[Dict[str, str]]):
    def fake(*, queries, user_id, **kwargs):
        return {
            "provider": "tavily",
            "sources": sources,
            "url_allowlist": {s["url"] for s in sources},
        }

    return fake


@pytest.fixture
def extract(monkeypatch):
    """Stub Tavily extract; records requested URLs."""
    state: Dict[str, Any] = {"urls": [], "pages": []}

    def fake_extract(urls, timeout=None):
        state["urls"].extend(urls)
        return state["pages"]

    monkeypatch.setattr("utils.tavily_client.tavily_extract", fake_extract)
    return state


def test_full_team_page_replaces_a_truncated_snippet(extract):
    extract["pages"] = [{"url": "https://acme.com/team", "content": _FULL_TEAM_PAGE}]
    sources = [
        {"title": "Acme — Team", "url": "https://acme.com/team", "snippet": _TRUNCATED_SNIPPET},
    ]

    resolution = resolve_founders(
        "Acme", user_id="u1", website="acme.com", search=_search(sources)
    )

    assert extract["urls"] == ["https://acme.com/team"]
    by_name = {f.name: f for f in resolution.founders}
    assert set(by_name) == {"Ada Byron", "Grace Hopper"}
    assert by_name["Ada Byron"].role == "Co-founder & CEO"
    assert by_name["Ada Byron"].previous_employment == ["Stripe"]
    assert by_name["Ada Byron"].education == ["Imperial College London"]
    assert by_name["Grace Hopper"].previous_employment == ["DeepMind"]


def test_without_extraction_the_truncated_snippet_finds_nobody(monkeypatch):
    """Baseline: this is the behaviour the extraction step exists to fix."""
    monkeypatch.setenv("FOUNDER_TEAM_PAGE_EXTRACTION", "false")
    sources = [
        {"title": "Acme — Team", "url": "https://acme.com/team", "snippet": _TRUNCATED_SNIPPET},
    ]
    resolution = resolve_founders(
        "Acme", user_id="u1", website="acme.com", search=_search(sources)
    )
    assert resolution.founders == []


def test_conventional_paths_are_tried_when_no_team_page_was_retrieved(extract):
    extract["pages"] = [{"url": "https://acme.com/team", "content": _FULL_TEAM_PAGE}]
    sources = [{"title": "Acme", "url": "https://acme.com/", "snippet": "We build things."}]

    resolution = resolve_founders(
        "Acme", user_id="u1", website="acme.com", search=_search(sources)
    )

    assert "https://acme.com/team" in extract["urls"]
    assert [f.name for f in resolution.founders] == ["Ada Byron", "Grace Hopper"]


def test_extracted_page_not_already_in_the_pack_is_added_as_evidence(extract):
    extract["pages"] = [{"url": "https://acme.com/about", "content": _FULL_TEAM_PAGE}]
    sources = [{"title": "Acme", "url": "https://acme.com/", "snippet": "We build things."}]

    resolution = resolve_founders(
        "Acme", user_id="u1", website="acme.com", search=_search(sources)
    )

    evidence_urls = {e.url for f in resolution.founders for e in f.evidence}
    assert "https://acme.com/about" in evidence_urls


@pytest.mark.parametrize(
    "path", ["/team", "/about", "/about-us", "/people", "/leadership", "/our-team"]
)
def test_team_page_paths_are_recognised(extract, path):
    url = f"https://acme.com{path}"
    extract["pages"] = [{"url": url, "content": _FULL_TEAM_PAGE}]
    sources = [{"title": "Acme", "url": url, "snippet": _TRUNCATED_SNIPPET}]

    resolve_founders("Acme", user_id="u1", website="acme.com", search=_search(sources))
    assert url in extract["urls"]


def test_offsite_pages_are_never_extracted(extract):
    """Only the company's own domain is fetched — not arbitrary third-party URLs."""
    sources = [
        {"title": "About us", "url": "https://randomblog.example/about", "snippet": "x"},
    ]
    resolve_founders("Acme", user_id="u1", website="acme.com", search=_search(sources))
    assert all("randomblog.example" not in u for u in extract["urls"])


def test_extraction_is_skipped_without_a_website(extract):
    sources = [{"title": "Acme", "url": "https://acme.com/team", "snippet": _TRUNCATED_SNIPPET}]
    resolve_founders("Acme", user_id="u1", search=_search(sources))
    assert extract["urls"] == []


def test_extraction_can_be_disabled(monkeypatch, extract):
    monkeypatch.setenv("FOUNDER_TEAM_PAGE_EXTRACTION", "false")
    sources = [{"title": "Acme", "url": "https://acme.com/team", "snippet": _TRUNCATED_SNIPPET}]
    resolve_founders("Acme", user_id="u1", website="acme.com", search=_search(sources))
    assert extract["urls"] == []


def test_page_budget_is_bounded(monkeypatch, extract):
    monkeypatch.setenv("FOUNDER_TEAM_PAGE_MAX", "1")
    sources = [
        {"title": "t", "url": "https://acme.com/team", "snippet": "x"},
        {"title": "a", "url": "https://acme.com/about", "snippet": "x"},
        {"title": "p", "url": "https://acme.com/people", "snippet": "x"},
    ]
    resolve_founders("Acme", user_id="u1", website="acme.com", search=_search(sources))
    assert len(extract["urls"]) == 1


def test_extraction_failure_is_non_fatal(monkeypatch):
    def boom(urls, timeout=None):
        raise RuntimeError("extract down")

    monkeypatch.setattr("utils.tavily_client.tavily_extract", boom)
    sources = [
        {
            "title": "Acme — Team",
            "url": "https://acme.com/team",
            "snippet": "Ada Byron, Founder & CEO.",
        }
    ]

    resolution = resolve_founders(
        "Acme", user_id="u1", website="acme.com", search=_search(sources)
    )

    # Falls back to the original snippet rather than losing the founder.
    assert [f.name for f in resolution.founders] == ["Ada Byron"]


def test_stage_log_records_the_team_page_read(extract):
    extract["pages"] = [{"url": "https://acme.com/team", "content": _FULL_TEAM_PAGE}]
    sources = [{"title": "t", "url": "https://acme.com/team", "snippet": _TRUNCATED_SNIPPET}]

    resolution = resolve_founders(
        "Acme", user_id="u1", website="acme.com", search=_search(sources)
    )

    stages = [s.stage for s in resolution.stage_log]
    assert "team_pages" in stages
    assert resolution.stage_log[stages.index("team_pages")].sources_found == 1


def test_no_team_page_stage_when_nothing_was_fetched(extract):
    extract["pages"] = []
    sources = [{"title": "t", "url": "https://acme.com/", "snippet": "x"}]

    resolution = resolve_founders(
        "Acme", user_id="u1", website="acme.com", search=_search(sources)
    )

    assert "team_pages" not in [s.stage for s in resolution.stage_log]
