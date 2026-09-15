"""Parsing for on-demand lookup input.

Extracted from api.py: turns a typed lookup string ("find Stripe", "Aethria
aethria.ai", "https://lyra.co") into a structured {company_name, website,
lookup_query, lookup_input_type}. Pure functions, no app state — covered by
tests/test_lookup_dispatch.py.
"""
from __future__ import annotations

import re
from typing import Dict, Optional
from urllib.parse import urlparse

_LOOKUP_LEADING_PHRASE_RE = re.compile(
    r"(?i)^\s*(?:find|lookup|look\s+up|search(?:\s+for)?|analy[sz]e|evaluate|check(?:\s+out)?|research)\s+"
)
_LOOKUP_TRAILING_QUALIFIERS = {"company", "startup", "website", "profile"}
_LOOKUP_COMMAND_ONLY_PHRASES = {
    "find",
    "lookup",
    "look up",
    "search",
    "search for",
    "analyze",
    "analyse",
    "evaluate",
    "check",
    "check out",
    "research",
}


def parse_lookup_input(lookup_input: str) -> Dict[str, Optional[str]]:
    raw = (lookup_input or "").strip()
    lowered = raw.lower()
    website: Optional[str] = None
    company_name = normalize_lookup_company_phrase(raw)
    input_type = "context_query"
    domain_like = re.match(r"^(https?://)?([a-z0-9-]+\.)+[a-z]{2,}([/:?#].*)?$", lowered)
    embedded_url_or_domain = re.search(
        r"(?i)\b((?:https?://)?(?:www\.)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:[/:?#][^\s]*)?)\b",
        raw,
    )

    if domain_like:
        parsed = urlparse(raw if lowered.startswith(("http://", "https://")) else f"https://{raw}")
        host = (parsed.netloc or parsed.path or "").lower().strip()
        host = host[4:] if host.startswith("www.") else host
        website = host or None
        if website:
            label = website.split(".")[0].replace("-", " ").strip()
            company_name = label.title() if label else raw
            input_type = "website"
    else:
        if embedded_url_or_domain:
            token = embedded_url_or_domain.group(1).strip()
            parsed = urlparse(token if token.lower().startswith(("http://", "https://")) else f"https://{token}")
            host = (parsed.netloc or parsed.path or "").lower().strip()
            host = host[4:] if host.startswith("www.") else host
            website = host or None
            # Strip the detected website token so company_name remains clean.
            candidate_name = re.sub(re.escape(token), " ", raw, flags=re.IGNORECASE).strip(" ,|-–—")
            candidate_name = normalize_lookup_company_phrase(candidate_name)
            if candidate_name and not is_lookup_command_only(candidate_name):
                company_name = candidate_name
                input_type = "context_query" if len(candidate_name.split()) > 3 else "company_name"
            elif website:
                label = website.split(".")[0].replace("-", " ").strip()
                company_name = label.title() if label else raw
                input_type = "website"
        else:
            token_count = len([t for t in re.split(r"\s+", raw) if t])
            input_type = "company_name" if token_count <= 3 else "context_query"

    return {
        "company_name": company_name.strip() if company_name else raw,
        "website": website,
        "lookup_query": raw,
        "lookup_input_type": input_type,
    }


def normalize_lookup_company_phrase(raw: str) -> str:
    """
    Keep on-demand lookup focused on the intended company when users type
    natural commands instead of only the brand name.
    """
    value = (raw or "").strip()
    if not value:
        return ""
    value = _LOOKUP_LEADING_PHRASE_RE.sub("", value).strip(" ,:;-")
    value = re.sub(r"(?i)^(?:company|startup)\s+(?:named|called)\s+", "", value).strip(" ,:;-")
    tokens = [t for t in re.split(r"\s+", value) if t]
    if len(tokens) > 2:
        last = re.sub(r"[^a-z0-9]", "", tokens[-1].lower())
        starts_with_the = tokens[0].lower() == "the"
        if last in _LOOKUP_TRAILING_QUALIFIERS and not (last == "company" and starts_with_the):
            value = " ".join(tokens[:-1]).strip(" ,:;-")
    return value or raw.strip()


def is_lookup_command_only(value: str) -> bool:
    normalized = re.sub(r"[^a-z ]+", " ", (value or "").lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized in _LOOKUP_COMMAND_ONLY_PHRASES
