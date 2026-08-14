"""Founder Resolver: deterministic founder identification and enrichment.

Runs AFTER company resolution, seeded with the resolved company identity
(canonical name, domain, aliases, location) so founder retrieval is anchored to a
company we have already proven exists. No LLM is involved: every field is either
extracted from a retrieved source with a regex or left empty.

Contract mirrors the Company Resolver's design rules:
- Weak evidence is never a silent drop. Thin founder data becomes PARTIAL /
  LOW_CONFIDENCE with explicit `missing_fields` and a `stage_log`.
- Disagreement between sources is surfaced as an explicit `conflicts` entry
  rather than being resolved by picking a winner.
- Every field carries its own confidence in `field_confidence`, so downstream
  consumers can discount a guessed role without discarding a verified name.

Retrieval is injectable (`search=`), which keeps founder retrieval independently
routable to a dedicated people-search provider — see `search_providers`.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Callable, Dict, List, Literal, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from tenant_context import require_user_id
from utils.reference_verify import hostname_from_user_hint, registrable_domain

logger = logging.getLogger("resolver.founder")

FounderResolutionStatus = Literal["FOUND", "PARTIAL", "LOW_CONFIDENCE", "NOT_FOUND"]

FOUNDER_RESOLUTION_STATUSES: tuple[str, ...] = (
    "FOUND",
    "PARTIAL",
    "LOW_CONFIDENCE",
    "NOT_FOUND",
)

FounderSourceType = Literal[
    "official_site",
    "linkedin",
    "x",
    "github",
    "crunchbase",
    "news",
    "other",
]

# Titles that identify a founder/executive. Ordered longest-first when matched so
# "co-founder and ceo" wins over a bare "ceo".
_ROLE_CANONICAL: tuple[tuple[str, str], ...] = (
    (r"co[-\s]?founder\s*(?:&|and|/)\s*(?:ceo|chief executive(?:\s+officer)?)", "Co-founder & CEO"),
    (r"co[-\s]?founder\s*(?:&|and|/)\s*(?:cto|chief technology(?:\s+officer)?)", "Co-founder & CTO"),
    (r"co[-\s]?founder\s*(?:&|and|/)\s*(?:coo|chief operating(?:\s+officer)?)", "Co-founder & COO"),
    (r"founder\s*(?:&|and|/)\s*(?:ceo|chief executive(?:\s+officer)?)", "Founder & CEO"),
    (r"founder\s*(?:&|and|/)\s*(?:cto|chief technology(?:\s+officer)?)", "Founder & CTO"),
    (r"co[-\s]?founder", "Co-founder"),
    (r"founding\s+(?:partner|engineer)", "Founding team"),
    (r"chief\s+executive(?:\s+officer)?", "CEO"),
    (r"chief\s+technology(?:\s+officer)?", "CTO"),
    (r"chief\s+operating(?:\s+officer)?", "COO"),
    (r"chief\s+product(?:\s+officer)?", "CPO"),
    (r"chief\s+scientific(?:\s+officer)?", "CSO"),
    (r"\bceo\b", "CEO"),
    (r"\bcto\b", "CTO"),
    (r"\bcoo\b", "COO"),
    (r"\bcpo\b", "CPO"),
    (r"\bcso\b", "CSO"),
    (r"\bfounder\b", "Founder"),
)

_ROLE_ALTERNATION = (
    r"(?:co[-\s]?founders?|founders?|founding\s+(?:partner|engineer|team)|"
    r"chief\s+(?:executive|technology|operating|product|scientific)(?:\s+officer)?|"
    r"ceo|cto|coo|cpo|cso|president|chairman)"
)

# NOTE: person and organization patterns deliberately do NOT use re.IGNORECASE —
# they rely on `[A-Z]` to require capitalization. A global ignorecase flag lets
# `_PERSON` swallow lowercase connectors ("Jane Smith and" reads as a 3-word
# name), which silently loses the second founder in "founded by X and Y".
# Case-insensitivity is scoped to role/verb literals with inline `(?i:...)`.
_PERSON = r"[A-Z][\w'’.-]+(?:\s+[A-Z][\w'’.-]+){1,2}"

_ROLE_CI = f"(?i:{_ROLE_ALTERNATION})"

# "Jane Smith, co-founder and CEO" / "Jane Smith — Co-founder"
_NAME_THEN_ROLE_RE = re.compile(
    rf"({_PERSON})\s*(?:,|–|—|-|\||\()\s*(?i:the\s+|is\s+the\s+|is\s+)?"
    rf"({_ROLE_CI}(?i:[\w\s&/-]{{0,30}}))"
)
# "CEO Jane Smith" / "co-founder: Jane Smith"
_ROLE_THEN_NAME_RE = re.compile(rf"({_ROLE_CI})\s*(?:[:\-–—]|\s)\s*({_PERSON})")
# "founded by Jane Smith and John Doe"
_FOUNDED_BY_RE = re.compile(
    rf"(?i:founded|co[-\s]?founded|started|launched)\s+(?:in\s+\d{{4}}\s+)?(?i:by)\s+"
    rf"({_PERSON}(?:\s*(?i:,|and|&)\s*{_PERSON})*)"
)

_ORG = r"[A-Z][\w&.'’-]*(?:\s+(?:of|de|van|the)\s+[A-Z][\w&.'’-]*|\s+[A-Z][\w&.'’-]*){0,3}"

_PREVIOUS_EMPLOYMENT_RES = (
    re.compile(rf"(?i:previously|formerly|prior to that)\s+(?i:a\s+|an\s+|the\s+)?(?i:[\w\s]{{0,24}}?\s)?(?i:at|with|of)\s+({_ORG})"),
    re.compile(rf"\b(?i:ex)[-\s]({_ORG})"),
    re.compile(rf"(?i:spent|worked)\s+(?i:[\w\s]{{0,20}}?)(?i:at|for|with)\s+({_ORG})"),
    re.compile(rf"(?i:veteran|alum(?:nus|na|ni)?)\s+(?i:of)\s+({_ORG})"),
    re.compile(rf"(?i:before|prior to)\s+(?i:founding|starting|launching|joining)[^.,;]{{0,40}}?,?\s+(?:he|she|they|[A-Z][\w'’.-]+)\s+(?i:was|worked|led|ran|served)[^.,;]{{0,30}}?(?i:at|for|with)\s+({_ORG})"),
)

_EDUCATION_RES = (
    re.compile(rf"(?i:studied|graduated|holds?\s+(?:a|an)[\w\s]{{0,24}}?|earned[\w\s]{{0,24}}?)\s+(?i:at|from)\s+({_ORG})"),
    re.compile(rf"(?i:PhD|MBA|MSc|BSc|M\.?S\.?|B\.?S\.?|B\.?A\.?|M\.?A\.?)\s+(?i:in\s+[\w\s]{{0,30}}?\s+)?(?i:at|from)\s+({_ORG})"),
    re.compile(rf"({_ORG})\s+(?i:alum(?:nus|na|ni)|graduate)\b"),
)

_EDUCATION_MARKERS = (
    "university",
    "universit",  # universität / université / universiteit
    "college",
    "institute of technology",
    "polytechnic",
    "school of",
    "business school",
    "academy",
    "eth zurich",
    "mit",
    "epfl",
    "insead",
    "kth",
    "tu delft",
    "tu munich",
    "imperial college",
)

# Words that regularly survive the person regex but are never people.
_NAME_REJECT = frozenset(
    {
        "the company",
        "the startup",
        "the team",
        "the founders",
        "the founder",
        "series a",
        "series b",
        "series c",
        "san francisco",
        "new york",
        "los angeles",
        "united states",
        "united kingdom",
        "y combinator",
        "silicon valley",
        "north america",
        "south america",
        "press release",
        "read more",
        "learn more",
        "privacy policy",
        "terms of service",
        "all rights",
        "chief executive",
        "chief technology",
        "managing director",
        "general partner",
        "board of directors",
    }
)

# Words that never start a person's name. Retrieved snippets are attacker-
# influenced text, and a sentence like "You Are, CEO, ..." otherwise satisfies
# the capitalized-words shape and becomes a founder candidate.
_NON_NAME_LEADING_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "this",
        "that",
        "these",
        "those",
        "it",
        "he",
        "she",
        "they",
        "we",
        "you",
        "i",
        "our",
        "your",
        "their",
        "his",
        "her",
        "its",
        "and",
        "or",
        "but",
        "if",
        "when",
        "while",
        "ignore",
        "system",
        "assistant",
        "user",
        "note",
        "click",
        "read",
        "learn",
        "view",
        "see",
        "follow",
        "subscribe",
        "download",
        "contact",
        "about",
        "home",
        "search",
        "share",
        "copyright",
        "all",
        "privacy",
        "terms",
        "cookie",
        "cookies",
    }
)

# Tokens that mark a "name" as an organization rather than a person.
_ORG_NAME_MARKERS = (
    "inc",
    "llc",
    "ltd",
    "gmbh",
    "corp",
    "labs",
    "capital",
    "ventures",
    "partners",
    "holdings",
    "university",
    "institute",
    "college",
    "foundation",
    "group",
    # Business descriptors. A LinkedIn profile lists every role a person has
    # held, so a company name from an *unrelated* role reads as a capitalised
    # multi-word phrase and passed the person-name shape test: "Blueprint Sales
    # Solutions" was resolved as a founder named "Blueprint Sales Solutions"
    # with role CEO, and became the "founders' industry pedigree" in an IC pack.
    #
    # Only words that are essentially never personal surnames are listed.
    # "Sales", "Global", "Digital" and "Security" are deliberately excluded —
    # Sales is a real Portuguese surname, and the rest read as adjectives.
    "solutions",
    "systems",
    "technologies",
    "technology",
    "consulting",
    "services",
    "software",
    "analytics",
    "logistics",
    "telematics",
    "enterprises",
    "industries",
    "networks",
    "robotics",
    "dynamics",
    "sciences",
    "media",
    "agency",
    "studio",
    "studios",
    "associates",
    "advisors",
    "advisory",
)

_NEWS_HOSTS = frozenset(
    {
        "techcrunch.com",
        "businesswire.com",
        "prnewswire.com",
        "globenewswire.com",
        "reuters.com",
        "bloomberg.com",
        "forbes.com",
        "sifted.eu",
        "tech.eu",
        "eu-startups.com",
        "venturebeat.com",
        "theinformation.com",
        "axios.com",
        "finsmes.com",
        "businessinsider.com",
        "fortune.com",
        "wired.com",
    }
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+|\n+")


class FounderEvidence(BaseModel):
    """One retrieved source that supports a founder field."""

    url: str
    title: str = ""
    snippet: str = ""
    source_type: FounderSourceType = "other"
    supports: str = ""
    access_class: Literal["public", "tenant_confidential", "restricted"] = "public"


class FounderFieldConflict(BaseModel):
    """Two or more sources disagree about the same founder field."""

    field: str
    values: List[str] = Field(default_factory=list)
    source_urls: List[str] = Field(default_factory=list)


class FounderCandidate(BaseModel):
    """A structured founder profile assembled from retrieved evidence."""

    name: str
    role: Optional[str] = None
    linkedin_url: Optional[str] = None
    x_url: Optional[str] = None
    github_url: Optional[str] = None
    previous_employment: List[str] = Field(default_factory=list)
    education: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    evidence: List[FounderEvidence] = Field(default_factory=list)
    conflicts: List[FounderFieldConflict] = Field(default_factory=list)
    # Per-field confidence in [0, 1]; a field absent from the map was not extracted.
    field_confidence: Dict[str, float] = Field(default_factory=dict)
    confidence: float = 0.0


class FounderStageLog(BaseModel):
    """Per-stage debug record: what we asked, what we got, what we decided."""

    stage: str
    queries: List[str] = Field(default_factory=list)
    sources_found: int = 0
    candidates: int = 0
    decision: str = ""
    reason: str = ""


class FounderResolution(BaseModel):
    """Founder Resolver output contract (persisted alongside the company resolution)."""

    company: str
    website: Optional[str] = None
    founders: List[FounderCandidate] = Field(default_factory=list)
    resolution_status: str = "NOT_FOUND"
    confidence: float = 0.0
    missing_fields: List[str] = Field(default_factory=list)
    queries_used: List[str] = Field(default_factory=list)
    stage_log: List[FounderStageLog] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    retrieval_provider: Optional[str] = None

    def founder_names(self) -> List[str]:
        return [f.name for f in self.founders]

    def summary_line(self) -> str:
        return (
            f"status={self.resolution_status} confidence={self.confidence:.2f} "
            f"founders={len(self.founders)} missing={','.join(self.missing_fields) or 'none'}"
        )


# --------------------------------------------------------------------------- #
# Retrieval seam
# --------------------------------------------------------------------------- #

# A search callable takes (queries, user_id) and returns a retrieval source pack
# dict: {"provider": str, "sources": [{title,url,snippet}], "url_allowlist": set}.
SearchFn = Callable[..., Dict[str, Any]]


def _default_search(*, queries: List[str], user_id: str, **kwargs: Any) -> Dict[str, Any]:
    """Route founder retrieval through the people-search category.

    Kept as a thin indirection so a dedicated people-search provider can be
    registered without touching any extraction logic.
    """
    from utils.search_providers import search_source_pack

    return search_source_pack(
        queries=queries,
        user_id=user_id,
        category="people",
        **kwargs,
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower().strip(".")
    except Exception:
        return ""


def _clean_person_name(raw: str) -> str:
    name = re.sub(r"^(?:and|&|,|;|:)\s+", "", (raw or "").strip(), flags=re.IGNORECASE)
    name = name.strip(" .,'’\"-–—|")
    name = re.sub(r"\s+", " ", name)
    return name


def _is_person_name(name: str) -> bool:
    n = _clean_person_name(name)
    if not n or len(n) > 40:
        return False
    lowered = n.lower()
    if lowered in _NAME_REJECT:
        return False
    words = n.split()
    if not (2 <= len(words) <= 3):
        return False
    if words[0].lower().strip(".") in _NON_NAME_LEADING_WORDS:
        return False
    if any(w.lower().strip(".") in _ORG_NAME_MARKERS for w in words):
        return False
    for w in words:
        if not re.fullmatch(r"[A-Z][\w'’.-]*", w):
            return False
        # A word ending in "." is a sentence end that the person pattern ran past
        # ("Jane Smith - LinkedIn. Jane Smith"), unless it is a single initial.
        if w.endswith(".") and len(w) > 2:
            return False
    return True


def _name_tokens(name: str) -> List[str]:
    return [t for t in re.split(r"[^a-z0-9]+", (name or "").lower()) if t]


def _classify_source(url: str, *, anchor_host: Optional[str]) -> FounderSourceType:
    host = _host_of(url)
    reg = registrable_domain(host)
    lowered = url.lower()
    if anchor_host and (host == anchor_host or host.endswith("." + anchor_host)):
        return "official_site"
    if reg == "linkedin.com":
        return "linkedin"
    if reg in ("x.com", "twitter.com"):
        return "x"
    if reg == "github.com":
        return "github"
    if reg == "crunchbase.com":
        return "crunchbase"
    if reg in _NEWS_HOSTS:
        return "news"
    if "/team" in lowered or "/about" in lowered or "/leadership" in lowered:
        return "official_site" if not reg.endswith((".com", ".io")) or anchor_host is None else "other"
    return "other"


def _canonical_role(text: str) -> Optional[str]:
    lowered = (text or "").lower()
    for pattern, canonical in _ROLE_CANONICAL:
        if re.search(pattern, lowered):
            return canonical
    return None


def _split_sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text or "") if s.strip()]


def _mentions_person(sentence: str, name: str) -> bool:
    words = name.split()
    last = words[-1] if words else name
    lowered = sentence.lower()
    return name.lower() in lowered or (len(last) >= 4 and last.lower() in lowered)


def _sentences_mentioning(text: str, name: str) -> List[str]:
    """Sentences from `text` that mention the person by full or last name."""
    return [s for s in _split_sentences(text) if _mentions_person(s, name)]


def attribute_sentences(text: str, known_names: Optional[List[str]] = None) -> Dict[str, List[str]]:
    """Map each person mentioned in `text` to the sentences describing them.

    Walks sentences in order and tracks the current subject, so a follow-on
    sentence with a pronoun ("She graduated from ETH Zurich.") is attributed to
    the person named in the preceding sentence. When a sentence names two people
    the subject is cleared: attributing a shared "They previously worked at ..."
    to both would invent facts, and a missing field is always safer than a wrong one.
    """
    attributed: Dict[str, List[str]] = {}
    subject: Optional[str] = None
    known = [n for n in (known_names or []) if _is_person_name(n)]

    for sentence in _split_sentences(text):
        named: List[str] = []
        for name, _role in _collect_name_role_pairs(sentence):
            if name not in named:
                named.append(name)
        # A bare mention of an already-known founder also moves the subject.
        for name in known:
            if name not in named and _mentions_person(sentence, name):
                named.append(name)

        if named:
            for name in named:
                attributed.setdefault(name, []).append(sentence)
            subject = named[0] if len(named) == 1 else None
        elif subject:
            attributed.setdefault(subject, []).append(sentence)
    return attributed


def _dedupe_preserving(values: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for v in values:
        key = re.sub(r"\s+", " ", v.strip().lower())
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(v.strip())
    return out


def _looks_like_school(org: str) -> bool:
    lowered = org.lower()
    return any(marker in lowered for marker in _EDUCATION_MARKERS)


def _extract_orgs(sentences: List[str], patterns, *, want_school: bool) -> List[str]:
    found: List[str] = []
    for sentence in sentences:
        for pattern in patterns:
            for match in pattern.finditer(sentence):
                org = _clean_person_name(match.group(1))
                if not org or len(org) > 60:
                    continue
                if org.lower() in _NAME_REJECT:
                    continue
                if _looks_like_school(org) != want_school:
                    continue
                found.append(org)
    return _dedupe_preserving(found)[:6]


def _profile_url_for(name: str, url: str, kind: str) -> bool:
    """True when a platform profile URL's slug plausibly belongs to this person."""
    path = urlparse(url).path.strip("/")
    if kind == "linkedin":
        if not re.match(r"(?i)^in/", path):
            return False
        slug = path.split("/", 1)[1] if "/" in path else ""
    elif kind in ("x", "github"):
        parts = [p for p in path.split("/") if p]
        if len(parts) != 1:
            return False
        slug = parts[0]
        if slug.lower() in ("home", "about", "search", "explore", "login", "orgs", "topics"):
            return False
    else:
        return False
    slug_tokens = set(re.split(r"[^a-z0-9]+", slug.lower()))
    slug_compact = re.sub(r"[^a-z0-9]", "", slug.lower())
    tokens = _name_tokens(name)
    if not tokens or not slug_compact:
        return False
    compact_name = "".join(tokens)
    if compact_name and compact_name in slug_compact:
        return True
    # Require the surname plus at least the first initial for a shortened handle.
    surname = tokens[-1]
    if surname and surname in slug_tokens:
        return True
    if surname and surname in slug_compact and tokens[0][:1] in slug_compact:
        return True
    return False


