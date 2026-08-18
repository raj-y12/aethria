"""
Company Resolver: stage 1 of every on-demand lookup.

Takes a typed company name (messy: aliases, old names, LinkedIn names, domains,
Crunchbase slugs) and attempts to identify the real company using layered
fallback searches before any scout/enrichment/scoring runs.

Design rules (analyst, not judge):
- Weak retrieval is NOT failure. Some evidence => PARTIAL / LOW_CONFIDENCE /
  NEEDS_REVIEW with explicit found/missing fields, never a silent drop.
- NOT_FOUND only when there is genuinely no credible evidence at all.
- Every stage logs: query used, sources found, confidence, decision reason,
  status assigned, and missing evidence — persisted on the resolution itself
  (stage_log) so the UI/memo can explain what happened.

Deterministic by design: no LLM call here. The scout LLM runs AFTER identity
resolution and consumes the resolver's evidence pack.
"""
from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from tenant_context import require_user_id
from utils.reference_verify import hostname_from_user_hint, registrable_domain
from utils.retrieval_grounding import retrieve_source_pack_merged
from utils.search_providers import extract_pages

logger = logging.getLogger("resolver.company")

ResolutionStatus = Literal["FOUND", "PARTIAL", "LOW_CONFIDENCE", "NEEDS_REVIEW", "NOT_FOUND"]

RESOLUTION_STATUSES: tuple[str, ...] = (
    "FOUND",
    "PARTIAL",
    "LOW_CONFIDENCE",
    "NEEDS_REVIEW",
    "NOT_FOUND",
)

# Hosts that are evidence ABOUT a company but never the company's own website.
_PLATFORM_REGISTRABLE_DOMAINS = frozenset(
    {
        "linkedin.com",
        "crunchbase.com",
        "dealroom.co",
        "ycombinator.com",
        "pitchbook.com",
        "tracxn.com",
        "cbinsights.com",
        "twitter.com",
        "x.com",
        "facebook.com",
        "instagram.com",
        "youtube.com",
        "wikipedia.org",
        "github.com",
        "medium.com",
        "substack.com",
        "reddit.com",
        "glassdoor.com",
        "indeed.com",
        "g2.com",
        "producthunt.com",
        "apollo.io",
        "zoominfo.com",
        "owler.com",
        "wellfound.com",
        "angel.co",
        "f6s.com",
        "google.com",
        "bing.com",
    }
)

_NEWS_REGISTRABLE_DOMAINS = frozenset(
    {
        "techcrunch.com",
        "businesswire.com",
        "prnewswire.com",
        "globenewswire.com",
        "reuters.com",
        "bloomberg.com",
        "forbes.com",
        "businessinsider.com",
        "theinformation.com",
        "venturebeat.com",
        "sifted.eu",
        "eu-startups.com",
        "tech.eu",
        "axios.com",
        "wsj.com",
        "ft.com",
        "cnbc.com",
        "fortune.com",
        "wired.com",
        "theverge.com",
        "finsmes.com",
        "siliconangle.com",
        # General-news aggregators / outlets: they host articles ABOUT companies,
        # so they are evidence, never company candidates or identity sources.
        "yahoo.com",
        "msn.com",
        "cnn.com",
        "nytimes.com",
        "theguardian.com",
        "bbc.com",
        "bbc.co.uk",
        "washingtonpost.com",
        "apnews.com",
        "nbcnews.com",
        "cbsnews.com",
        "marketwatch.com",
        "seekingalpha.com",
        "fool.com",
        "barrons.com",
        "fastcompany.com",
        "inc.com",
        "entrepreneur.com",
        "cnet.com",
        "zdnet.com",
        "engadget.com",
        "mashable.com",
        "time.com",
        "newsweek.com",
        "economist.com",
    }
)

_NAME_STOPWORDS = frozenset(
    {
        "inc",
        "llc",
        "ltd",
        "gmbh",
        "sas",
        "bv",
        "corp",
        "co",
        "company",
        "the",
        "and",
        "labs",
        "technologies",
        "technology",
        "systems",
        "group",
        "holdings",
        "app",
        "hq",
        "ai",
        "io",
    }
)

