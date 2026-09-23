"""Thin Firecrawl v2 API client for retrieval grounding."""
from __future__ import annotations

import json
import logging
import os
import socket
import ssl
import time
from datetime import date, timedelta
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

import certifi

import metrics
from utils.retry import retry_delay
from research.search_results import ProviderSearchResults
from research.reference_validation import is_scraped_http_error_page

logger = logging.getLogger("firecrawl")

# Socket deadline sits above the API deadline so Firecrawl's own structured error
# surfaces instead of an opaque socket timeout.
_SOCKET_HEADROOM_SECONDS = 5.0


def _is_transient(error: BaseException) -> bool:
    """True for read/connect timeouts, which are worth retrying."""
    if isinstance(error, (socket.timeout, TimeoutError)):
        return True
    if isinstance(error, URLError) and isinstance(getattr(error, "reason", None), (socket.timeout, TimeoutError)):
        return True
    return False


def _provider_diagnostic(
    *,
    outcome: str,
    reason: str | None,
    result_count: int,
    http_status: int | None = None,
) -> Dict[str, Any]:
    diagnostic: Dict[str, Any] = {
        "provider": "firecrawl",
        "outcome": outcome,
        "reason": reason,
        "result_count": result_count,
    }
    if http_status is not None:
        diagnostic["http_status"] = http_status
    return diagnostic


def _firecrawl_config(max_results: int) -> tuple[int, float, int, bool, int, int]:
    cap = max(1, min(int(os.getenv("FIRECRAWL_MAX_RESULTS_CAP", "15")), 100))
    results = max(1, min(int(max_results), cap, 100))
    timeout = max(1.0, min(float(os.getenv("FIRECRAWL_TIMEOUT", "20.0")), 120.0))
    retries = max(0, min(int(os.getenv("FIRECRAWL_MAX_RETRIES", "2")), 5))
    include_markdown = os.getenv("FIRECRAWL_INCLUDE_MARKDOWN", "1").strip().lower() in (
        "1", "true", "yes"
    )
    markdown_max = max(200, min(int(os.getenv("FIRECRAWL_MARKDOWN_MAX_CHARS", "4500")), 12000))
    scrape_max_urls = max(1, min(int(os.getenv("FIRECRAWL_SCRAPE_MAX_URLS", "3")), 10))
    return results, timeout, retries, include_markdown, markdown_max, scrape_max_urls


def _normalized_url(url: str) -> str:
    parsed = urlsplit(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return ""
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), parsed.query, ""))


def _observe(*, outcome: str, result_count: int, extraction_ok: bool, started: float, credits: int | None) -> None:
    metrics.observe_retrieval_provider(
        provider="firecrawl",
        outcome=outcome,
        result_count=result_count,
        extraction_ok=extraction_ok,
        latency_seconds=time.monotonic() - started,
        credits=credits,
    )


def _search_body(query: str, max_results: int, include_markdown: bool, time_range: str | None, topic: str | None, days: int | None, timeout: float) -> tuple[Dict[str, Any], str]:
    is_news = str(topic or "").strip().lower() == "news"
    body: Dict[str, Any] = {
        "query": str(query)[:500],
        "limit": max_results,
        "sources": [{"type": "news"}] if is_news else ["web"],
        "timeout": int(timeout * 1000),
    }
    if include_markdown:
        body["scrapeOptions"] = {"formats": [{"type": "markdown"}]}
    range_map = {"day": "qdr:d", "week": "qdr:w", "month": "qdr:m", "year": "qdr:y"}
    normalized_range = str(time_range or "").strip().lower()
    if normalized_range in range_map:
        body["tbs"] = range_map[normalized_range]
    if is_news and isinstance(days, int) and days > 0:
        today = date.today()
        body["tbs"] = "cdr:1,cd_min:{},cd_max:{}".format(
            (today - timedelta(days=days)).strftime("%m/%d/%Y"), today.strftime("%m/%d/%Y")
        )
    return body, "news" if is_news else "web"


def _retry_after(error: HTTPError, fallback: float) -> float:
    try:
        return max(0.0, min(float(error.headers.get("Retry-After", fallback)), 10.0))
    except (TypeError, ValueError):
        return fallback


