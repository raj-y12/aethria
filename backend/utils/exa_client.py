"""Thin Exa API client for retrieval grounding.

Exa is a *semantic* search index: it ranks by meaning rather than keyword
overlap, and it returns links — not page text — unless contents are requested.
That difference drives two decisions here:

1. **Queries are rewritten into natural language.** The existing discovery
   queries use keyword/boolean phrasing (`"fintech" OR "payments" startup seed
   funding round raised`), which is what a keyword index like Firecrawl wants.
   Feeding that
   to a semantic index degrades it, so `semantic_query()` unpicks the boolean
   scaffolding into a sentence describing the *company* being looked for.

2. **Content comes from Firecrawl, not Exa.** Firecrawl stays the canonical
   content-retrieval layer (DEC-004), so full page text is deliberately not
   requested from Exa. Short highlights are requested for ranking, and are only
   promoted into the snippet when Firecrawl fails to scrape a URL — tagged
   `content_provider="exa_highlight"` so the provenance is never ambiguous.

Rows normalise to the same `{title, url, snippet}` shape every other provider
returns, so no downstream consumer changes.
"""
from __future__ import annotations

import json
import logging
import os
import socket
import ssl
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import certifi

import metrics
from utils.reference_verify import normalize_url_for_match
from utils.search_results import ProviderSearchResults

logger = logging.getLogger("exa")

_ENDPOINT = "https://api.exa.ai/search"

# Socket deadline sits above the request budget so a slow response surfaces as a
# retryable timeout rather than an opaque connection reset.
_SOCKET_HEADROOM_SECONDS = 5.0

# Exa's own search modes. `deep`, `deep-lite` and `deep-reasoning` perform
# autonomous multi-step research and synthesis, which the pipeline must never
# do — investment conclusions come from the evaluation layer, not the index.
_ALLOWED_SEARCH_TYPES = ("auto", "fast", "instant")

# Exa rejects `excludeDomains`, `startPublishedDate` and `endPublishedDate` with
# a 400 when these categories are used. Verified against the API reference.
_FILTER_RESTRICTED_CATEGORIES = frozenset({"company", "people"})

# Query intents, and the Exa category each maps to. The pipeline's four routing
# categories (general/news/company/people) decide *which provider* answers; the
# intent decides *how Exa is asked*, and is derived from the query text.
_INTENT_EXA_CATEGORY: Dict[str, Optional[str]] = {
    "company": "company",
    "founder": "people",
    "funding": "news",
    "news": "news",
    "hiring": None,
    "customers": None,
    "competitors": None,
    "product": None,
    "market": None,
}

# Ordered longest-signal-first: the first intent whose terms appear wins.
_INTENT_TERMS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("funding", ("funding", "raised", "seed round", "series a", "series b", "valuation", "investors")),
    ("founder", ("founder", "co-founder", "cofounder", "ceo", "leadership", "team page", "who founded")),
    ("hiring", ("hiring", "jobs", "careers", "open roles", "headcount")),
    ("customers", ("customers", "case study", "pilots", "testimonial", "deployment")),
    ("competitors", ("competitor", "alternatives", "vs ", "landscape")),
    ("product", ("product", "platform", "pricing", "documentation", "features")),
    ("market", ("market size", "tam", "industry report", "market report")),
    ("news", ("news", "announcement", "latest", "recent")),
)

# Hosts that aggregate companies rather than being one. Demoted for open
# discovery only — the company resolver actively wants Crunchbase/LinkedIn as
# identity anchors, so it must never inherit this penalty.
_AGGREGATOR_HOSTS = frozenset({
    "crunchbase.com", "pitchbook.com", "tracxn.com", "cbinsights.com", "dealroom.co",
    "linkedin.com", "wellfound.com", "angel.co", "f6s.com", "producthunt.com",
    "medium.com", "substack.com", "reddit.com", "quora.com", "youtube.com",
    "en.wikipedia.org", "wikipedia.org", "glassdoor.com", "indeed.com",
})

