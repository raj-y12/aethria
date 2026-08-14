"""Convert already-validated source payloads into identity observations."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urlparse

from identity.models import SourceChannel, SourceObservationInput
from identity.normalization import normalize_alias, normalize_domain


_PROVIDER_DOMAINS = {
    "linkedin.com": "linkedin",
    "crunchbase.com": "crunchbase",
    "dealroom.co": "dealroom",
    "ycombinator.com": "yc",
}


def _url(value: Any) -> Optional[str]:
    match = re.search(r"https?://[^\s)>\]}\"']+", str(value or ""), re.I)
    return match.group(0).rstrip(".,;:") if match else None


def _domain_slug(domain: str) -> str:
    return normalize_alias(domain.split(".", 1)[0]).replace(" ", "")


def _name_slug(name: str) -> str:
    return normalize_alias(name).replace(" ", "")


def _provider_type(url: str) -> Optional[str]:
    host = str(urlparse(url).hostname or "").lower().removeprefix("www.")
    for domain, provider in _PROVIDER_DOMAINS.items():
        if host == domain or host.endswith(f".{domain}"):
            return provider
    return None


def observation_from_scout_discovery(
    *,
    user_id: str,
    discovery: Dict[str, Any],
    include_legacy_projection: bool = True,
) -> SourceObservationInput:
    """Build a conservative observation without performing another retrieval pass."""

    name = str(discovery.get("name") or "").strip()
    startup_id = str(
        discovery.get("persisted_startup_id") or discovery.get("id") or ""
    ).strip()
    scout_type = str(discovery.get("scout_type") or "unknown").strip()
    references = [url for item in discovery.get("references") or [] if (url := _url(item))]
    provider_identifiers: Dict[str, str] = {}
    candidate_domains = []
    for url in references:
        provider = _provider_type(url)
        if provider:
            provider_identifiers.setdefault(provider, url)
            continue
        domain = normalize_domain(url)
        if domain and domain not in candidate_domains:
            candidate_domains.append(domain)

    name_slug = _name_slug(name)
    official_domain = next(
        (
            domain
            for domain in candidate_domains
            if name_slug and _domain_slug(domain) == name_slug
        ),
        None,
    )
    observed_domain = official_domain or (candidate_domains[0] if len(candidate_domains) == 1 else None)
    confidence = max(0.0, min(1.0, float(discovery.get("confidence") or 0)))
    evidence_sources = [
        {
            "url": url,
            "source_type": (
                "official_site"
                if official_domain and normalize_domain(url) == official_domain
                else (_provider_type(url) or "other")
            ),
        }
        for url in references
    ]
    resolution_payload = {
        "canonical_name": name,
        "website": official_domain,
        "confidence": confidence,
        "resolution_status": "FOUND" if official_domain else "PARTIAL",
        "evidence_sources": evidence_sources,
        "source": "validated_scout_payload",
    }
    is_named_lookup = (
        str(discovery.get("origin_type") or "").strip() == "on_demand_lookup"
    )
    channel = (
        SourceChannel.MANUAL_LOOKUP
        if is_named_lookup
        else SourceChannel.AUTONOMOUS_DISCOVERY
    )
    lookup_id = str(discovery.get("lookup_id") or "").strip() or None
    external_key = (
        f"lookup:{lookup_id or startup_id}"
        if is_named_lookup
        else f"discovery:{startup_id}:{scout_type}"
    )
    return SourceObservationInput(
        user_id=user_id,
        channel=channel,
        observed_name=name,
        observed_domain=observed_domain,
        provider_identifiers=provider_identifiers,
        external_event_key=external_key,
        lookup_id=lookup_id,
        legacy_startup_id=(startup_id or None) if include_legacy_projection else None,
        source_metadata={
            "source": "scout_engine" if not is_named_lookup else "named_lookup",
            "scout_type": scout_type,
            "prompt_version": str(discovery.get("prompt_version") or "").strip() or None,
            "pipeline_run_id": str(discovery.get("pipeline_run_id") or "").strip() or None,
            "reference_count": len(references),
            "operator_confirmed_identity": bool(
                is_named_lookup and str(discovery.get("lookup_website") or "").strip()
            ),
        },
        resolution_payload=resolution_payload,
    )
