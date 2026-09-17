"""Provider-neutral search interface for retrieval grounding.

Retrieval used to call one provider directly from `retrieval_grounding`, which
made the provider choice global: founder/people lookups could not be routed to a
specialised provider without changing every call site.

This module introduces a small interface with explicit categories:

    general  — open discovery and generic corroboration
    news     — recency-ranked, date-filtered coverage
    company  — company identity / profile lookups
    people   — founder and team lookups

Each category is resolved independently through the registry, so registering a
dedicated people-search provider later routes founder retrieval to it without
touching extraction logic or any other category:

    register_provider(MyPeopleProvider(), categories=["people"])

Every category defaults to the full retrieval chain — `exa → firecrawl`, with
DuckDuckGo as the keyless last resort one level up in `retrieval_grounding`.
Routing can be overridden per category from the environment, e.g.
`SEARCH_PROVIDER_PEOPLE=firecrawl`, and the chain order itself with
`RETRIEVAL_PROVIDER_ORDER`.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Literal, Optional, Protocol, Sequence, runtime_checkable

import metrics
from research.exa_client import exa_search, is_company_domain
from research.firecrawl_client import firecrawl_scrape, firecrawl_search
from research.search_results import ProviderSearchResults

logger = logging.getLogger("search_providers")

SearchCategory = Literal["general", "news", "company", "people"]

SEARCH_CATEGORIES: tuple[str, ...] = ("general", "news", "company", "people")

DEFAULT_CATEGORY: SearchCategory = "general"

# Retrieval tiers, best-first. DuckDuckGo is deliberately absent: it lives in
# `retrieval_grounding` as the keyless last resort after this whole chain fails.
DEFAULT_PROVIDER_ORDER: tuple[str, ...] = ("exa", "firecrawl")


@runtime_checkable
class SearchProvider(Protocol):
    """A search backend for one or more categories.

    Implementations return `ProviderSearchResults` — a list of
    `{title, url, snippet}` rows carrying structured `.diagnostics`, so provider
    outages stay observable instead of looking like empty result sets.
    """

    name: str
    supported_categories: frozenset

    def search(
        self,
        query: str,
        *,
        max_results: int,
        category: SearchCategory = DEFAULT_CATEGORY,
        time_range: Optional[str] = None,
        days: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        ...


class FirecrawlSearchProvider:
    """Firecrawl v2-backed provider. Supports every retrieval category."""

    name = "firecrawl"
    supported_categories = frozenset(SEARCH_CATEGORIES)

    def search(self, query: str, *, max_results: int, category: SearchCategory = DEFAULT_CATEGORY,
               time_range: Optional[str] = None, days: Optional[int] = None) -> List[Dict[str, str]]:
        topic = "news" if category == "news" else "general"
        return firecrawl_search(query=query, max_results=max_results, time_range=time_range,
                                topic=topic, days=days if topic == "news" else None)


def _enrich_with_firecrawl(rows: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Replace Exa highlights with Firecrawl page content where possible.

    Firecrawl is the canonical content layer, so the top-ranked Exa URLs are
    scraped and their markdown becomes the snippet. A URL Firecrawl could not
    fetch keeps its Exa highlight, tagged `content_provider="exa_highlight"` so a
    reader can always tell which layer produced the text.

    Note the scrape budget is bounded twice: by `EXA_ENRICH_MAX_URLS` here and by
    `FIRECRAWL_SCRAPE_MAX_URLS` inside the Firecrawl client, whichever is lower.
    """
    enabled = os.getenv("EXA_ENRICH_WITH_FIRECRAWL", "1").strip().lower() in ("1", "true", "yes")
    limit = max(0, min(int(os.getenv("EXA_ENRICH_MAX_URLS", "3")), 10))
    targets = [str(row.get("url") or "") for row in rows[:limit]] if enabled else []

    pages: Dict[str, str] = {}
    scrape_failed = False
    if targets:
        try:
            pages = {
                str(page.get("url")): str(page.get("content"))
                for page in (firecrawl_scrape(targets) or [])
                if page.get("url") and page.get("content")
            }
        except Exception as exc:  # a content-layer outage must not lose the URLs
            scrape_failed = True
            logger.warning("Exa->Firecrawl enrichment failed: %s", exc)

    enriched: List[Dict[str, Any]] = []
    for row in rows:
        url = str(row.get("url") or "")
        content = pages.get(url)
        highlight = str(row.get("highlight") or "")
        if content:
            snippet, content_provider = content, "firecrawl"
        elif highlight:
            snippet, content_provider = highlight, "exa_highlight"
        else:
            snippet, content_provider = "", "none"
        enriched.append({
            "title": str(row.get("title") or ""),
            "url": url,
            "snippet": snippet,
            "content_provider": content_provider,
            "published_date": row.get("published_date"),
            "author": row.get("author"),
            "score": row.get("score"),
        })

    domains = {u.split("/")[2] for u in (str(r.get("url") or "") for r in rows) if u.count("/") >= 2}
    company_hits = sum(1 for row in rows if is_company_domain(str(row.get("url") or "")))
    stats = {
        "unique_domains": len(domains),
        "company_domain_rate": round(company_hits / len(rows), 3) if rows else 0.0,
        "firecrawl_success_rate": round(len(pages) / len(targets), 3) if targets else 0.0,
        "firecrawl_attempted": len(targets),
        "content_fallback": "firecrawl_error" if scrape_failed else (
            "exa_highlight" if targets and len(pages) < len(targets) else None
        ),
    }
    return enriched, stats