_FOUNDER_PATTERNS = (
    re.compile(
        r"(?:founded|co-?founded|started|launched)\s+(?:in\s+\d{4}\s+)?by\s+"
        r"([A-Z][\w'’.-]+(?:\s+[A-Z][\w'’.-]+){1,2}(?:\s*(?:,|and)\s*[A-Z][\w'’.-]+(?:\s+[A-Z][\w'’.-]+){1,2})*)"
    ),
    re.compile(
        r"([A-Z][\w'’.-]+(?:\s+[A-Z][\w'’.-]+){1,2})\s*(?:,|–|-|—)\s*"
        r"(?:is\s+the\s+)?(?:co-?founder|founder|ceo|cto|coo)\b",
    ),
    re.compile(
        r"(?:(?i:CEO|CTO|chief executive|co-?founder|founder))\s*(?:[:\-–—]\s*)"
        r"([A-Z][\w'’.-]+\s+[A-Z][\w'’.-]+)"
    ),
    re.compile(
        r"(?:(?i:founding team|founders?|co-?founders?))\s*[:\-–—]\s*"
        r"([A-Z][\w'’.-]+(?:\s+[A-Z][\w'’.-]+){1,2}(?:\s*(?:,|and|&)\s*[A-Z][\w'’.-]+(?:\s+[A-Z][\w'’.-]+){1,2})+)"
    ),
)

# Guards a founder-role match against attribution to a company mentioned in the
# same sentence: "Mitchell Hashimoto, Co-Founder of HashiCorp" must not credit
# Mitchell Hashimoto as a founder of the *target* company just because the
# sentence itself is about that target (e.g. a board-appointment announcement).
_FOUNDER_OF_OTHER_COMPANY_RE = re.compile(
    r"^\s*of\s+([A-Z][\w&.,'’-]*(?:\s+[A-Z][\w&.,'’-]*){0,3})"
)

_FOUNDER_NAME_REJECT = frozenset(
    {
        "the company",
        "the startup",
        "series a",
        "series b",
        "san francisco",
        "new york",
        "y combinator",
        "the team",
    }
)


class EvidenceSource(BaseModel):
    """One retrieved source supporting (or contextualizing) the company identity."""

    url: str
    title: str = ""
    snippet: str = ""
    source_type: Literal[
        "official_site",
        "linkedin",
        "crunchbase",
        "dealroom",
        "yc",
        "news",
        "directory",
        "other",
        "user_hint",
    ] = "other"
    match_score: float = 0.0
    supports: str = ""


class AlternativeMatch(BaseModel):
    """A plausible different entity the typed name could have meant."""

    name: str
    website: Optional[str] = None
    reason: str = ""
    match_score: float = 0.0


class CompanyCandidate(BaseModel):
    """A distinct company-owned entity the typed name could refer to.

    Used by the dispatch disambiguation picker: each candidate is one
    registrable domain (so foo.ie and foo.com are separate companies).
    """

    name: str
    website: str
    description: str = ""
    confidence: float = 0.0
    source_badges: List[str] = Field(default_factory=list)


class ResolutionStageLog(BaseModel):
    """Per-stage debug record: what we asked, what we got, what we decided."""

    stage: str
    queries: List[str] = Field(default_factory=list)
    sources_found: int = 0
    confidence: Optional[float] = None
    decision: str = ""
    reason: str = ""
    missing: List[str] = Field(default_factory=list)


class CompanyResolution(BaseModel):
    """
    Resolver output contract. Persisted on the scout row (scout_info.company_resolution)
    and surfaced in the UI so weak lookups are explainable rather than gone.
    """

    query: str
    canonical_name: str
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    crunchbase_url: Optional[str] = None
    dealroom_url: Optional[str] = None
    yc_url: Optional[str] = None
    founder_names: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    confidence: float = 0.0
    resolution_status: str = "NOT_FOUND"
    alternative_matches: List[AlternativeMatch] = Field(default_factory=list)
    candidates: List[CompanyCandidate] = Field(default_factory=list)
    evidence_sources: List[EvidenceSource] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    queries_used: List[str] = Field(default_factory=list)
    stage_log: List[ResolutionStageLog] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    retrieval_provider: Optional[str] = None

    def has_any_evidence(self) -> bool:
        return bool(self.evidence_sources) or bool(self.website)

    def summary_line(self) -> str:
        found = [f for f in ("website", "linkedin_url", "crunchbase_url") if getattr(self, f)]
        return (
            f"status={self.resolution_status} confidence={self.confidence:.2f} "
            f"found={','.join(found) or 'none'} missing={','.join(self.missing_fields) or 'none'}"
        )


def _name_tokens(name: str) -> List[str]:
    text = re.sub(r"[^a-z0-9 ]+", " ", (name or "").lower())
    return [t for t in text.split() if len(t) >= 2 and t not in _NAME_STOPWORDS]


def _compact_name(name: str) -> str:
    return "".join(_name_tokens(name)) or re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def _host_of(url: str) -> str:
    from urllib.parse import urlparse

    try:
        return (urlparse(url).hostname or "").lower().strip(".")
    except Exception:
        return ""