# --------------------------------------------------------------------------- #
# Query construction
# --------------------------------------------------------------------------- #


_TEAM_PATH_RE = re.compile(
    r"/(team|teams|about|about-us|aboutus|people|leadership|founders|management|"
    r"who-we-are|our-team|our-story|company)(/|$)",
    re.IGNORECASE,
)

# Paths worth trying when retrieval never surfaced a team page for the domain.
_TEAM_PATH_GUESSES = ("/team", "/about", "/about-us")


def _team_page_extraction_enabled() -> bool:
    return os.getenv("FOUNDER_TEAM_PAGE_EXTRACTION", "true").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _max_team_pages() -> int:
    try:
        value = int(os.getenv("FOUNDER_TEAM_PAGE_MAX", "2"))
    except ValueError:
        value = 2
    # The extraction layer accepts at most 3 URLs per call.
    return max(0, min(value, 3))


def _looks_like_team_page(url: str) -> bool:
    try:
        return bool(_TEAM_PATH_RE.search(urlparse(url).path or ""))
    except Exception:
        return False


def _augment_with_team_pages(
    evidence: List[FounderEvidence],
    *,
    anchor_host: Optional[str],
    company: str,
) -> int:
    """Replace team/about snippets with full page text. Returns pages fetched.

    Best-effort: an unreachable page simply leaves the original snippet in place.
    """
    if not anchor_host or not _team_page_extraction_enabled():
        return 0
    limit = _max_team_pages()
    if limit <= 0:
        return 0

    from utils.search_providers import extract_pages

    by_url = {e.url.lower().rstrip("/"): e for e in evidence}
    targets = [
        e.url
        for e in evidence
        if _host_of(e.url)
        and (
            _host_of(e.url) == anchor_host or _host_of(e.url).endswith("." + anchor_host)
        )
        and _looks_like_team_page(e.url)
    ][:limit]

    # Retrieval never surfaced a team page — try the conventional paths.
    guessed: List[str] = []
    if not targets:
        guessed = [f"https://{anchor_host}{path}" for path in _TEAM_PATH_GUESSES][:limit]
        targets = guessed

    if not targets:
        return 0
    try:
        pages = extract_pages(targets)
    except Exception as exc:
        logger.warning("founder team-page extraction failed company=%s: %s", company, exc)
        return 0

    fetched = 0
    for page in pages:
        url = str(page.get("url") or "").strip()
        content = str(page.get("content") or "").strip()
        if not url or not content:
            continue
        existing = by_url.get(url.lower().rstrip("/"))
        if existing is not None:
            existing.snippet = content[:12000]
        else:
            evidence.append(
                FounderEvidence(
                    url=url,
                    title=f"{company} team page",
                    snippet=content[:12000],
                    source_type="official_site",
                    supports="Founder or team evidence",
                )
            )
        fetched += 1
    return fetched


