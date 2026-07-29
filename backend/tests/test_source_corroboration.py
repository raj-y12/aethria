"""Supplying a company website must anchor the pack, not shrink it to one page.

The scout lookup path used to drop every source whose host was not the supplied
domain, so providing a website left the model with the company's own homepage and
nothing else — no funding coverage, no team reporting, no profile pages.
"""
import pytest

from utils.source_corroboration import (
    TRUSTED_CORROBORATION_DOMAINS,
    filter_sources_to_anchor,
    keep_source_for_anchor,
    source_mentions_company,
)

_ANCHOR = "acme.com"

_HOME = {"title": "Acme — Home", "url": "https://acme.com/", "snippet": "We build things."}
_TEAM = {"title": "Acme — Team", "url": "https://acme.com/team", "snippet": "Our team."}
_SUB = {"title": "Acme blog", "url": "https://blog.acme.com/post", "snippet": "News."}
_NEWS = {
    "title": "Acme raises $8M",
    "url": "https://techcrunch.com/acme-seed",
    "snippet": "Acme raised $8M led by Index.",
}
_LINKEDIN = {
    "title": "Acme | LinkedIn",
    "url": "https://linkedin.com/company/acme",
    "snippet": "Acme, 42 employees.",
}
_OTHER_STARTUP = {
    "title": "Zzz raises $2M",
    "url": "https://techcrunch.com/zzz",
    "snippet": "Zzz raised $2M.",
}
_UNRELATED = {
    "title": "Acme Diner",
    "url": "https://randomblog.example/diner",
    "snippet": "A diner in Ohio.",
}


def _urls(sources):
    return [s["url"] for s in sources]


# --------------------------------------------------------------------------- #
# The regression
# --------------------------------------------------------------------------- #


def test_corroborating_sources_survive_an_anchor():
    kept = filter_sources_to_anchor(
        [_HOME, _NEWS, _LINKEDIN], anchor_host=_ANCHOR, company_name="Acme"
    )
    assert _urls(kept) == [_HOME["url"], _NEWS["url"], _LINKEDIN["url"]]


def test_anchor_sources_are_ordered_first():
    kept = filter_sources_to_anchor(
        [_NEWS, _HOME, _LINKEDIN, _TEAM], anchor_host=_ANCHOR, company_name="Acme"
    )
    assert _urls(kept)[:2] == [_HOME["url"], _TEAM["url"]]


def test_subdomains_count_as_the_anchor():
    kept = filter_sources_to_anchor([_SUB], anchor_host=_ANCHOR, company_name="Acme")
    assert _urls(kept) == [_SUB["url"]]


# --------------------------------------------------------------------------- #
# Disambiguation is still enforced
# --------------------------------------------------------------------------- #


def test_unrelated_hosts_are_dropped():
    kept = filter_sources_to_anchor(
        [_HOME, _UNRELATED], anchor_host=_ANCHOR, company_name="Acme"
    )
    assert _urls(kept) == [_HOME["url"]]


def test_trusted_domain_about_a_different_company_is_dropped():
    """Being TechCrunch is not enough — the article must be about this company."""
    kept = filter_sources_to_anchor(
        [_HOME, _OTHER_STARTUP], anchor_host=_ANCHOR, company_name="Acme"
    )
    assert _urls(kept) == [_HOME["url"]]


def test_a_source_naming_the_anchor_domain_is_kept_without_a_name_match():
    source = {
        "title": "Funding roundup",
        "url": "https://techcrunch.com/roundup",
        "snippet": "Also of note: acme.com closed a round.",
    }
    assert keep_source_for_anchor(source, anchor_host=_ANCHOR, company_name="Zeta") is True


def test_multi_word_company_needs_all_tokens():
    source = {
        "title": "Dark raises",
        "url": "https://techcrunch.com/dark",
        "snippet": "Dark raised money.",
    }
    assert (
        source_mentions_company(source, company_name="Dark Matter Labs", anchor_host=None)
        is False
    )
    source["snippet"] = "Dark Matter Labs raised money."
    assert (
        source_mentions_company(source, company_name="Dark Matter Labs", anchor_host=None)
        is True
    )


# --------------------------------------------------------------------------- #
# Edges
# --------------------------------------------------------------------------- #


def test_no_anchor_keeps_everything():
    sources = [_HOME, _NEWS, _UNRELATED]
    kept = filter_sources_to_anchor(sources, anchor_host=None, company_name="Acme")
    assert _urls(kept) == _urls(sources)


def test_malformed_rows_are_skipped():
    kept = filter_sources_to_anchor(
        [_HOME, None, "nope", {}], anchor_host=_ANCHOR, company_name="Acme"
    )
    assert _urls(kept) == [_HOME["url"]]


def test_known_corroboration_domains_cover_news_and_databases():
    for domain in ("techcrunch.com", "crunchbase.com", "linkedin.com", "reuters.com"):
        assert domain in TRUSTED_CORROBORATION_DOMAINS


# --------------------------------------------------------------------------- #
# Wiring: the scout lookup path
# --------------------------------------------------------------------------- #


def test_scout_lookup_pack_keeps_corroboration(monkeypatch):
    from scout.base import Scout

    class DummyScout(Scout):
        pass

    scout = DummyScout(
        scout_type="market_driven",
        system_prompt="t",
        api_key="k",
        tenant_user_id="user_test_123",
    )
    monkeypatch.setattr(DummyScout, "_fetch_explicit_website_snippet", lambda self, url: "Title: Acme")

    out = scout._add_explicit_website_source(
        {"sources": [_HOME, _NEWS, _LINKEDIN, _UNRELATED], "url_allowlist": set()},
        company_name="Acme",
        website_hint=_ANCHOR,
    )
    urls = _urls(out["sources"])
    assert _NEWS["url"] in urls
    assert _LINKEDIN["url"] in urls
    assert _UNRELATED["url"] not in urls
    # The allowlist must grow with the retained sources, or citations to them get pruned.
    assert _NEWS["url"] in out["url_allowlist"]


def test_reviewer_and_scout_paths_agree(monkeypatch):
    from utils.reviewer_gap_retrieval import _restrict_pack_to_lookup_website

    pack = {"sources": [_HOME, _NEWS, _LINKEDIN, _UNRELATED], "url_allowlist": set()}
    out = _restrict_pack_to_lookup_website(
        pack, {"name": "Acme", "lookup_website": _ANCHOR}
    )
    urls = _urls(out["sources"])
    assert _NEWS["url"] in urls and _LINKEDIN["url"] in urls
    assert _UNRELATED["url"] not in urls