def _slug_similarity(company_name: str, host: str) -> float:
    """0..1 similarity between the company name and a host's registrable slug."""
    slug = registrable_domain(host).split(".", 1)[0]
    compact = _compact_name(company_name)
    if not slug or not compact:
        return 0.0
    if slug == compact:
        return 1.0
    if compact in slug or slug in compact:
        return 0.85
    return SequenceMatcher(None, compact, slug).ratio()


def _text_name_match(company_name: str, text: str) -> float:
    """0..1: how strongly a title/snippet mentions the typed company name."""
    tokens = _name_tokens(company_name)
    if not tokens:
        return 0.0
    lowered = (text or "").lower()
    hits = sum(1 for t in tokens if t in lowered)
    if hits == len(tokens):
        return 1.0
    return hits / len(tokens)


def _classify_source(url: str) -> str:
    host = _host_of(url)
    reg = registrable_domain(host)
    path = url.lower()
    if reg == "linkedin.com":
        return "linkedin" if "/company/" in path or "/school/" in path else "other"
    if reg == "crunchbase.com":
        return "crunchbase" if "/organization/" in path else "directory"
    if reg == "dealroom.co":
        return "dealroom"
    if reg == "ycombinator.com":
        return "yc" if "/companies/" in path else "other"
    if reg in _NEWS_REGISTRABLE_DOMAINS:
        return "news"
    if reg in _PLATFORM_REGISTRABLE_DOMAINS:
        return "directory"
    return "official_site_candidate"


def _profile_slug(url: str) -> str:
    """Return the platform's company slug from a supported profile URL."""
    from urllib.parse import unquote, urlparse

    path = unquote(urlparse(url).path).strip("/")
    parts = [part for part in path.split("/") if part]
    if not parts:
        return ""
    for marker in ("company", "organization", "companies"):
        lowered = [part.lower() for part in parts]
        if marker in lowered:
            index = lowered.index(marker)
            if index + 1 < len(parts):
                return parts[index + 1]
    return parts[-1]


def _profile_matches_anchor(
    source: EvidenceSource,
    *,
    company: str,
    anchor_host: Optional[str],
) -> bool:
    """Require a platform profile's own slug to match the identity anchor.

    Search-result titles are intentionally not sufficient: a page titled
    "Aethria Solutions" still contains the queried token "Aethria". Profile
    slugs are the stable cross-source identifier available without fetching a
    page, and exact normalized equality avoids substring collisions.
    """
    if source.source_type == "official_site":
        # Fixed 2026-08-17 (live-observed on Anthropic): _score_and_collect_sources
        # classifies ANY domain whose slug resembles the company name as
        # "official_site" via `slug_sim >= 0.55` -- independent of whether it
        # actually matches the resolved anchor domain. Without this check, a
        # same-named different company (anthropic.io, a UK VC fund) got
        # "official_site" purely by name similarity, and this function used
        # to treat every official_site source as anchor-matching unconditionally
        # -- so its description overwrote the real company's (anthropic.com,
        # the AI lab) even though the resolver's own website field was
        # correctly anchored. Only enforce when an anchor is actually known;
        # without one there's nothing to check against.
        if not anchor_host:
            return True
        host = _host_of(source.url)
        return bool(host) and (host == anchor_host or host.endswith("." + anchor_host))
    if source.source_type not in {"linkedin", "crunchbase", "dealroom", "yc"}:
        return True
    target = registrable_domain(_host_of(anchor_host or "")) if anchor_host else ""
    target_slug = target.split(".", 1)[0] if target else _compact_name(company)
    profile_slug = _compact_name(_profile_slug(source.url))
    if not target_slug or not profile_slug:
        return False
    if profile_slug == _compact_name(target_slug):
        return True
    # A result can corroborate the anchor when the page explicitly names the
    # anchored domain, even if the platform chose a non-identical slug.
    if anchor_host:
        text = f"{source.title} {source.snippet}".lower()
        return anchor_host.lower() in text or f"www.{anchor_host.lower()}" in text
    return False


def _founder_sources(
    sources: List[EvidenceSource],
    *,
    company: str,
    anchor_host: Optional[str],
) -> List[EvidenceSource]:
    """Keep only identity-correlated sources eligible to name founders."""
    return [
        source
        for source in sources
        if source.match_score >= 0.34
        and _profile_matches_anchor(source, company=company, anchor_host=anchor_host)
    ]