def build_founder_queries(
    company: str,
    *,
    website: Optional[str] = None,
    aliases: Optional[List[str]] = None,
    location: Optional[str] = None,
    known_founder_names: Optional[List[str]] = None,
    max_queries: int = 5,
) -> List[str]:
    """Founder-specific queries anchored on the already-resolved company identity."""
    name = (company or "").strip()
    if not name:
        return []
    host = hostname_from_user_hint(website)
    queries: List[str] = []
    if host:
        queries.append(f"site:{host} founders team about leadership")
    queries.append(f'"{name}" founder co-founder CEO CTO')
    queries.append(f'site:linkedin.com/in "{name}" founder')
    known = [n.strip() for n in (known_founder_names or []) if str(n).strip()][:2]
    for person in known:
        queries.append(f'"{person}" "{name}" founder previously worked education')
    if not known:
        loc = (location or "").strip()
        if loc:
            queries.append(f'"{name}" founders {loc} team background')
        else:
            queries.append(f'"{name}" founding team background previously')
    for alias in [a.strip() for a in (aliases or []) if str(a).strip()][:1]:
        if alias.lower() != name.lower():
            queries.append(f'"{alias}" founder co-founder')

    seen: set[str] = set()
    out: List[str] = []
    for q in queries:
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
    return out[: max(1, max_queries)]


# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #


def _collect_name_role_pairs(text: str) -> List[tuple[str, Optional[str]]]:
    """Deterministically pull (person, role) pairs out of one source's text."""
    pairs: List[tuple[str, Optional[str]]] = []

    for match in _NAME_THEN_ROLE_RE.finditer(text):
        name = _clean_person_name(match.group(1))
        if _is_person_name(name):
            pairs.append((name, _canonical_role(match.group(2))))

    for match in _ROLE_THEN_NAME_RE.finditer(text):
        name = _clean_person_name(match.group(2))
        if _is_person_name(name):
            pairs.append((name, _canonical_role(match.group(1))))

    for match in _FOUNDED_BY_RE.finditer(text):
        blob = match.group(1)
        for raw in re.split(r"\s*(?:,|and|&)\s*", blob):
            name = _clean_person_name(raw)
            if _is_person_name(name):
                pairs.append((name, "Co-founder" if "," in blob or " and " in blob.lower() else "Founder"))

    return pairs


def _accumulate(
    candidates: Dict[str, Dict[str, Any]],
    *,
    name: str,
    role: Optional[str],
    source: FounderEvidence,
    sentences: Optional[List[str]] = None,
) -> None:
    key = " ".join(_name_tokens(name))
    entry = candidates.setdefault(
        key,
        {
            "name": name,
            "roles": [],  # (role, url)
            "evidence": [],
            "urls": set(),
            "sentences": [],
        },
    )
    # Prefer the longest observed spelling ("Jane A. Smith" over "Jane Smith").
    if len(name) > len(entry["name"]):
        entry["name"] = name
    if role:
        entry["roles"].append((role, source.url))
    if source.url not in entry["urls"]:
        entry["urls"].add(source.url)
        entry["evidence"].append(source)
    entry["sentences"].extend(sentences or [])


