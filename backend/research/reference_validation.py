"""
Shared validation helpers for Scout outputs.
Avoids circular imports between storage and scout.
"""

from __future__ import annotations

import re
from typing import List
from urllib.parse import urlparse

# Placeholder that does NOT prove a company exists; reject discoveries using only this
_GENERIC_REF_PATTERNS = (
    "general domain knowledge",
    "no specific external sources",
    "no specific sources",
)

# Mega-cap incumbents are matched on NORMALIZED WHOLE WORDS or a normalized exact
# alias — never on raw substrings. Substring matching silently discarded valid
# venture-scale companies whose names merely contain an incumbent token
# ("Metaview"/"Metabase" -> meta, "Intellia" -> intel, "Sapient"/"Sapling" -> sap,
# "Notional" -> notion, "Canvas" -> canva), each of which raised a hard
# ValueError in validate_scout_output and dropped the whole discovery.
_MEGACAP_WORDS = frozenset(
    {
        "google",
        "alphabet",
        "microsoft",
        "azure",
        "amazon",
        "aws",
        "apple",
        "meta",
        "facebook",
        "ibm",
        "oracle",
        "salesforce",
        "sap",
        "nvidia",
        "tesla",
        "snowflake",
        "palantir",
        "shopify",
        "coinbase",
        "servicenow",
        "twilio",
        "atlassian",
        "workday",
        "adyen",
        "robinhood",
        "doordash",
        "instacart",
        "openai",
        "anthropic",
        "databricks",
        "canva",
        "figma",
        "notion",
        "airbnb",
        "spotify",
        "netflix",
        "walmart",
        "cisco",
        "intel",
        "samsung",
        "sony",
        # Previously whole-word-only; same rule now applies to every entry.
        "stripe",
        "paypal",
        "uber",
        "lyft",
        "visa",
        "mastercard",
        "intuit",
        "square",
        "plaid",
        "checkout",
        "chime",
        "revolut",
        "wise",
        "klarna",
        "affirm",
        "sofi",
        "roku",
        "peloton",
        "zoom",
        "slack",
        "dropbox",
        "hubspot",
        "zendesk",
        "okta",
        "crowdstrike",
        "zscaler",
        "cloudflare",
        "datadog",
        "mongodb",
        "elastic",
    }
)

# Multi-word incumbent names that only count as an exact normalized alias, so a
# startup called "Meta Platforms Analytics" is not confused with the incumbent.
_MEGACAP_EXACT_ALIASES = frozenset(
    {
        "meta platforms",
        "alphabet inc",
        "google llc",
        "amazon web services",
        "microsoft corporation",
        "apple inc",
        "international business machines",
        "block inc",
        "square inc",
        "x corp",
    }
)

# Corporate suffixes dropped before alias comparison so "Stripe, Inc." == "stripe".
_CORPORATE_SUFFIXES = frozenset(
    {
        "inc",
        "incorporated",
        "llc",
        "ltd",
        "limited",
        "plc",
        "corp",
        "corporation",
        "co",
        "company",
        "gmbh",
        "sas",
        "sa",
        "bv",
        "nv",
        "ag",
        "ab",
        "oy",
        "as",
        "aps",
        "srl",
        "spa",
        "pte",
        "pty",
        "lp",
        "llp",
        "holdings",
        "group",
    }
)

_WORD_SPLIT_RE = re.compile(r"[^a-z0-9]+")

# Registrable domains of large public / mega-private companies. If ALL cited URLs land only here,
# the scout is effectively sourcing an incumbent (e.g. only stripe.com). Excludes google.com /
# microsoft.com / amazon.com so startups citing cloud/docs are not rejected.
_INCUMBENT_REFERENCE_REGISTRABLE_DOMAINS = frozenset(
    {
        "stripe.com",
        "shopify.com",
        "paypal.com",
        "apple.com",
        "meta.com",
        "facebook.com",
        "instagram.com",
        "oracle.com",
        "salesforce.com",
        "sap.com",
        "nvidia.com",
        "tesla.com",
        "snowflake.com",
        "palantir.com",
        "coinbase.com",
        "twilio.com",
        "servicenow.com",
        "workday.com",
        "atlassian.com",
        "uber.com",
        "lyft.com",
        "airbnb.com",
        "spotify.com",
        "netflix.com",
        "adyen.com",
        "robinhood.com",
        "doordash.com",
        "instacart.com",
        "openai.com",
        "anthropic.com",
        "databricks.com",
        "intuit.com",
        "squareup.com",
        "block.xyz",
        "wise.com",
        "klarna.com",
        "affirm.com",
        "sofi.com",
        "plaid.com",
        "checkout.com",
    }
)


def is_generic_reference(s: str) -> bool:
    """True if reference is the generic placeholder, not a real source (URL, news, etc.)."""
    if not s or not isinstance(s, str):
        return True
    lower = s.strip().lower()
    return any(p in lower for p in _GENERIC_REF_PATTERNS)


def _normalized_words(name: str) -> List[str]:
    """Lowercase alphanumeric words of a company name, corporate suffixes removed."""
    words = [w for w in _WORD_SPLIT_RE.split((name or "").lower()) if w]
    stripped = [w for w in words if w not in _CORPORATE_SUFFIXES]
    # A name made up entirely of suffixes ("The Company") keeps its raw words so
    # the caller still has something to compare.
    return stripped or words


def is_megacap_company(name: str) -> bool:
    """
    Heuristic: True if the company name looks like a large public/mega-cap incumbent
    (FAANG / hyperscalers, major fintech, public SaaS, etc.), which we do not consider
    as VC discovery targets for scouts.

    Matching is on normalized WHOLE WORDS or a normalized exact alias only. Substring
    matching is never used: it rejected legitimate venture-scale companies such as
    Metaview, Metabase, Intellia, Sapient, Sapling, Notional and Canvas.
    """
    if not isinstance(name, str):
        return False
    words = _normalized_words(name)
    if not words:
        return False
    if any(w in _MEGACAP_WORDS for w in words):
        return True
    # Apply the same corporate-suffix normalization to aliases as to the input.
    # Otherwise entries such as "block inc" and "x corp" can never match because
    # their suffixes were removed from `words` first.
    normalized_aliases = {
        " ".join(_normalized_words(alias)) for alias in _MEGACAP_EXACT_ALIASES
    }
    return " ".join(words) in normalized_aliases


def validate_references_not_only_incumbent_domains(references: List[str]) -> None:
    """
    Raise ValueError if every http(s) URL in references resolves to a registrable domain
    we treat as a large incumbent-only source (e.g. only stripe.com links).
    """
    from research.reference_verify import extract_http_urls, registrable_domain

    regs: list[str] = []
    for line in references:
        if not isinstance(line, str):
            continue
        for url in extract_http_urls(line):
            try:
                host = urlparse(url).hostname
            except Exception:
                continue
            if not host:
                continue
            rdom = registrable_domain(host.lower().strip("."))
            if rdom:
                regs.append(rdom)
    if not regs:
        return
    if all(r in _INCUMBENT_REFERENCE_REGISTRABLE_DOMAINS for r in regs):
        raise ValueError(
            "references cite only large incumbent corporate domains; scouts must include "
            "independent sources (news, funding databases, or the portfolio company's own site) "
            "and must not surface mega-caps as discovery targets."
        )
