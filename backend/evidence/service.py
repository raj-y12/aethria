"""Deterministic evidence standards and trust classification."""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

from evidence.models import ArtifactType, AssertionClass, ClaimInput, TrustClass
from identity.normalization import normalize_domain


class EvidenceStandardError(ValueError):
    pass


_INJECTION_PATTERNS = (
    re.compile(r"\bignore (?:all |any )?(?:previous|prior|system) instructions?\b", re.I),
    re.compile(r"\breveal (?:the )?(?:system prompt|hidden instructions?)\b", re.I),
    re.compile(r"\byou are now\b", re.I),
    re.compile(r"\bdeveloper message\b", re.I),
    re.compile(r"\bdo not follow\b.{0,40}\binstructions?\b", re.I),
)

_PERSONALITY_LABELS = {
    "magnetic",
    "charismatic",
    "obsessive",
    "visionary",
    "exceptional founder",
    "founder-market-fit personality",
    "unstoppable",
    "force of nature",
}

_INDEPENDENT_DOMAINS = {
    "reuters.com",
    "bloomberg.com",
    "ft.com",
    "wsj.com",
    "techcrunch.com",
    "sifted.eu",
}


def detect_prompt_injection(text: str) -> bool:
    bounded = str(text or "")[:20000]
    return any(pattern.search(bounded) for pattern in _INJECTION_PATTERNS)


def classify_trust(
    source_uri: Optional[str],
    artifact_type: ArtifactType,
    *,
    canonical_domain: Optional[str] = None,
    operator_attributed: bool = False,
) -> TrustClass:
    if operator_attributed or artifact_type in {
        ArtifactType.INTERVIEW_NOTE,
        ArtifactType.OPERATOR_CONTEXT,
    }:
        return TrustClass.OPERATOR
    if artifact_type in {ArtifactType.PITCH_DECK, ArtifactType.EMAIL}:
        return TrustClass.FOUNDER
    if artifact_type is ArtifactType.REGISTRY:
        return TrustClass.REGULATORY
    host_domain = normalize_domain(source_uri)
    if host_domain and canonical_domain and host_domain == normalize_domain(canonical_domain):
        return TrustClass.OFFICIAL
    host = str(urlparse(str(source_uri or "")).hostname or "").lower().removeprefix("www.")
    if any(host == domain or host.endswith(f".{domain}") for domain in _INDEPENDENT_DOMAINS):
        return TrustClass.INDEPENDENT
    return TrustClass.UNKNOWN


def validate_claim_standard(claim: ClaimInput, *, evidence_link_count: int) -> None:
    text = claim.display_text.lower()
    if claim.claim_type in {"founder_trait", "founder_personality"} or any(
        label in text for label in _PERSONALITY_LABELS
    ):
        if claim.assertion_class is not AssertionClass.OPERATOR_ASSERTED:
            raise EvidenceStandardError(
                "Unsupported founder personality labels cannot be model assertions"
            )
        if not claim.operator_attribution:
            raise EvidenceStandardError(
                "Subjective founder observations require operator attribution"
            )
    if (
        claim.claim_type.startswith("founder_")
        and claim.assertion_class is AssertionClass.OPERATOR_ASSERTED
        and not claim.operator_attribution
    ):
        raise EvidenceStandardError("Founder observations require operator attribution")
    if (
        claim.material
        and claim.assertion_class is AssertionClass.EXTERNALLY_VERIFIED
        and evidence_link_count < 1
    ):
        raise EvidenceStandardError("Externally verified material claims require evidence")