_EXEC_TITLES = ("CEO", "CTO", "COO", "CPO", "CSO")

# Founder standing, most specific first.
_FOUNDER_FACETS = ("Co-founder", "Founder", "Founding team")


def _role_facets(role: str) -> tuple[Optional[str], Optional[str]]:
    """Split a canonical role into (founder standing, executive title).

    Founder standing and executive title are orthogonal — "Co-founder" from one
    source and "CTO" from another describe the same person, so they are merged
    rather than reported as a conflict. Only two different executive titles
    (CEO vs COO) are genuinely contradictory.
    """
    lowered = (role or "").lower()
    founder: Optional[str] = None
    if "co-founder" in lowered:
        founder = "Co-founder"
    elif "founding team" in lowered:
        founder = "Founding team"
    elif "founder" in lowered:
        founder = "Founder"
    title: Optional[str] = None
    for candidate in _EXEC_TITLES:
        if re.search(rf"\b{candidate.lower()}\b", lowered):
            title = candidate
            break
    return founder, title


def _resolve_role(
    roles: List[tuple[str, str]],
) -> tuple[Optional[str], Optional[FounderFieldConflict], float]:
    """Merge observed roles, or surface a conflict when executive titles disagree."""
    if not roles:
        return None, None, 0.0

    founders: Dict[str, List[str]] = {}
    titles: Dict[str, List[str]] = {}
    for role, url in roles:
        founder, title = _role_facets(role)
        if founder:
            founders.setdefault(founder, []).append(url)
        if title:
            titles.setdefault(title, []).append(url)

    founder_facet = next((f for f in _FOUNDER_FACETS if f in founders), None)

    conflict: Optional[FounderFieldConflict] = None
    title_facet: Optional[str] = None
    if titles:
        # Most-corroborated title wins the display slot; disagreement is recorded.
        title_facet = sorted(titles, key=lambda t: (-len(set(titles[t])), t))[0]
        if len(titles) > 1:
            conflict = FounderFieldConflict(
                field="role",
                values=sorted(titles),
                source_urls=sorted({u for urls in titles.values() for u in urls}),
            )

    parts = [p for p in (founder_facet, title_facet) if p]
    if not parts:
        return None, None, 0.0
    resolved = " & ".join(parts)

    corroboration = len({url for _role, url in roles})
    confidence = 0.35 if conflict else min(1.0, 0.55 + 0.2 * corroboration)
    return resolved, conflict, confidence