def _extract_attached_profile(
    resolution: CompanyResolution,
    sources: List[EvidenceSource],
    *,
    company: str,
    anchor_host: Optional[str],
) -> None:
    """Best-effort fetch of one attached profile to recover structured facts."""
    attached_urls = [
        resolution.yc_url,
        resolution.linkedin_url,
        resolution.crunchbase_url,
        resolution.dealroom_url,
    ]
    url = next((candidate for candidate in attached_urls if candidate), None)
    if not url:
        return
    attached = next(
        (
            source
            for source in sources
            if source.url.lower().rstrip("/") == url.lower().rstrip("/")
            and _profile_matches_anchor(source, company=company, anchor_host=anchor_host)
        ),
        None,
    )
    if attached is None:
        return
    try:
        extracted = extract_pages([url])
    except Exception as exc:
        logger.warning("resolver profile extraction failed url=%s: %s", url, exc)
        return
    for page in extracted:
        content = str(page.get("content") or "").strip()
        if content:
            attached.snippet = content[:12000]
            resolution.notes.append(
                f"Founder evidence extracted from attached {attached.source_type} profile."
            )
            return


def _build_queries(company: str, *, phase: int, website_hint: Optional[str]) -> List[str]:
    """Layered fallback queries. Phase 1 = identity, phase 2 = corroboration."""
    c = company.strip()
    if phase == 1:
        queries = [
            f'"{c}" company official website',
            f"{c} startup",
            f'site:linkedin.com/company "{c}"',
            f'site:crunchbase.com/organization "{c}"',
        ]
        host = hostname_from_user_hint(website_hint)
        if host:
            queries.insert(0, f"{c} {host}")
            queries.insert(1, f"site:{host} founders team about leadership")
        return queries
    return [
        f"{c} founder CEO",
        f"{c} funding raised seed",
        f"{c} Y Combinator YC",
        f"{c} product launch",
    ]


def _extract_founders(sources: List[EvidenceSource], *, company: str = "") -> List[str]:
    target_compact = _compact_name(company) if company else ""
    found: List[str] = []
    for src in sources:
        text = f"{src.title}. {src.snippet}"
        for pattern in _FOUNDER_PATTERNS:
            for match in pattern.finditer(text):
                if target_compact:
                    trailing = text[match.end():match.end() + 60]
                    of_match = _FOUNDER_OF_OTHER_COMPANY_RE.match(trailing)
                    if of_match:
                        mentioned_compact = _compact_name(of_match.group(1))
                        if mentioned_compact and mentioned_compact != target_compact:
                            continue
                blob = match.group(1)
                for raw in re.split(r"\s*(?:,|and)\s*", blob):
                    name = raw.strip(" .,'’-")
                    if not name or len(name) > 40:
                        continue
                    if name.lower() in _FOUNDER_NAME_REJECT:
                        continue
                    name = re.sub(r"^(?:and|&|,|;|:)\s+", "", name, flags=re.IGNORECASE)
                    if len(name.split()) < 2:
                        continue
                    if name not in found:
                        found.append(name)
    return found[:5]


def _pick_description(sources: List[EvidenceSource]) -> Optional[str]:
    priority = ("official_site", "linkedin", "crunchbase", "yc", "dealroom", "news")
    for wanted in priority:
        for src in sources:
            if src.source_type == wanted and src.snippet and len(src.snippet) >= 40:
                text = re.sub(r"\s+", " ", src.snippet).strip()
                return text[:400]
    for src in sources:
        if src.snippet:
            return re.sub(r"\s+", " ", src.snippet).strip()[:400]
    return None


def _log_stage(
    resolution: CompanyResolution,
    *,
    stage: str,
    queries: List[str],
    sources_found: int,
    decision: str,
    reason: str,
    confidence: Optional[float] = None,
    missing: Optional[List[str]] = None,
) -> None:
    entry = ResolutionStageLog(
        stage=stage,
        queries=queries,
        sources_found=sources_found,
        confidence=confidence,
        decision=decision,
        reason=reason,
        missing=missing or [],
    )
    resolution.stage_log.append(entry)
    logger.info(
        "resolver stage=%s company=%s queries=%d sources=%d confidence=%s decision=%s reason=%s missing=%s",
        stage,
        resolution.query[:60],
        len(queries),
        sources_found,
        f"{confidence:.2f}" if confidence is not None else "-",
        decision,
        reason[:160],
        ",".join(missing or []) or "-",
    )