class ExaSearchProvider:
    """Exa-backed semantic discovery, with Firecrawl supplying page content.

    Exa answers "which companies match this?" far better than a keyword index,
    but it returns links rather than text. This provider therefore does the two
    halves of the brief in one place: semantic search for the URLs, Firecrawl for
    what is on them. It never synthesises, ranks investments, or draws
    conclusions — ranking here only decides which pages are worth scraping.
    """

    name = "exa"
    supported_categories = frozenset(SEARCH_CATEGORIES)

    def search(self, query: str, *, max_results: int, category: SearchCategory = DEFAULT_CATEGORY,
               time_range: Optional[str] = None, days: Optional[int] = None) -> ProviderSearchResults:
        rows = exa_search(
            query, max_results=max_results, time_range=time_range, days=days, category=category
        )
        diagnostics = dict(getattr(rows, "diagnostics", None) or {})
        if not rows:
            return ProviderSearchResults([], diagnostics)

        enriched, stats = _enrich_with_firecrawl(list(rows))
        diagnostics.update(stats)
        metrics.observe_exa_discovery(
            query_type=str(diagnostics.get("query_type") or "unknown"),
            outcome=str(diagnostics.get("outcome") or "success"),
            fallback_reason=stats["content_fallback"],
            unique_domains=stats["unique_domains"],
            company_domain_rate=stats["company_domain_rate"],
            firecrawl_success_rate=stats["firecrawl_success_rate"],
            cost_usd=diagnostics.get("cost_usd"),
        )
        return ProviderSearchResults(enriched, diagnostics)