_LISTICLE_MARKERS = ("/top-", "/best-", "/list/", "-startups-to-watch", "/rankings", "/directory")


def _is_transient(error: BaseException) -> bool:
    """True for read/connect timeouts, which are worth retrying."""
    if isinstance(error, (socket.timeout, TimeoutError)):
        return True
    return isinstance(error, URLError) and isinstance(
        getattr(error, "reason", None), (socket.timeout, TimeoutError)
    )


def _diagnostic(
    *,
    outcome: str,
    reason: Optional[str],
    result_count: int,
    http_status: Optional[int] = None,
    **extra: Any,
) -> Dict[str, Any]:
    diagnostic: Dict[str, Any] = {
        "provider": "exa",
        "outcome": outcome,
        "reason": reason,
        "result_count": result_count,
    }
    if http_status is not None:
        diagnostic["http_status"] = http_status
    diagnostic.update(extra)
    return diagnostic


def _config(max_results: int) -> Dict[str, Any]:
    cap = max(1, min(int(os.getenv("EXA_MAX_RESULTS_CAP", "15")), 100))
    search_type = os.getenv("EXA_SEARCH_TYPE", "auto").strip().lower()
    return {
        "results": max(1, min(int(max_results), cap)),
        "timeout": max(1.0, min(float(os.getenv("EXA_TIMEOUT", "20.0")), 120.0)),
        "retries": max(0, min(int(os.getenv("EXA_MAX_RETRIES", "2")), 5)),
        "search_type": search_type if search_type in _ALLOWED_SEARCH_TYPES else "auto",
        "highlight_max": max(200, min(int(os.getenv("EXA_HIGHLIGHT_MAX_CHARS", "1200")), 6000)),
    }


def _domain_list(name: str) -> List[str]:
    return [d.strip().lower() for d in os.getenv(name, "").split(",") if d.strip()]


def query_intent(query: str, category: str) -> str:
    """Classify a query into one of the nine retrieval intents.

    The routing category wins when it is unambiguous (`people`/`news`); otherwise
    the query text decides, defaulting to `company` so open discovery asks Exa
    for companies rather than articles about them.
    """
    normalized = f" {str(query or '').strip().lower()} "
    if category == "people":
        return "founder"
    if category == "news":
        return "news"
    for intent, terms in _INTENT_TERMS:
        if any(term in normalized for term in terms):
            return intent
    return "company"


def semantic_query(query: str, intent: str, *, discovery: bool = False) -> str:
    """Rewrite a keyword/boolean query into something a semantic index can use.

    The boolean scaffolding is always stripped: discovery queries are built for
    keyword engines (quoted phrases joined by `OR`, then a pile of bare nouns),
    and Exa scores meaning, so the operators are noise.

    The intent prefix is applied to **open discovery only**. It turns
    `"climate tech" OR "energy" startup seed funding round raised europe` into a
    request for companies rather than for articles containing those words. On a
    *named* lookup it does the opposite and must not be used: measured against
    the live API, "Companies working on Anthropic official company site" returned
    four unrelated companies, while the bare "Anthropic official company site"
    put anthropic.io and the correct LinkedIn page in the top three.
    """
    text = str(query or "").strip()
    if not text:
        return ""
    cleaned = text.replace('"', " ").replace("'", " ")
    cleaned = " ".join(word for word in cleaned.split() if word.upper() not in ("OR", "AND"))
    if not discovery:
        return cleaned[:500]
    prefix = {
        "company": "Companies working on",
        "founder": "The founders and leadership team of",
        "funding": "Startups that recently raised funding in",
        "hiring": "Companies currently hiring for",
        "customers": "Customers and deployments of",
        "competitors": "Companies competing with",
        "product": "The product and platform offered by",
        "market": "Market analysis of",
        "news": "Recent news about",
    }.get(intent, "Companies working on")
    return f"{prefix} {cleaned}"[:500]