def _resolve_profile_link(
    name: str,
    kind: str,
    sources: List[FounderEvidence],
) -> tuple[Optional[str], Optional[FounderFieldConflict], float]:
    """Find a platform profile URL belonging to this person."""
    matches: List[str] = []
    for source in sources:
        for url in {source.url, *re.findall(r"https?://[^\s\"'<>\)\]]+", source.snippet or "")}:
            host = registrable_domain(_host_of(url))
            if kind == "linkedin" and host != "linkedin.com":
                continue
            if kind == "x" and host not in ("x.com", "twitter.com"):
                continue
            if kind == "github" and host != "github.com":
                continue
            if _profile_url_for(name, url, kind):
                matches.append(url.rstrip("/"))
    unique = _dedupe_preserving(matches)
    if not unique:
        return None, None, 0.0
    if len(unique) == 1:
        return unique[0], None, 0.8
    conflict = FounderFieldConflict(field=f"{kind}_url", values=unique[:4], source_urls=unique[:4])
    return unique[0], conflict, 0.4


def _candidate_confidence(candidate: FounderCandidate, source_types: List[str]) -> float:
    """Blend name corroboration, source quality, and field coverage into 0..1."""
    distinct_sources = len({e.url for e in candidate.evidence})
    score = min(0.5, 0.2 + 0.15 * distinct_sources)
    if "official_site" in source_types:
        score += 0.2
    if "linkedin" in source_types or candidate.linkedin_url:
        score += 0.15
    if "crunchbase" in source_types or "news" in source_types:
        score += 0.05
    if candidate.role:
        score += 0.1
    if candidate.previous_employment or candidate.education:
        score += 0.05
    if candidate.conflicts:
        score -= 0.1 * len(candidate.conflicts)
    return round(max(0.0, min(1.0, score)), 3)


def _missing_fields(founders: List[FounderCandidate]) -> List[str]:
    if not founders:
        return ["founder_names", "role", "linkedin_url", "previous_employment", "education"]
    missing: List[str] = []
    if not any(f.role for f in founders):
        missing.append("role")
    if not any(f.linkedin_url for f in founders):
        missing.append("linkedin_url")
    if not any(f.x_url for f in founders):
        missing.append("x_url")
    if not any(f.github_url for f in founders):
        missing.append("github_url")
    if not any(f.previous_employment for f in founders):
        missing.append("previous_employment")
    if not any(f.education for f in founders):
        missing.append("education")
    return missing