def _score_and_collect_sources(
    company: str,
    raw_sources: List[Dict[str, Any]],
    *,
    anchor_host: Optional[str],
) -> List[EvidenceSource]:
    out: List[EvidenceSource] = []
    seen: set[str] = set()
    for row in raw_sources:
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        key = url.lower().rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        title = str(row.get("title") or "").strip()
        snippet = str(row.get("snippet") or "").strip()
        host = _host_of(url)
        kind = _classify_source(url)

        slug_sim = _slug_similarity(company, host) if kind == "official_site_candidate" else 0.0
        text_match = _text_name_match(company, f"{title} {snippet}")
        anchor_match = bool(
            anchor_host and host and (host == anchor_host or host.endswith("." + anchor_host))
        )
        score = max(slug_sim, text_match)
        if anchor_match:
            score = 1.0

        # Keep weakly-matching sources too (they may be the only evidence), but
        # mark genuinely unrelated noise so it never drives identity fields.
        if kind == "official_site_candidate":
            source_type = "official_site" if (anchor_match or slug_sim >= 0.55) else "other"
        else:
            source_type = kind  # linkedin / crunchbase / dealroom / yc / news / directory / other

        supports = {
            "official_site": "Company identity (official website)",
            "linkedin": "Company identity (LinkedIn company page)",
            "crunchbase": "Company identity (Crunchbase profile)",
            "dealroom": "Company identity (Dealroom profile)",
            "yc": "Company identity (Y Combinator profile)",
            "news": "News mention",
            "directory": "Directory mention",
            "other": "Context",
        }[source_type]

        out.append(
            EvidenceSource(
                url=url,
                title=title,
                snippet=snippet[:1200],
                source_type=source_type,
                match_score=round(score, 3),
                supports=supports,
            )
        )
    out.sort(key=lambda s: s.match_score, reverse=True)
    return out


def _assign_identity_fields(
    resolution: CompanyResolution,
    company: str,
    sources: List[EvidenceSource],
    *,
    anchor_host: Optional[str],
    website_hint: Optional[str],
) -> None:
    """Pick website / linkedin / crunchbase / dealroom / yc from scored evidence."""
    min_match = 0.5
    if website_hint:
        hint = website_hint.strip()
        resolution.website = (
            hint if hint.lower().startswith(("http://", "https://")) else f"https://{hint}"
        )
        resolution.notes.append("Website taken from user-provided hint.")
    else:
        official = [
            s for s in sources if s.source_type == "official_site" and s.match_score >= min_match
        ]
        if official:
            best = official[0]
            resolution.website = f"https://{_host_of(best.url)}"

    # Alternative official-site candidates that were NOT picked (different registrable domain).
    picked_reg = registrable_domain(_host_of(resolution.website)) if resolution.website else ""
    for s in sources:
        if s.source_type not in ("official_site", "other"):
            continue
        host = _host_of(s.url)
        reg = registrable_domain(host)
        if not reg or reg in _PLATFORM_REGISTRABLE_DOMAINS or reg in _NEWS_REGISTRABLE_DOMAINS:
            continue
        if picked_reg and reg == picked_reg:
            continue
        sim = _slug_similarity(company, host)
        if sim >= 0.55 and all(a.website != f"https://{reg}" for a in resolution.alternative_matches):
            resolution.alternative_matches.append(
                AlternativeMatch(
                    name=reg.split(".", 1)[0],
                    website=f"https://{reg}",
                    reason=f"Similarly named domain ({reg}) also matches the typed name.",
                    match_score=round(sim, 3),
                )
            )
    resolution.alternative_matches = resolution.alternative_matches[:4]

    profile_anchor = anchor_host or (_host_of(resolution.website) if resolution.website else None)
    for s in sources:
        if not _profile_matches_anchor(s, company=company, anchor_host=profile_anchor):
            continue
        if s.source_type == "linkedin" and not resolution.linkedin_url and s.match_score >= 0.34:
            resolution.linkedin_url = s.url
        elif s.source_type == "crunchbase" and not resolution.crunchbase_url and s.match_score >= 0.34:
            resolution.crunchbase_url = s.url
        elif s.source_type == "dealroom" and not resolution.dealroom_url and s.match_score >= 0.34:
            resolution.dealroom_url = s.url
        elif s.source_type == "yc" and not resolution.yc_url and s.match_score >= 0.34:
            resolution.yc_url = s.url


def _compute_confidence(resolution: CompanyResolution, *, website_hint: Optional[str]) -> float:
    score = 0.0
    if resolution.website:
        score += 0.45 if website_hint else 0.35
    if resolution.linkedin_url:
        score += 0.2
    if resolution.crunchbase_url or resolution.dealroom_url or resolution.yc_url:
        score += 0.15
    if resolution.founder_names:
        score += 0.05
    news = [s for s in resolution.evidence_sources if s.source_type == "news" and s.match_score >= 0.5]
    score += min(0.15, 0.05 * len(news))
    if resolution.description:
        score += 0.05
    return round(max(0.0, min(1.0, score)), 3)