def firecrawl_search(
    query: str,
    max_results: int = 10,
    timeout: float | None = None,
    time_range: str | None = None,
    topic: str | None = None,
    days: int | None = None,
) -> ProviderSearchResults:
    """Return normalized Firecrawl v2 search results with structured diagnostics."""
    started = time.monotonic()
    api_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        diagnostic = _provider_diagnostic(outcome="disabled", reason="missing_api_key", result_count=0)
        _observe(outcome="disabled", result_count=0, extraction_ok=False, started=started, credits=None)
        return ProviderSearchResults([], diagnostic)

    n, default_timeout, retries, include_markdown, markdown_max, _ = _firecrawl_config(max_results)
    effective_timeout = default_timeout if timeout is None else max(1.0, float(timeout))
    # Give the socket headroom over the API's own deadline so Firecrawl's structured
    # error wins the race instead of the socket dying first with an opaque timeout.
    body, result_key = _search_body(
        query, n, include_markdown, time_range, topic, days, effective_timeout
    )
    socket_timeout = effective_timeout + _SOCKET_HEADROOM_SECONDS
    request = Request(
        "https://api.firecrawl.dev/v2/search",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    context = ssl.create_default_context(cafile=certifi.where())
    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=socket_timeout, context=context) as response:
                data = json.loads(response.read().decode("utf-8"))
            if not isinstance(data, dict) or data.get("success") is not True or not isinstance(data.get("data"), dict):
                diagnostic = _provider_diagnostic(outcome="error", reason="malformed_response", result_count=0)
                _observe(outcome="error", result_count=0, extraction_ok=False, started=started, credits=None)
                return ProviderSearchResults([], diagnostic)
            items = data["data"].get(result_key)
            if not isinstance(items, list):
                diagnostic = _provider_diagnostic(outcome="error", reason="malformed_response", result_count=0)
                _observe(outcome="error", result_count=0, extraction_ok=False, started=started, credits=data.get("creditsUsed"))
                return ProviderSearchResults([], diagnostic)
            rows: List[Dict[str, str]] = []
            seen: set[str] = set()
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                url = str(item.get("url") or "").strip()
                normalized_url = _normalized_url(url)
                markdown = str(item.get("markdown") or "").strip()
                fallback = item.get("snippet") if result_key == "news" else item.get("description")
                snippet = markdown or str(fallback or "").strip()
                if not title or not normalized_url or normalized_url in seen:
                    continue
                seen.add(normalized_url)
                rows.append({"title": title, "url": url, "snippet": snippet[:markdown_max]})
            outcome = "success" if rows else "empty"
            diagnostic = _provider_diagnostic(outcome=outcome, reason=None if rows else "no_usable_results", result_count=len(rows))
            credits = data.get("creditsUsed") if isinstance(data.get("creditsUsed"), int) else None
            _observe(outcome=outcome, result_count=len(rows), extraction_ok=bool(rows), started=started, credits=credits)
            return ProviderSearchResults(rows, diagnostic)
        except HTTPError as error:
            status = getattr(error, "code", None)
            if status in (429,) or (isinstance(status, int) and 500 <= status <= 599):
                if attempt < retries:
                    time.sleep(_retry_after(error, retry_delay(attempt)))
                    continue
            reason = "rate_limited" if status == 429 else "http_error"
            diagnostic = _provider_diagnostic(outcome="error", reason=reason, result_count=0, http_status=status)
            _observe(outcome="error", result_count=0, extraction_ok=False, started=started, credits=None)
            return ProviderSearchResults([], diagnostic)
        except Exception as error:
            # Socket/read timeouts are transient and are the dominant observed
            # failure when markdown scraping is on (measured ~5s typical, but
            # tail latency exceeds the budget). Retry them like a 5xx; a plain
            # `except Exception` here would otherwise make them the one failure
            # mode that never retries.
            if _is_transient(error) and attempt < retries:
                time.sleep(retry_delay(attempt))
                continue
            reason = "timeout" if _is_transient(error) else "request_error"
            logger.warning("Firecrawl search failed (%s): %s", reason, error)
            diagnostic = _provider_diagnostic(outcome="error", reason=reason, result_count=0)
            _observe(outcome="error", result_count=0, extraction_ok=False, started=started, credits=None)
            return ProviderSearchResults([], diagnostic)
    raise AssertionError("unreachable")  # pragma: no cover


def firecrawl_scrape(urls: List[str], timeout: float | None = None) -> List[Dict[str, str]]:
    """Fetch explicit URLs through Firecrawl v2 scrape, returning [{url, content}]."""
    api_key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        return []
    _, default_timeout, retries, _, markdown_max, scrape_max_urls = _firecrawl_config(1)
    effective_timeout = default_timeout if timeout is None else max(1.0, float(timeout))
    clean = [url.strip() for url in urls if isinstance(url, str) and url.strip().startswith("http")]
    context = ssl.create_default_context(cafile=certifi.where())
    extracted: List[Dict[str, str]] = []
    for url in clean[:scrape_max_urls]:
        request = Request(
            "https://api.firecrawl.dev/v2/scrape",
            data=json.dumps({"url": url, "formats": ["markdown"], "onlyMainContent": True, "timeout": int(effective_timeout * 1000)}).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        for attempt in range(retries + 1):
            try:
                with urlopen(
                    request, timeout=effective_timeout + _SOCKET_HEADROOM_SECONDS, context=context
                ) as response:
                    data = json.loads(response.read().decode("utf-8"))
                payload = data.get("data") if isinstance(data, dict) and data.get("success") is True else None
                content = str(payload.get("markdown") or "").strip() if isinstance(payload, dict) else ""
                if content and not is_scraped_http_error_page(content):
                    extracted.append({"url": url, "content": content[:markdown_max]})
                break
            except HTTPError as error:
                if (error.code == 429 or 500 <= error.code <= 599) and attempt < retries:
                    time.sleep(_retry_after(error, min(0.25 * (2 ** attempt), 2.0)))
                    continue
                logger.warning("Firecrawl scrape failed: HTTP %s", error.code)
                break
            except Exception as error:
                if _is_transient(error) and attempt < retries:
                    time.sleep(min(0.25 * (2 ** attempt), 2.0))
                    continue
                logger.warning("Firecrawl scrape failed: %s", error)
                break
    return extracted