def _assign_status(founders: List[FounderCandidate]) -> str:
    if not founders:
        return "NOT_FOUND"
    best = max(f.confidence for f in founders)
    enriched = any(
        f.linkedin_url or f.role or f.previous_employment or f.education for f in founders
    )
    if best >= 0.65 and enriched:
        return "FOUND"
    if best >= 0.4:
        return "PARTIAL"
    return "LOW_CONFIDENCE"


def _log_stage(
    resolution: FounderResolution,
    *,
    stage: str,
    queries: List[str],
    sources_found: int,
    candidates: int,
    decision: str,
    reason: str,
) -> None:
    resolution.stage_log.append(
        FounderStageLog(
            stage=stage,
            queries=queries,
            sources_found=sources_found,
            candidates=candidates,
            decision=decision,
            reason=reason,
        )
    )
    logger.info(
        "founder_resolver stage=%s company=%s queries=%d sources=%d candidates=%d decision=%s reason=%s",
        stage,
        resolution.company[:60],
        len(queries),
        sources_found,
        candidates,
        decision,
        reason[:160],
    )


def build_resolution_from_evidence(
    company: str,
    candidates: List[FounderCandidate],
    *,
    website: Optional[str] = None,
    retrieval_provider: Optional[str] = None,
    stage: str = "evidence",
    reason: str = "",
    sources_found: int = 0,
) -> FounderResolution:
    """Wrap already-extracted candidates in a scored FounderResolution.

    Lets callers that already hold evidence (e.g. the reviewer gap-retrieval
    pack) produce the same contract as `resolve_founders` without re-running
    retrieval, and without reaching into this module's internals.
    """
    resolution = FounderResolution(
        company=company,
        website=website,
        founders=list(candidates),
        retrieval_provider=retrieval_provider,
    )
    resolution.confidence = round(max((c.confidence for c in candidates), default=0.0), 3)
    resolution.missing_fields = _missing_fields(candidates)
    resolution.resolution_status = _assign_status(candidates)
    resolution.stage_log.append(
        FounderStageLog(
            stage=stage,
            sources_found=sources_found,
            candidates=len(candidates),
            decision=resolution.resolution_status,
            reason=reason,
        )
    )
    return resolution