def _compute_missing_fields(resolution: CompanyResolution) -> List[str]:
    missing: List[str] = []
    if not resolution.website:
        missing.append("website")
    if not resolution.linkedin_url:
        missing.append("linkedin_url")
    if not (resolution.crunchbase_url or resolution.dealroom_url or resolution.yc_url):
        missing.append("funding_profile")
    if not resolution.founder_names:
        missing.append("founder_names")
    if not resolution.description:
        missing.append("description")
    if not any(s.source_type == "news" for s in resolution.evidence_sources):
        missing.append("news_mentions")
    return missing


def _assign_status(resolution: CompanyResolution, *, website_hint: Optional[str]) -> str:
    """
    FOUND          strong identity (high confidence, canonical anchors)
    PARTIAL        identity likely correct but profile incomplete
    NEEDS_REVIEW   credible but ambiguous (competing candidates) — human should confirm
    LOW_CONFIDENCE thin evidence; keep it visible, flag it
    NOT_FOUND      genuinely no credible evidence anywhere
    """
    has_identity_anchor = bool(
        resolution.website
        or resolution.linkedin_url
        or resolution.crunchbase_url
        or resolution.dealroom_url
        or resolution.yc_url
    )
    credible = [s for s in resolution.evidence_sources if s.match_score >= 0.5]

    if not resolution.evidence_sources and not website_hint:
        return "NOT_FOUND"
    if not has_identity_anchor and not credible:
        # Sources came back but nothing actually matches this name.
        return "NOT_FOUND" if not website_hint else "LOW_CONFIDENCE"

    # Ambiguity: a competing same-name domain with no user hint to disambiguate.
    # Fixed 2026-08-18 (fresh audit, same class as CRITICAL F1): this used to
    # require an alternative to score >= 0.8 to trigger review -- but 0.55 is
    # the bar _score_and_collect_sources uses to call a domain "official_site"
    # in the first place (line ~609 above). An alternative scoring anywhere
    # from 0.55 to 0.79 is exactly as plausible a candidate as the one that
    # got picked, yet silently lost the tie with no human ever told there was
    # one -- two same-named-but-different companies routinely land in that
    # band. Use the same 0.55 bar identity anchors are qualified against.
    strong_alternatives = [a for a in resolution.alternative_matches if a.match_score >= 0.55]
    if strong_alternatives and not website_hint:
        return "NEEDS_REVIEW"

    if resolution.confidence >= 0.7:
        return "FOUND"
    if resolution.confidence >= 0.4:
        return "PARTIAL"
    return "LOW_CONFIDENCE"


def _friendly_badge(source_type: str) -> Optional[str]:
    return {
        "official_site": "official",
        "linkedin": "linkedin",
        "crunchbase": "crunchbase",
        "dealroom": "dealroom",
        "yc": "yc",
        "news": "news",
    }.get(source_type)


def _candidate_display_name(reg: str, resolution: "CompanyResolution") -> str:
    """Human-facing name for a candidate domain.

    Prefer the resolver's canonical name when this domain is the resolved
    primary; otherwise prettify the registrable slug (acme-robotics -> Acme Robotics).
    """
    if (
        resolution.website
        and registrable_domain(_host_of(resolution.website)) == reg
        and resolution.canonical_name
        and resolution.canonical_name != "Unknown"
    ):
        return resolution.canonical_name
    return reg.split(".", 1)[0].replace("-", " ").title()


