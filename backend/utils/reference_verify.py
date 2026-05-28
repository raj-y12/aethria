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
from typing import Any, Dict, List, Optional, Tuple
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
    # Directory/funding profiles often block probes or rate-limit HEAD/GET.
    # Soft-accept keeps on-demand lookup from failing purely on probe transport noise.
    "crunchbase.com",
    "pitchbook.com",
)

_TRUSTED_SOURCE_SUFFIXES = (
    "crunchbase.com",
    "pitchbook.com",
    "techcrunch.com",
    "businesswire.com",
    "prnewswire.com",
    "globenewswire.com",
    "linkedin.com",
    "github.com",
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


def normalize_url_for_match(url: str) -> str:
    """
    Normalize URL for allowlist matching.
    Intentionally ignores scheme, query, and fragment so equivalent URLs match:
    - http vs https
    - www prefix
    - trailing slash
    """
    try:
        p = urlparse(url.strip())
    except Exception:
        return ""
    host = (p.netloc or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    path = (p.path or "").rstrip("/")
    if not host:
        return ""
    return f"{host}{path}"


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
            logger.warning(
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


def probe_url_status(url: str, timeout: float = 4.0) -> str:
    """
    Probe URL status with a conservative tri-state result:
    - reachable: request completed with a usable success/redirect code
    - unreachable: request completed with a hard-negative status
    - inconclusive: transport noise, rate limiting, auth walls, or other ambiguous failures
    """
    ctx = ssl.create_default_context(cafile=certifi.where())
    headers = {"User-Agent": "AethriaReferenceCheck/1.0 (verification)"}

    def classify_http_code(code: int) -> str:
        if 200 <= code < 400:
            return "reachable"
        if code in (401, 403, 405, 408, 409, 425, 429, 500, 502, 503, 504):
            return "inconclusive"
        return "unreachable"

    def get_fallback() -> str:
        try:
            req = Request(url, method="GET", headers=headers)
            with urlopen(req, timeout=timeout, context=ctx) as resp:
                code = getattr(resp, "status", None) or resp.getcode()
                return classify_http_code(int(code))
        except HTTPError as e:
            return classify_http_code(int(e.code))
        except Exception:
            return "inconclusive"

    try:
        req = Request(url, method="HEAD", headers=headers)
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            return classify_http_code(int(code))
    except HTTPError as e:
        c = e.code
        if c in (405, 501):
            return get_fallback()
        return classify_http_code(int(c))
    except URLError:
        return "inconclusive"
    except Exception:
        return "inconclusive"


def http_reachable(url: str, timeout: float = 4.0) -> bool:
    return probe_url_status(url, timeout=timeout) == "reachable"


def reference_string_verified(ref: str, timeout: float = 4.0) -> bool:
    from utils.reference_validation import is_generic_reference

    if not isinstance(ref, str) or not ref.strip() or is_generic_reference(ref):
        return False
    urls = extract_http_urls(ref)
    if not urls:
        return False
    for u in urls[:3]:
        status = probe_url_status(u, timeout=timeout)
        if status == "reachable":
            return True
        if status == "inconclusive" or _soft_accept_url(u):
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
        urls = extract_http_urls(s)
        hard_negative = False
        soft_accept = False
        for u in urls[:3]:
            status = probe_url_status(u, timeout=timeout)
            if status == "reachable":
                soft_accept = True
                break
            if status == "inconclusive" or _soft_accept_url(u):
                soft_accept = True
                break
            if status == "unreachable":
                hard_negative = True
        if soft_accept or not hard_negative:
            kept.append(s)
        else:
            logger.warning("reference_verify: dropped hard-dead reference: %s", s[:120])
    if not kept and refs:
        logger.warning(
            "reference_verify: all %d reference(s) failed URL probe — "
            "company may be valid but temporarily unreachable; startup will be skipped this cycle",
            len(refs),
        )
    output["references"] = kept
    return output


def _company_tokens(company_name: Optional[str]) -> List[str]:
    text = re.sub(r"[^a-z0-9 ]+", " ", (company_name or "").lower())
    stop = {"ai", "inc", "ltd", "llc", "the", "and", "company", "technologies", "technology", "labs"}
    return [t for t in text.split() if len(t) >= 3 and t not in stop]


def _text_tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (value or "").lower()))


def _host_identity_tokens(host: str) -> set[str]:
    h = (host or "").lower().strip(".")
    if not h:
        return set()
    reg = registrable_domain(h)
    slug = reg.split(".", 1)[0]
    parts = set(re.findall(r"[a-z0-9]+", slug))
    parts.add(slug)
    return {p for p in parts if p}


def _reference_company_match(ref: str, *, company_name: Optional[str], host: str) -> bool:
    tokens = _company_tokens(company_name)
    if not tokens:
        return True
    ref_tokens = _text_tokens(ref)
    host_tokens = _host_identity_tokens(host)
    all_tokens = set(tokens)
    compact = "".join(tokens)

    if compact and compact in host_tokens:
        return True
    if all_tokens.issubset(ref_tokens):
        return True
    if all_tokens.issubset(host_tokens):
        return True
    if len(tokens) == 1:
        token = tokens[0]
        return token in ref_tokens or token in host_tokens
    return False


def _reference_support_note(ref: str, company_name: Optional[str]) -> str:
    lowered = ref.lower()
    if any(x in lowered for x in ("funding", "raised", "series", "seed", "investor")):
        return "Funding or investor evidence"
    if any(x in lowered for x in ("customer", "pilot", "revenue", "arr", "users", "traction")):
        return "Traction or customer evidence"
    if any(x in lowered for x in ("founder", "ceo", "cto", "team", "leadership")):
        return "Founder or team evidence"
    if company_name and any(t in lowered for t in _company_tokens(company_name)):
        return "Company identity evidence"
    return "Supporting source"


def _rank_reference(ref: str, company_name: Optional[str], anchor_hostname: Optional[str]) -> Tuple[int, str]:
    urls = extract_http_urls(ref)
    host = ""
    if urls:
        try:
            host = (urlparse(urls[0]).hostname or "").lower()
        except Exception:
            host = ""
    score = 0
    if anchor_hostname and host:
        ah = anchor_hostname.lower().removeprefix("www.")
        hh = host.removeprefix("www.")
        if hh == ah or hh.endswith("." + ah):
            score += 100
    if host and any(host == s or host.endswith("." + s) for s in _TRUSTED_SOURCE_SUFFIXES):
        score += 35
    lowered = ref.lower()
    for token in _company_tokens(company_name):
        if token in _text_tokens(lowered) or (host and token in _host_identity_tokens(host)):
            score += 20
    if any(x in lowered for x in ("2026", "2025", "2024", "2023", "raised", "launch", "announces")):
        score += 8
    return (-score, normalize_url_for_match(urls[0]) if urls else ref.lower())


def filter_references_by_company_relevance(
    refs: List[Any],
    *,
    company_name: Optional[str],
    anchor_hostname: Optional[str],
) -> List[str]:
    tokens = _company_tokens(company_name)
    seen: set[str] = set()
    kept: List[str] = []
    dropped = 0
    for raw in refs:
        if not isinstance(raw, str):
            dropped += 1
            continue
        ref = raw.strip()
        if not ref:
            dropped += 1
            continue
        urls = extract_http_urls(ref)
        norm = normalize_url_for_match(urls[0]) if urls else ref.lower()
        if norm in seen:
            dropped += 1
            continue
        seen.add(norm)
        lowered = ref.lower()
        host = ""
        if urls:
            try:
                host = (urlparse(urls[0]).hostname or "").lower()
            except Exception:
                host = ""
        anchor_match = False
        if anchor_hostname and host:
            ah = anchor_hostname.lower().removeprefix("www.")
            hh = host.removeprefix("www.")
            anchor_match = hh == ah or hh.endswith("." + ah)
        token_match = _reference_company_match(ref, company_name=company_name, host=host)
        if not (anchor_match or token_match):
            logger.warning(
                "reference_verify: dropped company-irrelevant reference company=%s ref=%s",
                (company_name or "")[:80],
                ref[:160],
            )
            dropped += 1
            continue
        kept.append(ref)
    kept.sort(key=lambda r: _rank_reference(r, company_name, anchor_hostname))
    if dropped:
        logger.info(
            "reference_verify: source_filter company=%s kept=%d dropped=%d",
            (company_name or "")[:80],
            len(kept),
            dropped,
        )
    return kept[:8]


def build_source_evidence(refs: List[str], *, company_name: Optional[str]) -> List[Dict[str, str]]:
    evidence: List[Dict[str, str]] = []
    for ref in refs:
        urls = extract_http_urls(ref)
        evidence.append(
            {
                "reference": ref,
                "url": urls[0] if urls else "",
                "supports": _reference_support_note(ref, company_name),
            }
        )
    return evidence


def filter_references_to_allowlist(refs: List[Any], allowlist_urls: List[str]) -> Dict[str, Any]:
    """
    Keep references when at least one cited URL matches retrieval allowlist by:
    1) exact normalized URL, or
    2) same normalized host (path differences allowed).
    """
    normalized_allow = {normalize_url_for_match(u) for u in allowlist_urls if isinstance(u, str)}
    normalized_allow.discard("")
    allow_hosts = {
        x.split("/", 1)[0]
        for x in normalized_allow
        if "/" in x or x
    }
    kept: List[str] = []
    dropped = 0
    for r in refs:
        if not isinstance(r, str):
            dropped += 1
            continue
        s = r.strip()
        if not s:
            dropped += 1
            continue
        urls = [normalize_url_for_match(u) for u in extract_http_urls(s)]
        urls = [u for u in urls if u]
        url_hosts = {
            u.split("/", 1)[0]
            for u in urls
            if "/" in u or u
        }
        if any(u in normalized_allow for u in urls) or any(h in allow_hosts for h in url_hosts):
            kept.append(s)
        else:
            dropped += 1
    return {"kept": kept, "dropped_count": dropped}


def finalize_scout_references(
    output: Dict[str, Any],
    *,
    anchor_hostname: Optional[str] = None,
    company_name: Optional[str] = None,
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
    cleaned = filter_references_by_company_relevance(
        cleaned,
        company_name=company_name or output.get("name"),
        anchor_hostname=anchor_hostname,
    )
    output["references"] = cleaned
    output = filter_references_by_url_probe(output, timeout=probe_timeout)
    final_refs = output.get("references")
    if isinstance(final_refs, list):
        output["source_evidence"] = build_source_evidence(
            [str(r) for r in final_refs if isinstance(r, str)],
            company_name=company_name or output.get("name"),
        )
    return output
