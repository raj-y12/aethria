"""Pure founder-to-person projection rules.

This module deliberately does not decide founder quality. It only creates a
bounded identity/relationship draft from evidence already extracted by Scout.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from people.models import PersonDraft, PersonHistoryDraft, PersonIdentifierDraft
from resolver.founder_resolver import FounderCandidate, FounderResolution


def normalize_person_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^\w\s'-]", " ", text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def _normalize_url(raw: str) -> str:
    parsed = urlparse(str(raw or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    query = urlencode(sorted((key, value) for key, value in parse_qsl(parsed.query) if not key.lower().startswith("utm_")))
    path = parsed.path.rstrip("/") or "/"
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return urlunparse(("https", host, path, "", query, ""))


def _identifier(raw: str, kind: str) -> PersonIdentifierDraft | None:
    normalized = _normalize_url(raw)
    if not normalized:
        return None
    host = urlparse(normalized).hostname or ""
    hosts = {
        "linkedin": ("linkedin.com", "www.linkedin.com"),
        "github": ("github.com", "www.github.com"),
        "x": ("x.com", "www.x.com", "twitter.com", "www.twitter.com"),
    }
    if kind in hosts and not any(host == item or host.endswith("." + item) for item in hosts[kind]):
        return None
    return PersonIdentifierDraft(kind, normalized, raw)


def _identity_key(candidate: FounderCandidate, company_id: str, normalized_name: str, identifiers: list[PersonIdentifierDraft]) -> str:
    strong = next((item for item in identifiers if item.identifier_type in {"linkedin", "github", "x"}), None)
    if strong:
        return f"external:{strong.identifier_type}:{strong.normalized_value}"
    return f"company-name:{company_id}:{normalized_name}"


def canonicalize_founder_resolution(resolution: FounderResolution, *, company_id: str) -> list[PersonDraft]:
    drafts: list[PersonDraft] = []
    for candidate in resolution.founders:
        name = " ".join(str(candidate.name or "").split())
        normalized = normalize_person_name(name)
        evidence_urls = tuple(sorted({item.url for item in candidate.evidence if str(item.url or "").strip()}))
        identifiers = [item for item in (
            _identifier(candidate.linkedin_url, "linkedin"),
            _identifier(candidate.github_url, "github"),
            _identifier(candidate.x_url, "x"),
        ) if item is not None]
        if candidate.location:
            # Location is retained only as evidence in the legacy resolution; it is
            # intentionally not promoted into the canonical person model.
            pass
        histories = [
            *[PersonHistoryDraft("worked_at_company", value) for value in candidate.previous_employment if str(value).strip()],
            *[PersonHistoryDraft("education", value) for value in candidate.education if str(value).strip()],
        ]
        conflicts = tuple(sorted({str(item.field) for item in candidate.conflicts if str(item.field).strip()}))
        persistable = bool(name and normalized and (evidence_urls or identifiers))
        confidence = float(candidate.confidence or 0.0)
        if persistable and confidence <= 0:
            confidence = 0.5
        drafts.append(PersonDraft(
            canonical_name=name,
            normalized_name=normalized,
            company_id=company_id,
            identity_key=_identity_key(candidate, company_id, normalized, identifiers),
            identity_confidence=min(1.0, max(0.0, confidence)),
            relationship_type="cofounder" if str(candidate.role or "").lower().startswith("co-") else "founder",
            role=candidate.role,
            identifiers=tuple(identifiers),
            history=tuple(histories),
            conflict_fields=conflicts,
            evidence_urls=evidence_urls,
            persistable=persistable,
            unresolved_reason=None if persistable else "insufficient_grounding",
        ))
    return drafts