def _build_candidates(
    resolution: CompanyResolution,
    company: str,
    *,
    website_hint: Optional[str],
) -> List[CompanyCandidate]:
    """Group scored evidence into distinct company-owned domains.

    Different registrable domains (lyra.ie vs lyra.com) are different companies,
    so each becomes its own candidate with the best snippet on that domain.
    Platform (LinkedIn/Crunchbase/...) and news hosts are never candidates —
    they are evidence ABOUT a company, not the company's own site.
    """
    groups: Dict[str, Dict[str, Any]] = {}
    for s in resolution.evidence_sources:
        host = _host_of(s.url)
        reg = registrable_domain(host)
        if not reg or reg in _PLATFORM_REGISTRABLE_DOMAINS or reg in _NEWS_REGISTRABLE_DOMAINS:
            continue
        sim = _slug_similarity(company, host)
        # Candidates must be the company's OWN domain — its slug has to resemble the
        # typed name. A high match_score alone is NOT enough: it usually means the
        # name merely appears in a page's title/snippet (e.g. a Yahoo/news article
        # ABOUT the company), which is evidence, not a separate company candidate.
        if sim < 0.55:
            continue
        g = groups.setdefault(reg, {"best": s, "score": s.match_score, "badges": set()})
        if s.match_score > g["score"]:
            g["best"] = s
            g["score"] = s.match_score
        badge = _friendly_badge(s.source_type)
        if badge:
            g["badges"].add(badge)

    candidates: List[CompanyCandidate] = []
    for reg, g in groups.items():
        best: EvidenceSource = g["best"]
        candidates.append(
            CompanyCandidate(
                name=_candidate_display_name(reg, resolution),
                website=f"https://{reg}",
                description=(best.snippet or best.title or "")[:200],
                confidence=round(float(g["score"]), 3),
                source_badges=sorted(g["badges"] or {"official"}),
            )
        )

    # A user-provided website hint pins exactly one company.
    if website_hint:
        anchor = registrable_domain(hostname_from_user_hint(website_hint) or "")
        if anchor:
            pinned = [c for c in candidates if registrable_domain(_host_of(c.website)) == anchor]
            if pinned:
                return pinned[:1]
            return [
                CompanyCandidate(
                    name=_candidate_display_name(anchor, resolution),
                    website=f"https://{anchor}",
                    description=(resolution.description or "")[:200],
                    confidence=resolution.confidence,
                    source_badges=["official"],
                )
            ]

    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates[:5]


def resolve_company(
    company_name: str,
    *,
    user_id: str,
    website_hint: Optional[str] = None,
) -> CompanyResolution:
    """
    Resolve a typed company name into a real-company identity with explicit
    status, evidence, alternatives, and missing fields. Never raises on weak
    data; retrieval/transport errors degrade to LOW_CONFIDENCE/NOT_FOUND with
    an explanatory stage log instead of an exception.
    """
    uid = require_user_id(user_id, context="resolve_company")
    company = (company_name or "").strip()
    resolution = CompanyResolution(query=company, canonical_name=company or "Unknown")
    if not company:
        resolution.resolution_status = "NOT_FOUND"
        _log_stage(
            resolution,
            stage="input",
            queries=[],
            sources_found=0,
            decision="NOT_FOUND",
            reason="Empty company name.",
        )
        return resolution

    anchor_host = hostname_from_user_hint(website_hint)

    all_sources: List[EvidenceSource] = []
    for phase in (1, 2):
        queries = _build_queries(company, phase=phase, website_hint=website_hint)
        resolution.queries_used.extend(queries)
        try:
            pack = retrieve_source_pack_merged(
                queries=queries, user_id=uid, category="company"
            )
        except Exception as e:
            logger.warning("resolver retrieval failed phase=%d company=%s: %s", phase, company, e)
            _log_stage(
                resolution,
                stage=f"search_phase_{phase}",
                queries=queries,
                sources_found=0,
                decision="continue",
                reason=f"Retrieval provider error: {e}",
            )
            continue
        if not resolution.retrieval_provider:
            resolution.retrieval_provider = str(pack.get("provider") or "") or None
        scored = _score_and_collect_sources(
            company, list(pack.get("sources") or []), anchor_host=anchor_host
        )
        known = {s.url.lower().rstrip("/") for s in all_sources}
        fresh = [s for s in scored if s.url.lower().rstrip("/") not in known]
        all_sources.extend(fresh)
        _log_stage(
            resolution,
            stage=f"search_phase_{phase}",
            queries=queries,
            sources_found=len(fresh),
            decision="continue",
            reason=f"provider={pack.get('provider')} new_sources={len(fresh)}",
        )
        # Phase 2 (founders/funding/YC/product-launch queries) used to be
        # skipped whenever phase 1's official-site/LinkedIn/Crunchbase set
        # already looked strong and a regex match found a founder name --
        # exactly the case for well-known companies, whose own institutional
        # pages score high and often carry "founded by ..." boilerplate. That
        # meant the founder name came from a single self-published source,
        # never cross-checked against phase 2's broader web queries (which
        # aren't restricted to the company's own domain and are the only
        # queries that can surface independent news/press coverage). Always
        # run phase 2 now -- one extra search call, not an LLM call, so the
        # budget tradeoff this used to make no longer applies.

    all_sources.sort(key=lambda s: s.match_score, reverse=True)
    resolution.evidence_sources = all_sources[:16]

    _assign_identity_fields(
        resolution,
        company,
        resolution.evidence_sources,
        anchor_host=anchor_host,
        website_hint=website_hint,
    )
    profile_anchor = anchor_host or (_host_of(resolution.website) if resolution.website else None)
    _extract_attached_profile(
        resolution,
        resolution.evidence_sources,
        company=company,
        anchor_host=profile_anchor,
    )
    resolution.founder_names = _extract_founders(
        _founder_sources(
            resolution.evidence_sources,
            company=company,
            anchor_host=profile_anchor,
        ),
        company=company,
    )
    resolution.description = _pick_description(
        _founder_sources(
            resolution.evidence_sources,
            company=company,
            anchor_host=profile_anchor,
        )
    )
    resolution.confidence = _compute_confidence(resolution, website_hint=website_hint)
    resolution.missing_fields = _compute_missing_fields(resolution)
    resolution.resolution_status = _assign_status(resolution, website_hint=website_hint)
    resolution.candidates = _build_candidates(resolution, company, website_hint=website_hint)

    if resolution.resolution_status == "NEEDS_REVIEW":
        alts = ", ".join(a.website or a.name for a in resolution.alternative_matches[:3])
        resolution.notes.append(
            f"Multiple plausible entities match '{company}' ({alts}). "
            "Add the company website to the lookup to disambiguate."
        )
    if resolution.resolution_status in ("PARTIAL", "LOW_CONFIDENCE"):
        resolution.notes.append(
            "Evidence is incomplete — missing: " + (", ".join(resolution.missing_fields) or "none")
            + ". The company is kept and flagged instead of dropped."
        )

    _log_stage(
        resolution,
        stage="resolve",
        queries=[],
        sources_found=len(resolution.evidence_sources),
        confidence=resolution.confidence,
        decision=resolution.resolution_status,
        reason=resolution.summary_line(),
        missing=resolution.missing_fields,
    )
    return resolution