def extract_founder_candidates(
    sources: List[FounderEvidence],
    *,
    seed_names: Optional[List[str]] = None,
) -> List[FounderCandidate]:
    """Build structured founder candidates from evidence. Pure and deterministic."""
    accumulator: Dict[str, Dict[str, Any]] = {}
    seeds = [
        _clean_person_name(str(s)) for s in (seed_names or []) if _is_person_name(str(s))
    ]

    for source in sources:
        text = f"{source.title}. {source.snippet}"
        # Role pairs give the authoritative (person, role) signal; sentence
        # attribution gives each person their descriptive sentences.
        pairs = _collect_name_role_pairs(text)
        roles_by_name: Dict[str, Optional[str]] = {}
        for name, role in pairs:
            if role and not roles_by_name.get(name):
                roles_by_name[name] = role
            roles_by_name.setdefault(name, None)

        attributed = attribute_sentences(text, known_names=seeds)
        for name in {*roles_by_name, *attributed}:
            _accumulate(
                accumulator,
                name=name,
                role=roles_by_name.get(name) or _canonical_role(
                    " ".join(attributed.get(name, []))
                ),
                source=source,
                sentences=attributed.get(name, []),
            )

    candidates: List[FounderCandidate] = []
    for entry in accumulator.values():
        name = entry["name"]
        evidence: List[FounderEvidence] = entry["evidence"]
        conflicts: List[FounderFieldConflict] = []
        field_confidence: Dict[str, float] = {}

        role, role_conflict, role_conf = _resolve_role(entry["roles"])
        if role_conflict:
            conflicts.append(role_conflict)
        if role:
            field_confidence["role"] = round(role_conf, 3)

        links: Dict[str, Optional[str]] = {}
        for kind in ("linkedin", "x", "github"):
            url, conflict, conf = _resolve_profile_link(name, kind, evidence)
            links[kind] = url
            if conflict:
                conflicts.append(conflict)
            if url:
                field_confidence[f"{kind}_url"] = round(conf, 3)

        sentences: List[str] = _dedupe_preserving(entry["sentences"])
        previous_employment = _extract_orgs(sentences, _PREVIOUS_EMPLOYMENT_RES, want_school=False)
        education = _extract_orgs(sentences, _EDUCATION_RES, want_school=True)
        if previous_employment:
            field_confidence["previous_employment"] = 0.75 if len(evidence) > 1 else 0.5
        if education:
            field_confidence["education"] = 0.75 if len(evidence) > 1 else 0.5

        source_types = [e.source_type for e in evidence]
        field_confidence["name"] = round(
            min(1.0, 0.4 + 0.2 * len({e.url for e in evidence})), 3
        )

        candidate = FounderCandidate(
            name=name,
            role=role,
            linkedin_url=links.get("linkedin"),
            x_url=links.get("x"),
            github_url=links.get("github"),
            previous_employment=previous_employment,
            education=education,
            evidence=evidence[:8],
            conflicts=conflicts,
            field_confidence=field_confidence,
        )
        candidate.confidence = _candidate_confidence(candidate, source_types)
        candidates.append(candidate)

    candidates.sort(key=lambda c: (-c.confidence, c.name))
    return candidates[:8]


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def resolve_founders(
    company_name: str,
    *,
    user_id: str,
    website: Optional[str] = None,
    aliases: Optional[List[str]] = None,
    location: Optional[str] = None,
    known_founder_names: Optional[List[str]] = None,
    search: Optional[SearchFn] = None,
    max_queries: int = 5,
) -> FounderResolution:
    """Resolve founders for an already-identified company.

    Never raises on weak data: retrieval or transport errors degrade to a
    LOW_CONFIDENCE / NOT_FOUND resolution with an explanatory stage log.
    """
    uid = require_user_id(user_id, context="resolve_founders")
    company = (company_name or "").strip()
    resolution = FounderResolution(company=company or "Unknown", website=website or None)
    if not company:
        resolution.resolution_status = "NOT_FOUND"
        _log_stage(
            resolution,
            stage="input",
            queries=[],
            sources_found=0,
            candidates=0,
            decision="NOT_FOUND",
            reason="Empty company name.",
        )
        return resolution

    queries = build_founder_queries(
        company,
        website=website,
        aliases=aliases,
        location=location,
        known_founder_names=known_founder_names,
        max_queries=max_queries,
    )
    resolution.queries_used = list(queries)

    search_fn = search or _default_search
    try:
        pack = search_fn(queries=queries, user_id=uid)
    except Exception as exc:
        logger.warning("founder retrieval failed company=%s: %s", company, exc)
        _log_stage(
            resolution,
            stage="search",
            queries=queries,
            sources_found=0,
            candidates=0,
            decision="NOT_FOUND",
            reason=f"Retrieval provider error: {exc}",
        )
        resolution.resolution_status = "NOT_FOUND"
        resolution.missing_fields = _missing_fields([])
        resolution.notes.append("Founder retrieval was unavailable; no founder evidence collected.")
        return resolution

    resolution.retrieval_provider = str((pack or {}).get("provider") or "") or None
    anchor_host = hostname_from_user_hint(website)
    raw_sources = [s for s in list((pack or {}).get("sources") or []) if isinstance(s, dict)]

    evidence: List[FounderEvidence] = []
    seen_urls: set[str] = set()
    for row in raw_sources:
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        key = url.lower().rstrip("/")
        if key in seen_urls:
            continue
        seen_urls.add(key)
        source_type = _classify_source(url, anchor_host=anchor_host)
        evidence.append(
            FounderEvidence(
                url=url,
                title=str(row.get("title") or "").strip(),
                snippet=str(row.get("snippet") or "").strip()[:12000],
                source_type=source_type,
                supports="Founder or team evidence",
            )
        )

    _log_stage(
        resolution,
        stage="search",
        queries=queries,
        sources_found=len(evidence),
        candidates=0,
        decision="continue",
        reason=f"provider={resolution.retrieval_provider or 'none'}",
    )

    # A company's own /team or /about page usually lists the founders outright,
    # but a search snippet truncates it to a sentence or two — which is why
    # "readily available" team details were being missed. Read those pages in
    # full before extracting.
    extracted_pages = _augment_with_team_pages(
        evidence, anchor_host=anchor_host, company=company
    )
    if extracted_pages:
        _log_stage(
            resolution,
            stage="team_pages",
            queries=[],
            sources_found=extracted_pages,
            candidates=0,
            decision="continue",
            reason=f"Read {extracted_pages} company team/about page(s) in full.",
        )

    founders = extract_founder_candidates(evidence, seed_names=known_founder_names)
    resolution.founders = founders
    resolution.confidence = round(max((f.confidence for f in founders), default=0.0), 3)
    resolution.missing_fields = _missing_fields(founders)
    resolution.resolution_status = _assign_status(founders)

    if resolution.resolution_status == "NOT_FOUND":
        resolution.notes.append(
            f"No founder could be attributed to {company} from "
            f"{len(evidence)} retrieved source(s)."
        )
    elif resolution.resolution_status in ("PARTIAL", "LOW_CONFIDENCE"):
        resolution.notes.append(
            "Founder evidence is incomplete — missing: "
            + (", ".join(resolution.missing_fields) or "none")
            + ". Founders are kept and flagged instead of dropped."
        )
    for founder in founders:
        for conflict in founder.conflicts:
            resolution.notes.append(
                f"Conflicting {conflict.field} for {founder.name}: "
                + " | ".join(conflict.values[:3])
            )

    _log_stage(
        resolution,
        stage="resolve",
        queries=[],
        sources_found=len(evidence),
        candidates=len(founders),
        decision=resolution.resolution_status,
        reason=resolution.summary_line(),
    )
    return resolution