def _published_window(time_range: Optional[str], days: Optional[int]) -> Optional[str]:
    """ISO-8601 lower bound for Exa's `startPublishedDate`, or None."""
    window = {"day": 1, "week": 7, "month": 31, "year": 365}.get(
        str(time_range or "").strip().lower()
    )
    if isinstance(days, int) and days > 0:
        window = days if window is None else min(window, days)
    if window is None:
        return None
    start = datetime.now(timezone.utc) - timedelta(days=window)
    return start.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _build_body(
    *,
    query: str,
    intent: str,
    category: str,
    config: Dict[str, Any],
    time_range: Optional[str],
    days: Optional[int],
) -> Dict[str, Any]:
    exa_category = _INTENT_EXA_CATEGORY.get(intent)
    body: Dict[str, Any] = {
        # Only open discovery ("general") is looking for companies it cannot
        # name. Every other category already knows its subject.
        "query": semantic_query(query, intent, discovery=category == "general"),
        "numResults": config["results"],
        "type": config["search_type"],
        # Highlights only: Firecrawl is the canonical content layer, so full page
        # text is never requested here. These are for ranking and for the
        # Firecrawl-failure fallback.
        "contents": {"highlights": {"numSentences": 3, "highlightsPerUrl": 2}},
    }
    if exa_category:
        body["category"] = exa_category

    include = _domain_list("EXA_INCLUDE_DOMAINS")
    if include:
        body["includeDomains"] = include[:1200]

    # `company` and `people` categories 400 on these filters, so they are dropped
    # rather than sent and retried.
    if exa_category not in _FILTER_RESTRICTED_CATEGORIES:
        exclude = _domain_list("EXA_EXCLUDE_DOMAINS")
        if exclude:
            body["excludeDomains"] = exclude[:1200]
        start = _published_window(time_range, days)
        if start:
            body["startPublishedDate"] = start
    return body


def _host(url: str) -> str:
    try:
        return urlsplit(url).netloc.lower().removeprefix("www.")
    except ValueError:
        return ""


def is_company_domain(url: str) -> bool:
    """True when the URL looks like a company's own site, not an aggregator."""
    host = _host(url)
    if not host or host in _AGGREGATOR_HOSTS:
        return False
    return not any(host.endswith(f".{aggregator}") for aggregator in _AGGREGATOR_HOSTS)


def _rank_rows(rows: List[Dict[str, Any]], *, demote_aggregators: bool) -> List[Dict[str, Any]]:
    """Order candidate company domains ahead of directories and listicles.

    Search relevance is *not* investment quality — this only decides which pages
    are worth spending a Firecrawl scrape on, never how a company scores.
    """
    if not demote_aggregators:
        return rows

    def rank(row: Dict[str, Any]) -> float:
        url = str(row.get("url") or "")
        score = float(row.get("score") or 0.0)
        if not is_company_domain(url):
            score -= 1.0
        path = urlsplit(url).path.lower()
        if any(marker in path for marker in _LISTICLE_MARKERS):
            score -= 0.5
        if len([segment for segment in path.split("/") if segment]) <= 1:
            score += 0.2  # a homepage or a single-segment page, not a news article
        return score

    return sorted(rows, key=rank, reverse=True)


def _parse_results(
    data: Any, *, highlight_max: int
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[float]]:
    """Normalise the Exa payload, or (None, cost) when it is malformed."""
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        return None, None
    cost_block = data.get("costDollars")
    cost = float(cost_block["total"]) if isinstance(cost_block, dict) and isinstance(
        cost_block.get("total"), (int, float)
    ) else None

    rows: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for item in data["results"]:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        key = normalize_url_for_match(url)
        if not url or not title or not key or key in seen:
            continue
        seen.add(key)
        highlights = item.get("highlights")
        highlight = " ".join(
            str(h).strip() for h in highlights if isinstance(h, str) and str(h).strip()
        ) if isinstance(highlights, list) else ""
        if not highlight:
            highlight = str(item.get("text") or "").strip()
        rows.append({
            "title": title,
            "url": url,
            "highlight": highlight[:highlight_max],
            "published_date": str(item.get("publishedDate") or "").strip() or None,
            "author": str(item.get("author") or "").strip() or None,
            "score": float(item["score"]) if isinstance(item.get("score"), (int, float)) else None,
        })
    return rows, cost