def build_fallback_scout_payload(
    resolution: CompanyResolution,
    *,
    scout_type: str,
    company_name: str,
) -> Optional[Dict[str, Any]]:
    """
    Demo-safe last resort: when the scout LLM stage fails entirely but the
    resolver DID find credible evidence, synthesize a minimal valid scout
    payload from resolver evidence so the lookup lands in the queue as
    NEEDS_REVIEW instead of vanishing. Returns None only when the resolver
    itself has no evidence to stand on.
    """
    if not resolution.has_any_evidence():
        return None
    references: List[str] = []
    if resolution.website:
        references.append(f"{resolution.canonical_name} official website - {resolution.website}")
    for src in resolution.evidence_sources:
        if len(references) >= 8:
            break
        label = src.title or src.supports or "Source"
        line = f"{label} - {src.url}"
        if all(src.url not in r for r in references):
            references.append(line)
    if not references:
        return None

    description = resolution.description or (
        f"Identity evidence located for {resolution.canonical_name}; "
        "full profile could not be generated automatically."
    )
    founders = ", ".join(resolution.founder_names) if resolution.founder_names else None
    missing = ", ".join(resolution.missing_fields) or "none"

    from scout.schema import generate_id

    return {
        "id": generate_id(),
        "scout_type": scout_type,
        "name": resolution.canonical_name or company_name,
        "one_line": description[:200],
        "sector": "Unknown",
        "problem": "[NEEDS_REVIEW] Automated profile generation failed; resolver evidence attached.",
        "solution": description[:400],
        "target_users": "Unknown target users",
        "why_now": (
            "On-demand lookup: company identity resolved from "
            f"{len(resolution.evidence_sources)} source(s); analysis stage incomplete."
        ),
        "confidence": max(0.05, min(resolution.confidence, 0.95)),
        "primary_thesis": (
            f"Analyst lookup for {resolution.canonical_name}. "
            + (f"Founders: {founders}. " if founders else "")
            + f"Evidence is partial (missing: {missing}); review before scoring."
        ),
        "key_assumptions": [
            "Resolved identity matches the company the analyst intended.",
            "Missing evidence can be filled by a follow-up enrichment pass.",
        ],
        "biggest_unknown": f"Incomplete evidence — missing: {missing}.",
        "funding_stage": None,
        "est_tam": None,
        "location": None,
        "references": references[:8],
        "source_evidence": [
            {"reference": f"{s.title or s.supports} - {s.url}", "url": s.url, "supports": s.supports}
            for s in resolution.evidence_sources[:8]
        ],
        "resolution_status": "NEEDS_REVIEW",
        "company_resolution": resolution.model_dump(mode="json"),
    }
