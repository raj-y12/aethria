"""Which third-party sources may stay in a pack anchored to a known company domain.

When a lookup supplies the company's website, the source pack must be anchored to
that domain so a same-named company cannot hijack the identity. Anchoring is not
the same as *only* using that domain: funding rounds, team pages, leadership
changes and traction are almost always reported off-site, so discarding every
third-party source leaves the scout with one page to reason about.

The rule shared by the scout and reviewer paths:

  - the anchor host (and its subdomains) is always kept;
  - a known corroboration source (news wire, funding database, professional
    network) is kept when it actually refers to this company — by naming it, or
    by naming the anchor domain;
  - anything else is dropped, which is what preserves the disambiguation.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from utils.reference_verify import registrable_domain

# Publications and databases that report on private companies. Presence here only
# makes a source *eligible*; it still has to mention the company to be kept.
TRUSTED_CORROBORATION_DOMAINS = frozenset(
    {
        # Professional networks / funding databases
        "linkedin.com",
        "crunchbase.com",
        "dealroom.co",
        "ycombinator.com",
        "pitchbook.com",
        "tracxn.com",
        "cbinsights.com",
        "wellfound.com",
        "angel.co",
        "f6s.com",
        "github.com",
        # Tech and business press
        "techcrunch.com",
        "businesswire.com",
        "prnewswire.com",
        "globenewswire.com",
        "reuters.com",
        "venturebeat.com",
        "sifted.eu",
        "tech.eu",
        "eu-startups.com",
        "forbes.com",
        "bloomberg.com",
        "theinformation.com",
        "axios.com",
        "finsmes.com",
        "businessinsider.com",
        "fortune.com",
        "wired.com",
        "siliconangle.com",
        "fastcompany.com",
    }
)

_TOKEN_STOPWORDS = frozenset(
    {
        "inc",
        "llc",
        "ltd",
        "the",
        "and",
        "company",
        "technologies",
        "technology",
        "labs",
        "group",
        "holdings",
        "ai",
        "io",
        "app",
    }
)


def host_of(url: Any) -> str:
    try:
        return (urlparse(str(url or "")).hostname or "").lower().strip(".")
    except Exception:
        return ""


def is_anchor_host(host: str, anchor_host: str) -> bool:
    if not host or not anchor_host:
        return False
    return host == anchor_host or host.endswith("." + anchor_host)


def company_tokens(company_name: Optional[str]) -> List[str]:
    text = re.sub(r"[^a-z0-9 ]+", " ", str(company_name or "").lower())
    return [t for t in text.split() if len(t) >= 3 and t not in _TOKEN_STOPWORDS]


def source_mentions_company(
    source: Dict[str, Any],
    *,
    company_name: Optional[str],
    anchor_host: Optional[str],
) -> bool:
    """True when a source's own text refers to this company or its domain."""
    text = f"{source.get('title') or ''} {source.get('snippet') or ''} {source.get('url') or ''}".lower()
    if anchor_host:
        anchor_slug = registrable_domain(anchor_host).split(".", 1)[0]
        if anchor_host.lower() in text or (anchor_slug and anchor_slug in text):
            return True
    tokens = company_tokens(company_name)
    if not tokens:
        # Without a usable name the only safe signal is the anchor domain, which
        # was already checked above.
        return False
    return all(token in text for token in tokens)


def keep_source_for_anchor(
    source: Dict[str, Any],
    *,
    anchor_host: Optional[str],
    company_name: Optional[str],
) -> bool:
    """Whether a retrieved source survives anchoring to a known company domain."""
    if not anchor_host:
        return True
    host = host_of(source.get("url"))
    if is_anchor_host(host, anchor_host):
        return True
    if registrable_domain(host) in TRUSTED_CORROBORATION_DOMAINS:
        return source_mentions_company(
            source, company_name=company_name, anchor_host=anchor_host
        )
    return False


def filter_sources_to_anchor(
    sources: Iterable[Dict[str, Any]],
    *,
    anchor_host: Optional[str],
    company_name: Optional[str],
) -> List[Dict[str, Any]]:
    """Anchor-first filter that retains corroborating third-party coverage.

    Anchor-host sources are ordered first so the company's own pages stay the
    primary identity evidence, with corroboration following in retrieval order.
    """
    anchored: List[Dict[str, Any]] = []
    corroborating: List[Dict[str, Any]] = []
    for source in sources or []:
        if not isinstance(source, dict):
            continue
        if not anchor_host:
            anchored.append(source)
            continue
        if is_anchor_host(host_of(source.get("url")), anchor_host):
            anchored.append(source)
        elif keep_source_for_anchor(
            source, anchor_host=anchor_host, company_name=company_name
        ):
            corroborating.append(source)
    return anchored + corroborating
