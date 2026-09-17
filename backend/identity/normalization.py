"""Pure normalization for domains, provider IDs, aliases, and observation IDs."""

from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urlparse

from identity.models import (
    IdentifierType,
    NormalizedIdentifier,
    SourceChannel,
    SourceObservationInput,
    VerificationStatus,
)
from research.reference_verify import hostname_from_user_hint, registrable_domain


_NON_COMPANY_DOMAINS = {
    "linkedin.com",
    "crunchbase.com",
    "dealroom.co",
    "ycombinator.com",
    "techcrunch.com",
    "reuters.com",
    "bloomberg.com",
    "github.com",
    "producthunt.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "wikipedia.org",
}

_PROVIDER_PATH_PREFIXES = {
    IdentifierType.LINKEDIN: ("company", "school"),
    IdentifierType.CRUNCHBASE: ("organization",),
    IdentifierType.DEALROOM: ("companies",),
    IdentifierType.YC: ("companies",),
}


def normalize_domain(value: Optional[str]) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    host = hostname_from_user_hint(raw)
    domain = registrable_domain(host).lower().strip(".") if host else ""
    if not domain or domain in _NON_COMPANY_DOMAINS:
        return None
    return domain


def normalize_alias(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).split())


def normalize_provider_identifier(
    identifier_type: IdentifierType, value: Optional[str]
) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    if identifier_type in (IdentifierType.EXTERNAL, IdentifierType.REGISTRY):
        return raw.lower()
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    parts = [part.strip().lower() for part in parsed.path.split("/") if part.strip()]
    prefixes = _PROVIDER_PATH_PREFIXES.get(identifier_type, ())
    for prefix in prefixes:
        if prefix in parts:
            index = parts.index(prefix)
            if index + 1 < len(parts):
                return parts[index + 1]
    return parts[-1] if parts else None


def _resolution_confidence(observation: SourceObservationInput) -> float:
    try:
        return max(
            0.0,
            min(1.0, float((observation.resolution_payload or {}).get("confidence") or 0)),
        )
    except (TypeError, ValueError):
        return 0.0


def _domain_is_verified(
    observation: SourceObservationInput, normalized_domain: str
) -> bool:
    metadata = observation.source_metadata or {}
    if bool(metadata.get("operator_confirmed_identity")):
        return True
    resolution = observation.resolution_payload or {}
    resolution_domain = normalize_domain(resolution.get("website"))
    if resolution_domain != normalized_domain:
        return False
    if observation.channel not in {
        SourceChannel.AUTONOMOUS_DISCOVERY,
        SourceChannel.BACKFILL,
    }:
        return False
    official_domains = {
        normalize_domain(item.get("url"))
        for item in resolution.get("evidence_sources", [])
        if isinstance(item, dict) and item.get("source_type") == "official_site"
    }
    return (
        resolution.get("resolution_status") == "FOUND"
        and _resolution_confidence(observation) >= 0.9
        and normalized_domain in official_domains
    )


def extract_identifier_candidates(
    observation: SourceObservationInput,
) -> List[NormalizedIdentifier]:
    identifiers: List[NormalizedIdentifier] = []
    domain = normalize_domain(
        observation.observed_domain
        or (observation.resolution_payload or {}).get("website")
    )
    confidence = _resolution_confidence(observation)
    if domain:
        verified = _domain_is_verified(observation, domain)
        identifiers.append(
            NormalizedIdentifier(
                identifier_type=IdentifierType.DOMAIN,
                normalized_value=domain,
                raw_value=str(observation.observed_domain or domain),
                verification_status=(
                    VerificationStatus.VERIFIED
                    if verified
                    else VerificationStatus.UNVERIFIED
                ),
                confidence=1.0 if verified else confidence,
                is_primary=True,
            )
        )

    verified_provider_ids = {
        str(item).strip().lower()
        for item in (observation.source_metadata or {}).get("verified_provider_ids", [])
    }
    for raw_kind, raw_value in observation.provider_identifiers.items():
        try:
            kind = IdentifierType(str(raw_kind).strip().lower())
        except ValueError:
            kind = IdentifierType.EXTERNAL
        normalized = normalize_provider_identifier(kind, raw_value)
        if not normalized:
            continue
        verification = (
            VerificationStatus.VERIFIED
            if f"{kind.value}:{normalized}" in verified_provider_ids
            else VerificationStatus.UNVERIFIED
        )
        identifiers.append(
            NormalizedIdentifier(
                identifier_type=kind,
                normalized_value=normalized,
                raw_value=str(raw_value),
                verification_status=verification,
                confidence=1.0 if verification is VerificationStatus.VERIFIED else confidence,
            )
        )
    return identifiers
