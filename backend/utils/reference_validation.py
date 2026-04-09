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

# Substring match on normalized company name (use tokens unlikely to appear inside unrelated names).
_MEGACAP_KEYWORDS = (
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
)

# Short / ambiguous tokens: whole-word match only (avoids "intuit" in "intuitive", "stripe" in "stripes").
_MEGACAP_WORD_RE = re.compile(
    r"\b("
    r"stripe|paypal|uber|lyft|visa|mastercard|intuit|square|plaid|checkout|"
    r"chime|revolut|wise|klarna|affirm|sofi|roku|peloton|zoom|slack|dropbox|"
    r"hubspot|zendesk|okta|crowdstrike|zscaler|cloudflare|datadog|mongodb|elastic"
    r")\b",
    re.I,
)

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


def is_megacap_company(name: str) -> bool:
    """
    Heuristic: True if the company name looks like a large public/mega-cap incumbent
    (FAANG / hyperscalers, major fintech, public SaaS, etc.), which we do not consider
    as VC discovery targets for scouts.
    """
    if not isinstance(name, str):
        return False
    lower = name.strip().lower()
    if not lower:
        return False
    if any(k in lower for k in _MEGACAP_KEYWORDS):
        return True
    return _MEGACAP_WORD_RE.search(lower) is not None


def validate_references_not_only_incumbent_domains(references: List[str]) -> None:
    """
    Raise ValueError if every http(s) URL in references resolves to a registrable domain
    we treat as a large incumbent-only source (e.g. only stripe.com links).
    """
    from utils.reference_verify import extract_http_urls, registrable_domain

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
