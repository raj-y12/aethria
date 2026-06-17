"""Centralized real-time date + recency context for LLM prompts and retrieval.

Single source of truth so Scout, Reviewer, and Memo all anchor to the same
"today" and the same recency window. The date is resolved at call time and the
directives are injected into the *user* message (or freshly-built reviewer
prompt), never baked into the mutable Scout system prompt — the MetaAgent can
promote/mutate that prompt and would otherwise silently strip recency rules.

Tunable via env:
    RECENCY_WINDOW_MONTHS  (default 12, clamped 1..36)
"""
from __future__ import annotations

import os
from datetime import datetime, timezone


def current_date_iso() -> str:
    """Today's date (UTC) as YYYY-MM-DD — the single notion of "now"."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def current_year() -> int:
    return datetime.now(timezone.utc).year


def recency_window_months() -> int:
    raw = os.getenv("RECENCY_WINDOW_MONTHS", "12")
    try:
        n = int(raw)
    except ValueError:
        n = 12
    return max(1, min(n, 36))


def tavily_time_range() -> str:
    """Coarse Tavily `time_range` matching the recency window.

    Tavily only offers day/week/month/year granularity, so the window is mapped
    to the nearest range that won't exclude in-window results: <=1mo -> month,
    otherwise year. This biases the recency query toward fresh pages without
    hard-dropping anything the prompt-level window still allows.
    """
    return "month" if recency_window_months() <= 1 else "year"


def recency_window_days() -> int:
    """Recency window expressed in days for Tavily's news `days` parameter.

    Capped at 365 — news older than a year is not "recent" for our purposes and
    Tavily's news topic is tuned for recent coverage.
    """
    return max(7, min(recency_window_months() * 31, 365))


def scout_recency_directive() -> str:
    """Date anchor + recency mandate for Scout LLM calls (open discovery + lookup)."""
    today = current_date_iso()
    months = recency_window_months()
    return (
        f"CURRENT DATE: today is {today}. Treat this as 'now'. Your training data may be "
        "out of date, so when retrieved sources carry more recent, dated facts, trust those "
        "sources over your prior assumptions.\n"
        f"RECENCY MANDATE: actively surface MATERIAL RECENT EVENTS from roughly the last "
        f"{months} months — funding rounds, acquisitions / M&A, IPOs, leadership changes, "
        "major product launches, and valuation changes. When such an event exists, reflect it "
        "in why_now and primary_thesis, prefer sources that show a publication date, and state "
        "the event's date when known. Never invent an event you cannot ground in a cited source.\n"
        "BREAKING-EVENT PRIORITY: if ANY retrieved source dated within the window reports an "
        "acquisition, merger, IPO, shutdown, major funding round, or CEO change, you MUST state "
        "that event explicitly in why_now WITH its date and INCLUDE that source's URL in "
        "references — even when it is a news site rather than the company's own domain. Do NOT "
        "describe older funding as the latest status when a more recent material event is in the sources."
    )


def reviewer_recency_directive() -> str:
    """Date anchor + recency check for the Reviewer LLM user message."""
    today = current_date_iso()
    months = recency_window_months()
    return (
        f"CURRENT DATE: today is {today}. Treat older claims as potentially stale. "
        f"If the Scout memo or supplemental snippets reference material events from the last "
        f"{months} months (funding, acquisition/M&A, leadership change, major launch), weigh "
        "them explicitly and note whether they change the thesis. Flag when key facts look outdated."
    )


def recency_query(label: str) -> str:
    """A dated recent-events retrieval query for a company / lens label.

    Recency is expressed with query *terms* (year + event keywords) so Tavily
    surfaces fresh results without a provider-specific time filter.
    """
    label = (label or "").strip()
    if not label:
        return ""
    return (
        f"{label} latest news {current_year()} funding round acquisition merger "
        "leadership announcement"
    )


def memo_recency_note() -> str:
    """As-of line for the generated memo header (keeps the recency trail auditable)."""
    today = current_date_iso()
    months = recency_window_months()
    return (
        f"**Information current as of:** {today} "
        f"(recency window: last {months} months — verify time-sensitive facts before acting)"
    )
