"""
Scout retrieval grounding: provider selection, source normalization, and prompt context.
"""
from __future__ import annotations

import logging
import os
import re
import ssl
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen
from typing import Any, Dict, List, Set

import certifi

from utils.reference_verify import extract_http_urls, normalize_url_for_match
from utils.search_providers import normalize_category, provider_name, provider_search
from utils.tavily_client import ProviderSearchResults
from security.prompt_safety import flag_prompt_injection, isolate_untrusted_text, prompt_safety_instruction

logger = logging.getLogger("retrieval_grounding")


def _fallback_search(query: str, max_results: int) -> List[Dict[str, str]]:
    """Small no-key fallback for provider outages; results stay reference-validated."""
    if os.getenv("RETRIEVAL_FALLBACK_ENABLED", "1").strip().lower() in {"0", "false", "no"}:
        return ProviderSearchResults(
            [],
            {
                "provider": "duckduckgo_html_fallback",
                "outcome": "disabled",
                "reason": "fallback_disabled",
                "result_count": 0,
            },
        )
    # DDG's /html endpoint increasingly serves an anti-bot challenge to cloud
    # IPs. The lightweight /lite endpoint is intended for simple clients and
    # returns stable result-link markup without JavaScript.
    urls = (
        f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}",
        f"https://html.duckduckgo.com/html/?q={quote_plus(query)}",
    )
    request_headers = {"User-Agent": "Mozilla/5.0 (compatible; AethriaResearch/1.0)"}
    html = ""
    challenge_seen = False
    request_failed = False
    try:
        context = ssl.create_default_context(cafile=certifi.where())
        for url in urls:
            try:
                request = Request(url, headers=request_headers)
                with urlopen(request, timeout=8.0, context=context) as response:
                    candidate = response.read().decode("utf-8", errors="replace")
                # Do not parse DDG's challenge page as an empty successful search.
                if "challenge-form" in candidate or "anomaly.js" in candidate:
                    challenge_seen = True
                    continue
                html = candidate
                break
            except Exception as exc:
                request_failed = True
                logger.debug("retrieval fallback endpoint failed (%s): %s", url, exc)
    except Exception as exc:
        logger.warning("retrieval fallback failed: %s", exc)
        return ProviderSearchResults(
            [],
            {
                "provider": "duckduckgo_html_fallback",
                "outcome": "error",
                "reason": "request_error",
                "result_count": 0,
            },
        )
    if not html:
        logger.warning("retrieval fallback returned no usable results")
        reason = "challenge_response" if challenge_seen else "request_error" if request_failed else "no_usable_results"
        return ProviderSearchResults(
            [],
            {
                "provider": "duckduckgo_html_fallback",
                "outcome": "error" if reason != "no_usable_results" else "empty",
                "reason": reason,
                "result_count": 0,
            },
        )

    rows: List[Dict[str, str]] = []
    # Lite currently emits class='result-link'; retain support for the older
    # /html result__a markup in case that endpoint becomes available again.
    patterns = (
        re.compile(
            r"<a[^>]+href=['\"]([^'\"]+)['\"][^>]+class=['\"]result-link['\"][^>]*>(.*?)</a>",
            re.IGNORECASE | re.DOTALL,
        ),
        re.compile(
            r'<a[^>]+class=[\"\']result__a[\"\'][^>]+href=[\"\']([^\"\']+)[\"\'][^>]*>(.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        ),
    )
    matches = []
    for pattern in patterns:
        matches = pattern.findall(html)
        if matches:
            break
    for href, title_html in matches:
        clean_url = unescape(href.strip())
        if clean_url.startswith("//"):
            clean_url = f"https:{clean_url}"
        parsed = urlparse(clean_url)
        if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
            clean_url = unquote(parse_qs(parsed.query).get("uddg", [""])[0]).strip()
        title = unescape(re.sub(r"<[^>]+>", "", title_html)).strip()
        if not clean_url.startswith(("http://", "https://")) or not title:
            continue
        rows.append({"title": title, "url": clean_url, "snippet": ""})
        if len(rows) >= max_results:
            break
    return ProviderSearchResults(
        rows,
        {
            "provider": "duckduckgo_html_fallback",
            "outcome": "success" if rows else "empty",
            "reason": None if rows else "no_usable_results",
            "result_count": len(rows),
        },
    )


def _diagnostic_for_rows(
    rows: List[Dict[str, str]],
    *,
    provider: str,
    query: str,
) -> Dict[str, Any]:
    diagnostic = getattr(rows, "diagnostics", None)
    if not isinstance(diagnostic, dict):
        diagnostic = {
            "provider": provider,
            "outcome": "success" if rows else "empty",
            "reason": None if rows else "no_usable_results",
            "result_count": len(rows),
        }
    else:
        diagnostic = dict(diagnostic)
        diagnostic.setdefault("provider", provider)
        diagnostic.setdefault("result_count", len(rows))
    diagnostic["query"] = query
    return diagnostic


def _snippet_char_cap() -> int:
    raw = os.getenv("RETRIEVAL_SNIPPET_MAX_CHARS", "2800")
    try:
        n = int(raw)
    except ValueError:
        n = 2800
    return max(400, min(n, 12000))


def _default_max_results() -> int:
    raw = os.getenv("SCOUT_RETRIEVAL_MAX_RESULTS", "10")
    try:
        n = int(raw)
    except ValueError:
        n = 10
    return max(3, min(n, 15))


def _source_id(i: int) -> str:
    return f"S{i + 1}"


# Retrieval is blocking HTTP, one query at a time. A single lookup issues a dozen
# or more searches, so running them serially dominated end-to-end latency. The
# pool is module-level and bounded: per-call pools would multiply threads across
# concurrent pipeline cycles.
_QUERY_EXECUTOR = ThreadPoolExecutor(
    max_workers=8,
    thread_name_prefix="retrieval-query",
)


def _query_concurrency() -> int:
    """How many retrieval queries may be in flight at once. 1 == sequential."""
    raw = os.getenv("RETRIEVAL_QUERY_CONCURRENCY", "4")
    try:
        n = int(raw)
    except ValueError:
        n = 4
    return max(1, min(n, 8))


def _run_query_wave(
    queries: List[str],
    *,
    user_id: str,
    max_results: int,
    category: str,
) -> List[Dict[str, Any]]:
    """Run queries concurrently, returning packs in the ORIGINAL query order.

    Order matters: the merged pack keeps the first occurrence of each URL, so
    preserving submission order keeps results deterministic and identical to the
    sequential path.
    """
    if not queries:
        return []
    if len(queries) == 1 or _query_concurrency() == 1:
        return [
            retrieve_source_pack(
                query=q, user_id=user_id, max_results=max_results, category=category
            )
            for q in queries
        ]
    return list(
        _QUERY_EXECUTOR.map(
            lambda q: retrieve_source_pack(
                query=q, user_id=user_id, max_results=max_results, category=category
            ),
            queries,
        )
    )


def _normalize_sources(raw_results: List[Dict[str, str]]) -> List[Dict[str, str]]:
    cap = _snippet_char_cap()
    out: List[Dict[str, str]] = []
    for i, row in enumerate(raw_results):
        title = str(row.get("title") or "").strip()
        url = str(row.get("url") or "").strip()
        snippet = str(row.get("snippet") or "").strip()
        if not title or not url:
            continue
        if len(snippet) > cap:
            snippet = snippet[:cap]
        out.append(
            {
                "source_id": _source_id(i),
                "title": title,
                "url": url,
                "snippet": snippet,
            }
        )
    return out


def retrieve_source_pack(
    *,
    query: str,
    user_id: str,
    max_results: int | None = None,
    time_range: str | None = None,
    topic: str | None = None,
    days: int | None = None,
    category: str | None = None,
) -> Dict[str, Any]:
    """
    Build retrieval source pack with provider metadata and URL allowlist.

    time_range: optional recency filter ("day"|"week"|"month"|"year").
    topic/days: optional news-topic recency controls. `topic="news"` is accepted
    for backwards compatibility and is equivalent to category="news".
    category: which SearchProvider answers this query (general/news/company/people).
    """
    if max_results is None:
        max_results = _default_max_results()
    # A caller asking for the news topic is asking for the news category; keep the
    # legacy `topic` argument working for existing call sites.
    effective_category = normalize_category(
        category or ("news" if str(topic or "").strip().lower() == "news" else None)
    )
    primary_provider = provider_name(effective_category)
    used_provider = "none"
    raw: List[Dict[str, str]] = provider_search(
        query,
        max_results=max_results,
        category=effective_category,
        time_range=time_range,
        days=days,
    )
    provider_diagnostics = [
        _diagnostic_for_rows(raw, provider=primary_provider, query=query)
    ]
    if not raw:
        raw = _fallback_search(query, max_results)
        provider_diagnostics.append(
            _diagnostic_for_rows(
                raw,
                provider="duckduckgo_html_fallback",
                query=query,
            )
        )
        if raw:
            used_provider = "duckduckgo_html_fallback"
    else:
        used_provider = primary_provider

    sources = _normalize_sources(raw)
    allowlist: Set[str] = {s["url"] for s in sources if s.get("url")}
    normalized_allowlist = sorted(
        {
            normalize_url_for_match(url)
            for url in allowlist
            if isinstance(url, str) and normalize_url_for_match(url)
        }
    )
    logger.info("DEBUG retrieval normalized_allowlist=%s", normalized_allowlist)
    logger.info(
        "retrieval_grounding: provider=%s category=%s query=%s results=%d",
        used_provider,
        effective_category,
        query[:100],
        len(sources),
    )
    return {
        "provider": used_provider,
        "category": effective_category,
        "retrieval_outcome": "sources_found" if sources else "no_results",
        "provider_diagnostics": provider_diagnostics,
        "query": query,
        "sources": sources,
        "url_allowlist": allowlist,
    }


def retrieve_source_pack_merged(
    *,
    queries: List[str],
    user_id: str,
    max_per_query: int | None = None,
    max_total_sources: int | None = None,
    recency_query: str | None = None,
    recency_time_range: str | None = None,
    category: str | None = None,
) -> Dict[str, Any]:
    """
    Run retrieval for several queries, merge by normalized URL (first occurrence wins),
    cap total sources, and re-number [S1], [S2], ... for the prompt.

    recency_query: optional extra query run with a time filter so fresh, dated
    pages (funding/M&A/leadership) actually surface. The time filter is scoped to
    ONLY this query — the identity/general queries stay unfiltered.
    category: SearchProvider category for the general queries (general/company/people).
    The recency query always runs against the `news` category.
    """
    if max_per_query is None:
        max_per_query = max(4, min(_default_max_results(), 10))
    if max_total_sources is None:
        max_total_sources = int(os.getenv("SCOUT_RETRIEVAL_MERGED_CAP", "16"))
    max_total_sources = max(5, min(max_total_sources, 24))

    general_queries = [str(q).strip() for q in queries if str(q).strip()]
    rq = str(recency_query or "").strip()
    effective_category = normalize_category(category)
    if not general_queries and not rq:
        return {
            "provider": "none",
            "category": effective_category,
            "retrieval_outcome": "no_results",
            "provider_diagnostics": [],
            "query": "",
            "sources": [],
            "url_allowlist": set(),
        }

    merged_rows: List[Dict[str, str]] = []
    seen_norm: Set[str] = set()
    admitted_providers: Set[str] = set()
    used_provider = "none"
    provider_diagnostics: List[Dict[str, Any]] = []

    def _ingest(rows: List[Dict[str, str]], limit: int | None, provider: str = "") -> None:
        added = 0
        for row in rows or []:
            if len(merged_rows) >= max_total_sources:
                return
            if limit is not None and added >= limit:
                return
            url = str(row.get("url") or "").strip()
            nu = normalize_url_for_match(url)
            if not nu or nu in seen_norm:
                continue
            seen_norm.add(nu)
            if provider:
                admitted_providers.add(provider)
            merged_rows.append(
                {
                    "title": str(row.get("title") or "").strip(),
                    "url": url,
                    "snippet": str(row.get("snippet") or "").strip(),
                }
            )
            added += 1

    concurrency = _query_concurrency()

    # The recency query and the first wave of general queries do not depend on one
    # another, so they are issued together; results are still INGESTED in the
    # recency-first order below.
    first_wave = general_queries[:concurrency] if concurrency > 1 else []
    first_wave_future = (
        _QUERY_EXECUTOR.submit(
            _run_query_wave,
            first_wave,
            user_id=user_id,
            max_results=max_per_query,
            category=effective_category,
        )
        if first_wave and rq
        else None
    )

    # Recency FIRST, with a reserved quota, so a breaking event (acquisition, IPO,
    # round) is never starved out of the source pack by the general queries hitting
    # the cap. The recency query runs against the news category (recency-ranked),
    # with a general-search fallback if news returns nothing.
    if rq:
        from utils.recency import recency_window_days, tavily_time_range

        tr = recency_time_range or tavily_time_range()
        reserved = int(os.getenv("SCOUT_RECENCY_RESERVED_SLOTS", "5"))
        reserved = max(2, min(reserved, max_total_sources - 1))
        news = retrieve_source_pack(
            query=rq,
            user_id=user_id,
            max_results=max_per_query,
            time_range=tr,
            category="news",
            days=recency_window_days(),
        )
        rows = news.get("sources") or []
        admitted_provider = str(news.get("provider") or "")
        provider_diagnostics.extend(news.get("provider_diagnostics") or [])
        if rows:
            used_provider = str(news.get("provider") or used_provider)
        if not rows:
            fallback_news = retrieve_source_pack(
                query=rq,
                user_id=user_id,
                max_results=max_per_query,
                time_range=tr,
                category=effective_category,
            )
            rows = fallback_news.get("sources") or []
            admitted_provider = str(fallback_news.get("provider") or admitted_provider)
            provider_diagnostics.extend(fallback_news.get("provider_diagnostics") or [])
            if rows:
                used_provider = str(fallback_news.get("provider") or used_provider)
        _ingest(rows, limit=reserved, provider=admitted_provider)

    # General queries fill the remaining slots, issued in concurrent waves. The
    # cap is re-checked between waves so a full pack still stops further queries.
    def _ingest_packs(packs: List[Dict[str, Any]]) -> None:
        nonlocal used_provider
        for pack in packs:
            provider_diagnostics.extend(pack.get("provider_diagnostics") or [])
            if pack.get("sources"):
                used_provider = str(pack.get("provider") or used_provider)
            _ingest(pack.get("sources"), limit=None, provider=str(pack.get("provider") or ""))

    remaining = list(general_queries)
    if first_wave_future is not None:
        _ingest_packs(first_wave_future.result())
        remaining = remaining[len(first_wave):]

    while remaining and len(merged_rows) < max_total_sources:
        wave = remaining[:concurrency] if concurrency > 1 else remaining[:1]
        remaining = remaining[len(wave):]
        _ingest_packs(
            _run_query_wave(
                wave,
                user_id=user_id,
                max_results=max_per_query,
                category=effective_category,
            )
        )

    cleaned_queries = ([rq] if rq else []) + general_queries
    sources = _normalize_sources(merged_rows)
    allowlist: Set[str] = {s["url"] for s in sources if s.get("url")}
    providers = sorted(admitted_providers)
    provider_label = providers[0] if len(providers) == 1 else "mixed" if providers else "none"
    logger.info(
        "retrieval_grounding merged: queries=%d unique_urls=%d provider=%s category=%s",
        len(cleaned_queries),
        len(sources),
        provider_label,
        effective_category,
    )
    return {
        # Keep `provider` for existing callers, but never claim one provider
        # when the merged pack actually used several.
        "provider": provider_label,
        "providers": providers,
        "category": effective_category,
        "retrieval_outcome": "sources_found" if sources else "no_results",
        "provider_diagnostics": provider_diagnostics,
        "query": " | ".join(cleaned_queries[:4]),
        "sources": sources,
        "url_allowlist": allowlist,
    }


def render_sources_for_prompt(sources: List[Dict[str, str]]) -> str:
    if not sources:
        return "No retrieved sources available."
    lines: List[str] = [
        "Retrieved sources (ONLY these may be cited):",
        prompt_safety_instruction(),
    ]
    for s in sources:
        snippet = isolate_untrusted_text(
            s["snippet"],
            label=f'{s["source_id"]} snippet',
        )
        safety = flag_prompt_injection(s["snippet"])
        suffix = " safety=PROMPT_INJECTION_SUSPECTED" if safety.suspicious else ""
        lines.append(
            f'[{s["source_id"]}] title="{s["title"]}" url="{s["url"]}"{suffix} snippet="{snippet}"'
        )
    return "\n".join(lines)


def log_pre_filter_cited_urls(refs: Any) -> None:
    """
    Temporary debug log for URLs cited by the model before allowlist filtering.
    """
    if not isinstance(refs, list):
        logger.info("DEBUG retrieval llm_cited_urls_pre_filter=[]")
        return
    cited: List[str] = []
    for r in refs:
        if not isinstance(r, str):
            continue
        for u in extract_http_urls(r):
            nu = normalize_url_for_match(u)
            if nu:
                cited.append(nu)
    logger.info("DEBUG retrieval llm_cited_urls_pre_filter=%s", cited)