class ChainedSearchProvider:
    """Try each retrieval tier in order until one returns usable results.

    Order is `exa → firecrawl` by default; DuckDuckGo remains the final
    fallback and stays in `retrieval_grounding`, one level up, so a total chain
    failure still degrades to a keyless search rather than to nothing.
    """

    supported_categories = frozenset(SEARCH_CATEGORIES)

    def __init__(self, providers: Dict[str, Any]):
        self._providers = dict(providers)

    def _order(self) -> tuple[str, ...]:
        configured = [
            name
            for name in (part.strip().lower() for part in os.getenv("RETRIEVAL_PROVIDER_ORDER", "").split(","))
            if name in self._providers
        ]
        order = tuple(configured) or DEFAULT_PROVIDER_ORDER
        # A single-provider override is the rollback lever: it moves that tier to
        # the head without discarding the ones behind it.
        primary = os.getenv("RETRIEVAL_PRIMARY_PROVIDER", "").strip().lower()
        if primary in self._providers:
            order = (primary,) + tuple(name for name in order if name != primary)
        return order + tuple(name for name in DEFAULT_PROVIDER_ORDER if name not in order)

    @property
    def name(self) -> str:
        return self._order()[0]

    def search(self, query: str, *, max_results: int, category: SearchCategory = DEFAULT_CATEGORY,
               time_range: Optional[str] = None, days: Optional[int] = None) -> ProviderSearchResults:
        tiers = self._order()
        diagnostics: List[Dict[str, Any]] = []
        for tier in tiers:
            # One tier raising must not sink the ones behind it — with three tiers
            # an Exa outage would otherwise take Firecrawl down with it.
            try:
                rows = self._providers[tier].search(query, max_results=max_results, category=category,
                                                    time_range=time_range, days=days)
            except Exception as exc:
                logger.warning("retrieval tier %s raised: %s", tier, exc)
                diagnostics.append({"provider": tier, "outcome": "error",
                                    "reason": "provider_error", "result_count": 0})
                continue
            diagnostic = getattr(rows, "diagnostics", None)
            if not isinstance(diagnostic, dict):
                diagnostic = {"provider": tier, "outcome": "success" if rows else "empty",
                              "reason": None if rows else "no_usable_results", "result_count": len(rows)}
            diagnostics.append(dict(diagnostic))
            if rows:
                combined = dict(diagnostic)
                combined["provider"] = tier
                combined["tiers"] = diagnostics
                return ProviderSearchResults(list(rows), combined)
        return ProviderSearchResults([], {"provider": tiers[-1], "outcome": "empty",
                                          "reason": "no_usable_results", "result_count": 0,
                                          "tiers": diagnostics})


_EXA_PROVIDER = ExaSearchProvider()
_FIRECRAWL_PROVIDER = FirecrawlSearchProvider()
_TIER_PROVIDERS = {
    _EXA_PROVIDER.name: _EXA_PROVIDER,
    _FIRECRAWL_PROVIDER.name: _FIRECRAWL_PROVIDER,
}
_DEFAULT_PROVIDER = ChainedSearchProvider(_TIER_PROVIDERS)

# category -> provider. Every category starts on the full chain.
_REGISTRY: Dict[str, Any] = {category: _DEFAULT_PROVIDER for category in SEARCH_CATEGORIES}


def _default_by_name() -> Dict[str, Any]:
    """name -> provider, for env-based routing by provider name.

    The chain is registered under the fixed key `chain` because its `name` is
    the *current head tier*, which moves with configuration — routing a category
    to `exa` must reach the single provider, not the whole chain.
    """
    return {"chain": _DEFAULT_PROVIDER, **_TIER_PROVIDERS}


_BY_NAME: Dict[str, Any] = _default_by_name()


def normalize_category(category: Optional[str]) -> SearchCategory:
    value = str(category or "").strip().lower()
    return value if value in SEARCH_CATEGORIES else DEFAULT_CATEGORY  # type: ignore[return-value]


def register_provider(
    provider: Any,
    *,
    categories: Optional[Sequence[str]] = None,
) -> None:
    """Register `provider` as the backend for the given categories.

    With no categories, the provider is registered for every category it declares
    in `supported_categories`. Registering is idempotent and takes effect for the
    next search — nothing is cached across calls.
    """
    name = str(getattr(provider, "name", "") or "").strip()
    if not name:
        raise ValueError("search provider must define a non-empty `name`")
    if not callable(getattr(provider, "search", None)):
        raise TypeError(f"search provider {name!r} must define a callable `search`")

    supported = {
        normalize_category(c)
        for c in (getattr(provider, "supported_categories", None) or SEARCH_CATEGORIES)
    }
    targets = (
        {normalize_category(c) for c in categories} if categories is not None else supported
    )
    unsupported = targets - supported
    if unsupported:
        raise ValueError(
            f"provider {name!r} does not support categories: {sorted(unsupported)}"
        )

    _BY_NAME[name] = provider
    for category in targets:
        _REGISTRY[category] = provider
    logger.info("search provider registered name=%s categories=%s", name, sorted(targets))


