"""Provider-neutral search interface for retrieval grounding.

Retrieval used to call Tavily directly from `retrieval_grounding`, which made the
provider choice global: founder/people lookups could not be routed to a
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

Tavily remains the initial (and default) implementation for every category.
Routing can also be overridden per category from the environment, e.g.
`SEARCH_PROVIDER_PEOPLE=tavily`.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Literal, Optional, Protocol, Sequence, runtime_checkable

import metrics
from utils.firecrawl_client import firecrawl_search
from utils.tavily_client import ProviderSearchResults, tavily_search

logger = logging.getLogger("search_providers")

SearchCategory = Literal["general", "news", "company", "people"]

SEARCH_CATEGORIES: tuple[str, ...] = ("general", "news", "company", "people")

DEFAULT_CATEGORY: SearchCategory = "general"


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


class TavilySearchProvider:
    """Tavily-backed provider. Supports every category.

    Category only affects the request shape, never the returned row shape:
    `news` maps to Tavily's recency-ranked news topic; the rest use the general
    topic. People/company searches are ordinary web searches today — the point of
    the category is that they are *routable* elsewhere.
    """

    name = "tavily"
    supported_categories = frozenset(SEARCH_CATEGORIES)

    def search(
        self,
        query: str,
        *,
        max_results: int,
        category: SearchCategory = DEFAULT_CATEGORY,
        time_range: Optional[str] = None,
        days: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        topic = "news" if category == "news" else "general"
        started = time.monotonic()
        try:
            rows = tavily_search(
                query=query,
                max_results=max_results,
                time_range=time_range,
                topic=topic,
                days=days if topic == "news" else None,
            )
            diagnostic = getattr(rows, "diagnostics", {})
            metrics.observe_retrieval_provider(
                provider="tavily",
                outcome=str(diagnostic.get("outcome", "success" if rows else "empty")),
                result_count=len(rows),
                extraction_ok=bool(rows),
                latency_seconds=time.monotonic() - started,
                credits=None,
            )
            return rows
        except Exception:
            metrics.observe_retrieval_provider(
                provider="tavily", outcome="error", result_count=0, extraction_ok=False,
                latency_seconds=time.monotonic() - started, credits=None,
            )
            raise


class FirecrawlSearchProvider:
    """Firecrawl v2-backed provider. Supports every retrieval category."""

    name = "firecrawl"
    supported_categories = frozenset(SEARCH_CATEGORIES)

    def search(self, query: str, *, max_results: int, category: SearchCategory = DEFAULT_CATEGORY,
               time_range: Optional[str] = None, days: Optional[int] = None) -> List[Dict[str, str]]:
        topic = "news" if category == "news" else "general"
        return firecrawl_search(query=query, max_results=max_results, time_range=time_range,
                                topic=topic, days=days if topic == "news" else None)


class ChainedSearchProvider:
    """Try the configured primary provider, then the other retrieval tier."""

    supported_categories = frozenset(SEARCH_CATEGORIES)

    def __init__(self, firecrawl: FirecrawlSearchProvider, tavily: TavilySearchProvider):
        self._providers = {"firecrawl": firecrawl, "tavily": tavily}

    @property
    def name(self) -> str:
        configured = os.getenv("RETRIEVAL_PRIMARY_PROVIDER", "firecrawl").strip().lower()
        return configured if configured in self._providers else "firecrawl"

    def search(self, query: str, *, max_results: int, category: SearchCategory = DEFAULT_CATEGORY,
               time_range: Optional[str] = None, days: Optional[int] = None) -> ProviderSearchResults:
        primary = self.name
        tiers = (primary, "tavily" if primary == "firecrawl" else "firecrawl")
        diagnostics: List[Dict[str, Any]] = []
        for tier in tiers:
            rows = self._providers[tier].search(query, max_results=max_results, category=category,
                                                time_range=time_range, days=days)
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


_FIRECRAWL_PROVIDER = FirecrawlSearchProvider()
_TAVILY_PROVIDER = TavilySearchProvider()
_DEFAULT_PROVIDER = ChainedSearchProvider(_FIRECRAWL_PROVIDER, _TAVILY_PROVIDER)

# category -> provider. Every category starts on Tavily.
_REGISTRY: Dict[str, Any] = {category: _DEFAULT_PROVIDER for category in SEARCH_CATEGORIES}

# name -> provider, for env-based routing by provider name.
_BY_NAME: Dict[str, Any] = {
    _DEFAULT_PROVIDER.name: _DEFAULT_PROVIDER,
    _FIRECRAWL_PROVIDER.name: _FIRECRAWL_PROVIDER,
    _TAVILY_PROVIDER.name: _TAVILY_PROVIDER,
}


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
    _BY_NAME[_DEFAULT_PROVIDER.name] = _DEFAULT_PROVIDER
    _BY_NAME[_FIRECRAWL_PROVIDER.name] = _FIRECRAWL_PROVIDER
    _BY_NAME[_TAVILY_PROVIDER.name] = _TAVILY_PROVIDER


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
    """Fetch page content for explicit URLs, provider-neutral.

    Mirrors the search chain: the configured primary tier runs first and the other
    tier backfills only the URLs it did not return. The contract is unchanged from
    `tavily_extract` — `[{url, content}]`, best-effort, failures dropped — so call
    sites need no other change.
    """
    from utils.firecrawl_client import firecrawl_scrape
    from utils.tavily_client import tavily_extract

    clean = [u.strip() for u in urls if isinstance(u, str) and u.strip().startswith("http")]
    if not clean:
        return []

    primary = os.getenv("RETRIEVAL_PRIMARY_PROVIDER", "firecrawl").strip().lower()
    tiers = (
        (tavily_extract, firecrawl_scrape)
        if primary == "tavily"
        else (firecrawl_scrape, tavily_extract)
    )

    collected: List[Dict[str, str]] = []
    seen: set = set()
    for tier in tiers:
        pending = [u for u in clean if u not in seen]
        if not pending:
            break
        try:
            pages = tier(pending, timeout) or []
        except Exception as exc:  # one tier's outage must not sink extraction
            logger.warning("extract tier %s failed: %s", getattr(tier, "__name__", "?"), exc)
            continue
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
    from utils.retrieval_grounding import retrieve_source_pack_merged

    return retrieve_source_pack_merged(
        queries=queries,
        user_id=user_id,
        category=category,
        **kwargs,
    )