def exa_search(
    query: str,
    max_results: int = 10,
    timeout: Optional[float] = None,
    time_range: Optional[str] = None,
    days: Optional[int] = None,
    category: str = "general",
) -> ProviderSearchResults:
    """Search Exa and return ranked, deduplicated candidate URLs.

    Snippets carry Exa *highlights* only. The caller (`ExaSearchProvider`) is
    responsible for replacing them with Firecrawl page content; this function
    stays a pure client so it is testable without a second provider.
    """
    started = time.monotonic()
    api_key = os.getenv("EXA_API_KEY", "").strip()
    intent = query_intent(query, category)
    if not api_key:
        metrics.observe_retrieval_provider(
            provider="exa", outcome="disabled", result_count=0, extraction_ok=False,
            latency_seconds=time.monotonic() - started, credits=None,
        )
        return ProviderSearchResults(
            [], _diagnostic(outcome="disabled", reason="missing_api_key", result_count=0, query_type=intent)
        )

    config = _config(max_results)
    effective_timeout = config["timeout"] if timeout is None else max(1.0, float(timeout))
    body = _build_body(
        query=query, intent=intent, category=category, config=config,
        time_range=time_range, days=days,
    )
    request = Request(
        _ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    context = ssl.create_default_context(cafile=certifi.where())

    def observe(outcome: str, count: int) -> None:
        metrics.observe_retrieval_provider(
            provider="exa", outcome=outcome, result_count=count, extraction_ok=bool(count),
            latency_seconds=time.monotonic() - started, credits=None,
        )

    for attempt in range(config["retries"] + 1):
        try:
            with urlopen(request, timeout=effective_timeout + _SOCKET_HEADROOM_SECONDS, context=context) as response:
                data = json.loads(response.read().decode("utf-8"))
            rows, cost = _parse_results(data, highlight_max=config["highlight_max"])
            if rows is None:
                observe("error", 0)
                return ProviderSearchResults(
                    [], _diagnostic(outcome="error", reason="malformed_response", result_count=0, query_type=intent)
                )
            # Demotion is scoped to open discovery. The company resolver and
            # founder lookups route with an explicit category and actively want
            # Crunchbase/LinkedIn as identity anchors — penalising them there
            # would break resolution, not improve it.
            ranked = _rank_rows(
                rows,
                demote_aggregators=category == "general" and intent in ("company", "funding", "market"),
            )
            outcome = "success" if ranked else "empty"
            observe(outcome, len(ranked))
            return ProviderSearchResults(
                ranked,
                _diagnostic(
                    outcome=outcome,
                    reason=None if ranked else "no_usable_results",
                    result_count=len(ranked),
                    query_type=intent,
                    cost_usd=cost,
                ),
            )
        except HTTPError as error:
            status = getattr(error, "code", None)
            retryable = status == 429 or (isinstance(status, int) and 500 <= status <= 599)
            if retryable and attempt < config["retries"]:
                time.sleep(min(0.25 * (2 ** attempt), 2.0))
                continue
            reason = "rate_limited" if status == 429 else "http_error"
            logger.warning("Exa search failed: HTTP %s", status)
            observe("error", 0)
            return ProviderSearchResults(
                [], _diagnostic(outcome="error", reason=reason, result_count=0, http_status=status, query_type=intent)
            )
        except Exception as error:
            if _is_transient(error) and attempt < config["retries"]:
                time.sleep(min(0.25 * (2 ** attempt), 2.0))
                continue
            reason = "timeout" if _is_transient(error) else "request_error"
            logger.warning("Exa search failed (%s): %s", reason, error)
            observe("error", 0)
            return ProviderSearchResults(
                [], _diagnostic(outcome="error", reason=reason, result_count=0, query_type=intent)
            )
    raise AssertionError("unreachable")  # pragma: no cover