def reset_providers() -> None:
    """Restore the default chained routing. Intended for tests."""
    for category in SEARCH_CATEGORIES:
        _REGISTRY[category] = _DEFAULT_PROVIDER
    _BY_NAME.clear()
    _BY_NAME.update(_default_by_name())


def _env_override(category: SearchCategory) -> Optional[Any]:
    name = os.getenv(f"SEARCH_PROVIDER_{category.upper()}", "").strip().lower()
    if not name:
        return None
    provider = _BY_NAME.get(name)
    if provider is None:
        logger.warning(
            "SEARCH_PROVIDER_%s=%s is not a registered provider; using registry default",
            category.upper(),
            name,
        )
        return None
    return provider


def get_provider(category: Optional[str] = None) -> Any:
    """Resolve the provider for a category (env override wins, then registry)."""
    cat = normalize_category(category)
    return _env_override(cat) or _REGISTRY.get(cat) or _DEFAULT_PROVIDER


def provider_name(category: Optional[str] = None) -> str:
    return str(getattr(get_provider(category), "name", "unknown"))


def provider_search(
    query: str,
    *,
    max_results: int,
    category: Optional[str] = None,
    time_range: Optional[str] = None,
    days: Optional[int] = None,
) -> List[Dict[str, str]]:
    """Run one search through the category's provider.

    A provider raising is treated as an outage: an empty result set carrying
    diagnostics is returned so the caller can fall back rather than crash.
    """
    cat = normalize_category(category)
    provider = get_provider(cat)
    try:
        return provider.search(
            query,
            max_results=max_results,
            category=cat,
            time_range=time_range,
            days=days,
        )
    except Exception as exc:
        logger.warning(
            "search provider %s failed category=%s: %s",
            getattr(provider, "name", "unknown"),
            cat,
            exc,
        )
        return ProviderSearchResults(
            [],
            {
                "provider": getattr(provider, "name", "unknown"),
                "outcome": "error",
                "reason": "provider_error",
                "result_count": 0,
            },
        )


def extract_pages(urls: List[str], timeout: Optional[float] = None) -> List[Dict[str, str]]:
    """Fetch page content for explicit URLs.

    Firecrawl is the only extraction layer now that Tavily is gone; the function
    keeps its provider-neutral name and `[{url, content}]` contract so the three
    call sites (`pipeline_runner`, `company_resolver`, `founder_resolver`) stay
    unaware of which provider reads a page.

    Best-effort by contract: an outage yields fewer pages, never an exception —
    founder and company resolution degrade to search snippets rather than failing.
    """
    clean = [u.strip() for u in urls if isinstance(u, str) and u.strip().startswith("http")]
    if not clean:
        return []

    try:
        pages = firecrawl_scrape(clean, timeout) or []
    except Exception as exc:
        logger.warning("extract_pages: firecrawl scrape failed: %s", exc)
        return []

    collected: List[Dict[str, str]] = []
    seen: set = set()
    for page in pages:
        url = str((page or {}).get("url") or "").strip()
        content = str((page or {}).get("content") or "").strip()
        if url and content and url not in seen:
            seen.add(url)
            collected.append({"url": url, "content": content})
    return collected


def search_source_pack(
    *,
    queries: List[str],
    user_id: str,
    category: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Merged source pack for `queries`, routed through the category's provider.

    Thin wrapper over `retrieval_grounding.retrieve_source_pack_merged` so callers
    that only care about *which* provider answers (e.g. the founder resolver) do
    not need to know about the merge/allowlist machinery.
    """
    from research.retrieval_grounding import retrieve_source_pack_merged

    return retrieve_source_pack_merged(
        queries=queries,
        user_id=user_id,
        category=category,
        **kwargs,
    )
