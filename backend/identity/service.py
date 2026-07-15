"""Deterministic, domain-first identity admission rules."""

from __future__ import annotations

from typing import Any, Dict, List

import env_config
from identity.models import (
    IdentityCandidate,
    NormalizedIdentifier,
    SourceObservationInput,
    VerificationStatus,
)
from identity.normalization import extract_identifier_candidates, normalize_domain


class IdentityService:
    def __init__(self, repository: Any, *, auto_resolve_confidence: float | None = None):
        self.repository = repository
        configured = env_config.get_float("IDENTITY_AUTO_RESOLVE_CONFIDENCE")
        self.auto_resolve_confidence = max(
            0.0,
            min(1.0, configured if auto_resolve_confidence is None else auto_resolve_confidence),
        )

    @staticmethod
    def _picker_candidates(observation: SourceObservationInput) -> List[IdentityCandidate]:
        results: List[IdentityCandidate] = []
        seen_domains = set()
        for raw in (observation.resolution_payload or {}).get("candidates", []):
            if not isinstance(raw, dict):
                continue
            domain = normalize_domain(raw.get("website"))
            if not domain or domain in seen_domains:
                continue
            try:
                confidence = max(0.0, min(1.0, float(raw.get("confidence") or 0)))
            except (TypeError, ValueError):
                confidence = 0.0
            seen_domains.add(domain)
            results.append(
                IdentityCandidate(
                    canonical_name=str(raw.get("name") or observation.observed_name).strip(),
                    canonical_domain=domain,
                    confidence=confidence,
                    evidence_urls=[str(raw.get("website"))],
                    reason="picker_candidate",
                )
            )
        return results

    @staticmethod
    def _matched_candidates(matches: List[Dict[str, Any]]) -> List[IdentityCandidate]:
        candidates: List[IdentityCandidate] = []
        seen = set()
        for match in matches:
            company_id = str(match.get("company_id") or "").strip()
            if not company_id or company_id in seen:
                continue
            seen.add(company_id)
            candidates.append(
                IdentityCandidate(
                    company_id=company_id,
                    canonical_name=str(match.get("canonical_name") or "Unknown"),
                    canonical_domain=match.get("canonical_domain"),
                    confidence=float(match.get("confidence") or 1.0),
                    reason="verified_identifier_match",
                )
            )
        return candidates

    async def admit(self, observation: SourceObservationInput):
        stored = await self.repository.record_observation(observation)
        existing = await self.repository.get_admission_for_observation(
            user_id=observation.user_id,
            observation_id=stored.observation_id,
        )
        if existing is not None:
            return existing

        identifiers = extract_identifier_candidates(observation)
        verified = [
            item
            for item in identifiers
            if item.verification_status is VerificationStatus.VERIFIED
        ]
        matches = await self.repository.find_companies_by_verified_identifiers(
            user_id=observation.user_id,
            identifiers=verified,
        )
        matched_candidates = self._matched_candidates(matches)
        picker_candidates = self._picker_candidates(observation)
        strong_picker = [
            candidate
            for candidate in picker_candidates
            if candidate.confidence >= self.auto_resolve_confidence
        ]

        if len(matched_candidates) > 1 or len(strong_picker) > 1:
            candidates = matched_candidates or strong_picker
            confidence = max((item.confidence for item in candidates), default=0.0)
            return await self.repository.open_identity_case(
                observation=observation,
                observation_id=stored.observation_id,
                candidates=candidates,
                reason_code=(
                    "conflicting_verified_identifiers"
                    if len(matched_candidates) > 1
                    else "multiple_strong_candidates"
                ),
                confidence=confidence,
            )

        if len(matched_candidates) == 1:
            match = matched_candidates[0]
            matched_identifier = verified[0] if verified else None
            return await self.repository.resolve_existing_admission(
                user_id=observation.user_id,
                observation_id=stored.observation_id,
                company_id=match.company_id,
                context_key=observation.opportunity_context_key,
                matched_identifier=matched_identifier,
                identifiers=identifiers,
                confidence=max(match.confidence, matched_identifier.confidence if matched_identifier else 0),
            )

        if verified:
            return await self.repository.create_company_admission(
                observation=observation,
                observation_id=stored.observation_id,
                identifiers=identifiers,
                confidence=max(item.confidence for item in verified),
            )

        if len(strong_picker) == 1:
            candidate = strong_picker[0]
            return await self.repository.create_company_admission(
                observation=observation,
                observation_id=stored.observation_id,
                identifiers=identifiers,
                confidence=candidate.confidence,
                canonical_name=candidate.canonical_name,
                canonical_domain=candidate.canonical_domain,
            )

        confidence = max(
            [item.confidence for item in picker_candidates]
            + [float((observation.resolution_payload or {}).get("confidence") or 0)]
        )
        return await self.repository.open_identity_case(
            observation=observation,
            observation_id=stored.observation_id,
            candidates=picker_candidates,
            reason_code="insufficient_verified_identifier",
            confidence=max(0.0, min(1.0, confidence)),
        )
