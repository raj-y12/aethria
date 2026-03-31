"""
Reference quality gates for Scout output: URL probes, parallel-domain rejection, hostname parsing.

- Filtering hallucinated or dead links (HTTP HEAD/GET).
- Rejecting same-brand wrong-TLD URLs (e.g. anchor aethria.co vs link aethria.com).
- Opt out with SKIP_REFERENCE_URL_VERIFY=1 (dev/tests).

Canonical / lookup anchor comes from lookup_website on the scout payload or
fund_identity.canonical_website in settings.
"""

from __future__ import annotations

import logging
import os
import re
import ssl
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import certifi

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://[^\s\]\)\"'<>]+", re.IGNORECASE)

# Multi-part public suffixes (registrable domain = last N labels).
_KNOWN_MULTI_SUFFIX = frozenset({
    "co.uk",
    "com.au",
    "co.nz",
    "co.jp",
    "com.br",
    "co.in",
    "com.mx",
    "org.uk",
    "net.au",
})

_SOFT_ACCEPT_HOST_SUFFIXES = (
    "linkedin.com",
    "linkedin.co",
    "twitter.com",
    "x.com",
)


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


def skip_reference_url_verify() -> bool:
    return _truthy_env("SKIP_REFERENCE_URL_VERIFY")


def hostname_from_user_hint(text: Optional[str]) -> Optional[str]:
    """Normalize URL or bare domain to lowercase hostname (no port)."""
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    if not re.match(r"https?://", s, re.I):
        s = "https://" + s
    try:
        p = urlparse(s)
        h = (p.hostname or "").lower().strip(".")
        return h or None
    except Exception:
        return None


def extract_http_urls(text: str) -> List[str]:
    if not text or not isinstance(text, str):
        return []
    out: List[str] = []
    for raw in _URL_RE.findall(text):
        u = raw.rstrip(".,;)'\"")
        if u and u not in out:
            out.append(u)
    return out


def registrable_domain(host: str) -> str:
    """
    Approximate registrable domain (eTLD+1 style) without PSL dependency.
    Handles common multi-part suffixes (e.g. foo.co.uk).
    """
    h = (host or "").lower().strip(".")
    parts = h.split(".")
    if len(parts) < 2:
        return h
    if len(parts) >= 3:
        s2 = f"{parts[-2]}.{parts[-1]}"
        if s2 in _KNOWN_MULTI_SUFFIX:
            return f"{parts[-3]}.{s2}"
    return f"{parts[-2]}.{parts[-1]}"


def is_parallel_same_slug_different_registrable(url_host: str, anchor_host: str) -> bool:
    """
    True if url_host looks like the same slug as anchor but a different registrable domain
    (e.g. aethria.com vs aethria.co). Third-party news domains are not affected.
    """
    uh = (url_host or "").lower().strip(".")
    ah = (anchor_host or "").lower().strip(".")
    if not uh or not ah:
        return False
    if uh == ah or uh.endswith("." + ah):
        return False
    ru, ra = registrable_domain(uh), registrable_domain(ah)
    if ru == ra:
        return False
    slug_u = ru.split(".")[0]
    slug_a = ra.split(".")[0]
    return slug_u == slug_a and bool(slug_u)


def reference_has_anchor_conflict(ref: str, anchor_host: str) -> bool:
    """True if any URL in ref is parallel-domain wrong TLD vs anchor."""
    if not anchor_host:
        return False
    for u in extract_http_urls(ref):
        try:
            h = (urlparse(u).hostname or "").lower().strip(".")
        except Exception:
            continue
        if h and is_parallel_same_slug_different_registrable(h, anchor_host):
            return True
    return False


def filter_references_anchor_conflicts(refs: List[Any], anchor_hostname: Optional[str]) -> List[str]:
    if not anchor_hostname:
        return [str(r).strip() for r in refs if isinstance(r, str) and str(r).strip()]
    kept: List[str] = []
    for r in refs:
        if not isinstance(r, str):
            continue
        s = r.strip()
        if not s:
            continue
        if reference_has_anchor_conflict(s, anchor_hostname):
            logger.info(
                "reference_verify: dropped anchor-conflicting reference (slug/TLD vs %s): %s",
                anchor_hostname,
                s[:120],
            )
            continue
        kept.append(s)
    return kept


def _host_suffix(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _soft_accept_url(url: str) -> bool:
    host = _host_suffix(url)
    return any(host == s or host.endswith("." + s) for s in _SOFT_ACCEPT_HOST_SUFFIXES)


def http_reachable(url: str, timeout: float = 4.0) -> bool:
    ctx = ssl.create_default_context(cafile=certifi.where())
    headers = {"User-Agent": "AethriaReferenceCheck/1.0 (verification)"}

    def get_fallback() -> bool:
        try:
            req = Request(url, method="GET", headers=headers)
            with urlopen(req, timeout=timeout, context=ctx) as resp:
                code = getattr(resp, "status", None) or resp.getcode()
                return 200 <= int(code) < 400
        except HTTPError as e:
            return 200 <= e.code < 400
        except Exception:
            return False

    try:
        req = Request(url, method="HEAD", headers=headers)
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            return 200 <= int(code) < 400
    except HTTPError as e:
        c = e.code
        if c in (405, 501):
            return get_fallback()
        return 200 <= c < 400
    except URLError:
        return False
    except Exception:
        return False


def reference_string_verified(ref: str, timeout: float = 4.0) -> bool:
    from utils.reference_validation import is_generic_reference

    if not isinstance(ref, str) or not ref.strip() or is_generic_reference(ref):
        return False
    urls = extract_http_urls(ref)
    if not urls:
        return False
    for u in urls[:3]:
        if http_reachable(u, timeout=timeout):
            return True
        if _soft_accept_url(u):
            logger.info("reference_verify: soft-accept URL (probe inconclusive): %s", u[:80])
            return True
    return False


def filter_references_by_url_probe(output: Dict[str, Any], timeout: float = 4.0) -> Dict[str, Any]:
    if skip_reference_url_verify():
        return output
    refs = output.get("references")
    if not isinstance(refs, list):
        return output
    kept: List[str] = []
    for r in refs:
        if not isinstance(r, str):
            continue
        s = r.strip()
        if not s:
            continue
        if reference_string_verified(s, timeout=timeout):
            kept.append(s)
        else:
            logger.info("reference_verify: dropped unverified reference: %s", s[:120])
    output["references"] = kept
    return output


def finalize_scout_references(
    output: Dict[str, Any],
    *,
    anchor_hostname: Optional[str] = None,
    probe_timeout: float = 4.0,
) -> Dict[str, Any]:
    """
    Apply anchor conflict filtering (wrong TLD for same slug), then URL probes.
    Mutates output['references'].
    """
    refs = output.get("references")
    if not isinstance(refs, list):
        return output
    cleaned = filter_references_anchor_conflicts(refs, anchor_hostname)
    output["references"] = cleaned
    return filter_references_by_url_probe(output, timeout=probe_timeout)
