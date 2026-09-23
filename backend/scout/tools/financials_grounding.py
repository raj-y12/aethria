"""Deterministic grounding for extracted financial facts.

Financial figures — funding history, valuation, traction/revenue, IP — are the
highest-trust-risk facts in the system: a single hallucinated valuation or made-up
ARR is a serious failure. So the scout LLM is only allowed to *propose* a financial
value together with (a) the exact source sentence it came from and (b) the source
URL. This module independently VERIFIES every proposal and DROPS anything it cannot
prove from the retrieved, allowlisted sources.

Guarantees (all enforced deterministically, no LLM involved):
  1. The cited source_url must be in the retrieval allowlist.
  2. The quoted sentence must appear verbatim (whitespace/punctuation-normalized)
     inside that source's retrieved snippet — a fabricated quote matches nothing.
  3. Every numeric figure in the proposed value must appear inside the quote — the
     model cannot attach a real sentence to a different number.

Any proposal failing any check is discarded and the field's *_missing flag is set.
A missing financial is always safer than a fabricated one, so every uncertain case
resolves to "missing". This module never estimates, infers, or repairs values.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# Scout-output financial sub-fields → the Financials model field they populate.
FINANCIAL_FIELDS = ("funding_history", "valuation_est", "traction_metrics", "ip_status")

# Financials.*_missing flags, keyed by the financial field that drives them.
_MISSING_FLAG = {
    "funding_history": "funding_missing",
    "valuation_est": "valuation_missing",
    "traction_metrics": "revenue_missing",
}

_SCALE = {
    "k": 1_000, "thousand": 1_000,
    "m": 1_000_000, "mm": 1_000_000, "million": 1_000_000,
    "b": 1_000_000_000, "bn": 1_000_000_000, "billion": 1_000_000_000,
}

# A figure: optional currency, a number (with commas/decimals), optional scale word/suffix.
_FIGURE_RE = re.compile(
    r"[$€£]?\s?\d[\d,]*(?:\.\d+)?\s?(?:k|mm|m|bn|b|thousand|million|billion)?",
    re.IGNORECASE,
)


def funding_history_for_stage(history: Optional[str], stage: Optional[str]) -> Optional[str]:
    """Withhold a claimed lifetime total that ends before the known funding stage.

    A source can accurately report an old total and still be unsuitable as the
    company's current total. Keep ordinary round histories; only an explicit
    lifetime-total claim with named, older rounds is withheld.
    """
    if not history or "total raised" not in history.lower():
        return history
    current = {"pre-seed": 0, "seed": 1, "series a": 2, "series b": 3,
               "series c": 4, "series c+": 4}.get((stage or "").strip().lower())
    if current is None:
        return history
    rounds = re.findall(r"\bpre[- ]?seed\b|\bseed\b|\bseries\s+[abc]\b", history.lower())
    ranks = {"pre-seed": 0, "pre seed": 0, "seed": 1, "series a": 2,
             "series b": 3, "series c": 4}
    return None if rounds and max(ranks[round_name] for round_name in rounds) < current else history


def _norm(text: Any) -> str:
    """Lowercase, unify dashes, drop punctuation that varies between source and quote,
    and collapse whitespace — so substring checks are robust to cosmetic differences."""
    t = str(text or "").lower()
    t = t.replace("–", "-").replace("—", "-").replace("’", "'")
    t = re.sub(r"[,’“”\"]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _canonical_amount(token: str) -> Optional[int]:
    """Convert a single figure token to an integer magnitude, e.g. '$5m' -> 5_000_000,
    '$1.2bn' -> 1_200_000_000, '500k' -> 500_000, '50' -> 50. None if not numeric."""
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(k|mm|m|bn|b|thousand|million|billion)?", token, re.IGNORECASE)
    if not m:
        return None
    try:
        num = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    scale = _SCALE.get((m.group(2) or "").lower(), 1)
    return int(round(num * scale))


def _figure_tokens(value: str) -> List[str]:
    """All digit-bearing figure tokens in a value string (deduped, stripped)."""
    out: List[str] = []
    seen = set()
    for raw in _FIGURE_RE.findall(value or ""):
        tok = raw.strip()
        if not any(ch.isdigit() for ch in tok):
            continue
        key = tok.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(tok)
    return out


def _figure_supported_by_quote(token: str, norm_quote: str, quote_amounts: set[int]) -> bool:
    """A figure in the value is supported iff its normalized text appears in the quote,
    OR its canonical magnitude matches a figure present in the quote (handles '$5M' vs
    '$5 million' vs '5,000,000')."""
    if _norm(token) in norm_quote:
        return True
    amount = _canonical_amount(token)
    return amount is not None and amount in quote_amounts


def verify_proposal(
    proposal: Any,
    sources_by_url: Dict[str, str],
) -> Optional[str]:
    """Return the cleaned value string iff the proposal is fully grounded, else None.

    `proposal` must be a dict: {"value": str, "quote": str, "source_url": str}.
    `sources_by_url` maps normalized allowlisted URL -> normalized snippet text.
    Anything malformed, uncited, mis-cited, or numerically unsupported returns None.
    """
    if not isinstance(proposal, dict):
        return None
    value = str(proposal.get("value") or "").strip()
    quote = str(proposal.get("quote") or "").strip()
    url = str(proposal.get("source_url") or "").strip()
    if not value or not quote or not url:
        return None

    # (1) cited source must be allowlisted/retrieved.
    snippet = sources_by_url.get(_norm_url(url))
    if snippet is None:
        return None

    # (2) the quoted sentence must really exist in that source's snippet.
    norm_quote = _norm(quote)
    if len(norm_quote) < 8 or norm_quote not in snippet:
        return None

    # (3) every figure in the value must be backed by the quote.
    quote_amounts = {
        amt for amt in (_canonical_amount(t) for t in _figure_tokens(quote)) if amt is not None
    }
    value_figures = _figure_tokens(value)
    if not value_figures:
        # No numbers to verify (e.g. "patents pending"): require the value's wording
        # itself to be grounded in the quote, so it can't be free-form invention.
        return value if _norm(value) in norm_quote else None
    for token in value_figures:
        if not _figure_supported_by_quote(token, norm_quote, quote_amounts):
            return None
    return value


def _norm_url(url: str) -> str:
    u = str(url or "").strip().lower().rstrip("/")
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    return u


def _build_sources_by_url(source_pack: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Normalized allowlisted-URL -> normalized snippet text. Only sources whose URL is
    in the allowlist are trusted; the snippet is what was actually retrieved/shown."""
    out: Dict[str, str] = {}
    if not isinstance(source_pack, dict):
        return out
    allowlist = {_norm_url(u) for u in (source_pack.get("url_allowlist") or set())}
    for src in source_pack.get("sources") or []:
        if not isinstance(src, dict):
            continue
        nu = _norm_url(src.get("url") or "")
        # Fixed 2026-08-17 (audit MEDIUM-A12): `allowlist and nu not in allowlist`
        # short-circuited to False when the allowlist was empty but `sources`
        # wasn't, silently trusting every source instead of none. Every
        # current caller keeps url_allowlist and sources in sync (empty
        # together), so this was latent, not live -- but a caller that
        # doesn't keep them in sync would have every source treated as
        # allowlisted, defeating the trust boundary this function exists to
        # enforce. Fail closed: an empty allowlist trusts nothing.
        if not nu or nu not in allowlist:
            continue
        snippet = _norm(f"{src.get('title') or ''} {src.get('snippet') or ''}")
        if snippet:
            # Concatenate if the same host appears more than once.
            out[nu] = (out.get(nu, "") + " " + snippet).strip()
    return out


def ground_financials(
    scout_output: Dict[str, Any],
    source_pack: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Verify the scout's proposed `financials` against retrieved sources.

    Returns a dict of Financials kwargs: verified string values (or None) plus the
    revenue_/funding_/valuation_missing flags. Drops every unverifiable proposal.
    """
    proposals = scout_output.get("financials")
    proposals = proposals if isinstance(proposals, dict) else {}
    sources_by_url = _build_sources_by_url(source_pack)

    result: Dict[str, Any] = {}
    for field in FINANCIAL_FIELDS:
        verified = verify_proposal(proposals.get(field), sources_by_url)
        result[field] = verified
        flag = _MISSING_FLAG.get(field)
        if flag:
            result[flag] = verified is None
    return result
