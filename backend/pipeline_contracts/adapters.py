"""Pure, opt-in current-payload adapters. No I/O, scoring or authority changes.

Projection replays the captured JSON payload, not edits to target fields. This
makes the legacy boundary reversible without making target fields authoritative.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any, Mapping

from pydantic import BaseModel
from pydantic_core import to_jsonable_python

from tenant_context import require_user_id
from evaluation_v2.provenance import ScoreOrigin
from .models import (
    AnalysisSection, AnalysisSectionType, AssessmentValidationResult,
    ContradictionStatus, Envelope, Identity, LegacyExtension, Lineage,
    PartnerOutput, PolicyResult, PolicyVersions, ReasoningType, ReasoningUnit,
    RecommendationOrigin, References, ReviewerAssessment, ReviewerOutput,
    ReviewStatus, ScoutOutput, SourceReference, StageMetadata,
    ValidatedAssessment, ValidationStatus,
)

DIMENSIONS = {
    "market": AnalysisSectionType.MARKET,
    "product": AnalysisSectionType.PRODUCT,
    "technical": AnalysisSectionType.TECHNOLOGY,
    "execution": AnalysisSectionType.EXECUTION,
    "defensibility": AnalysisSectionType.DEFENSIBILITY,
}


def _payload(user_id: str, payload: Mapping[str, Any] | BaseModel, lineage: Lineage):
    uid = require_user_id(user_id, context="pipeline_contract_adapter")
    if lineage.user_id != uid:
        raise ValueError("contract tenant mismatch")
    value = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else to_jsonable_python(dict(payload))

    def check(node):
        if isinstance(node, dict):
            if node.get("user_id") not in (None, uid):
                raise ValueError("payload tenant mismatch")
            for field in ("company_id", "opportunity_id"):
                known = getattr(lineage, field)
                if known is not None and node.get(field) not in (None, known):
                    raise ValueError(f"payload {field} mismatch")
            for child in node.values():
                check(child)
        elif isinstance(node, list):
            for child in node:
                check(child)
    check(value)
    # Reject non-JSON numbers rather than silently rewriting legacy payloads.
    json.dumps(value, allow_nan=False)
    return deepcopy(value)


def _identifier(lineage: Lineage, kind: str, raw: dict, path: str) -> str:
    value = [lineage.model_dump(mode="json"), kind, raw, path]
    digest = sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return f"compat-v1-{digest}"


def _units(lineage, kind, raw, path, values, reasoning_type=ReasoningType.UNKNOWN):
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    # Do not stringify structured legacy data into invented narrative.
    return [ReasoningUnit(reasoning_unit_id=_identifier(lineage, kind, raw, f"{path}/{i}"),
                          type=reasoning_type, text=value)
            for i, value in enumerate(values) if isinstance(value, str)]


def _legacy(kind, raw, *mismatches):
    return LegacyExtension(payload_kind=kind, original_payload=raw, mismatches=list(mismatches))


def _policies(raw):
    return PolicyVersions(
        thesis_version_id=raw.get("thesis_version_id") or raw.get("fund_thesis_version_id"),
        policy_version=raw.get("policy_version_id") or raw.get("policy_version"),
        policy_hash=raw.get("policy_hash"),
        rubric_version=raw.get("rubric_version") or raw.get("evaluation_rubric_version"),
        reviewer_rules_version=raw.get("reviewer_rules_version"),
        partner_rules_version=raw.get("partner_rules_version"),
    )


def _bound_lineage(lineage, raw, fields):
    additions = {}
    for target, source in fields.items():
        value = raw.get(source)
        if value is not None:
            existing = getattr(lineage, target)
            if existing is not None and existing != value:
                raise ValueError(f"lineage {target} mismatch")
            additions[target] = value
    return Lineage.model_validate({**lineage.model_dump(), **additions})


def adapt_current_scout_to_scout_output(*, user_id: str, payload, lineage: Lineage) -> ScoutOutput:
    raw = _payload(user_id, payload, lineage)
    return ScoutOutput(
        lineage=lineage,
        identity=Identity(name=raw.get("name"), website=raw.get("lookup_website"),
                          resolution_status=raw.get("resolution_status")),
        # Legacy narrative is not verified factual evidence. Retain it intact in
        # compatibility until factual-only Scout is implemented in a later phase.
        unknowns=_units(lineage, "scout", raw, "biggest_unknown", raw.get("biggest_unknown")),
        sources=[SourceReference(description=value) for value in raw.get("references") or [] if isinstance(value, str)],
        metadata=StageMetadata(model=raw.get("model"), prompt_version=raw.get("prompt_version")),
        compatibility=_legacy("scout", raw, "legacy_narrative_not_verified_facts", "investment_fields_retained_only_in_compatibility"),
    )


def adapt_current_review_to_reviewer_output(*, user_id: str, payload, lineage: Lineage) -> ReviewerOutput:
    raw = _payload(user_id, payload, lineage)
    assessments = []
    for dimension, section in DIMENSIONS.items():
        score_key = f"{dimension}_score"
        reasoning = (raw.get("score_reasoning") or {}).get(score_key)
        values = raw.get(f"{dimension}_reasoning")
        if score_key not in raw and values is None and reasoning is None:
            continue
        assessments.append(ReviewerAssessment(
            assessment_id=_identifier(lineage, "reviewer", raw, dimension), dimension=section,
            # Historical numeric values stay out of proposed_score. The current
            # reviewer has not produced a target ReviewerAssessment proposal.
            score_origin=(ScoreOrigin(raw["score_origin"]) if raw.get("score_origin") in {origin.value for origin in ScoreOrigin}
                          else ScoreOrigin.UNKNOWN_LEGACY) if raw.get(score_key) is not None else None,
            score_rationale=reasoning,
            reasoning_units=_units(lineage, "reviewer", raw, dimension, values),
            status=ReviewStatus.PRESENT if values or reasoning or raw.get(score_key) is not None else ReviewStatus.UNKNOWN,
        ))
    sections = []
    for key, section in (("team_analysis", AnalysisSectionType.TEAM),
                         ("competition_analysis", AnalysisSectionType.COMPETITION),
                         ("business_model_analysis", AnalysisSectionType.BUSINESS_MODEL)):
        if key in raw:
            sections.append(AnalysisSection(name=section,
                status=ReviewStatus.PRESENT if raw[key] else ReviewStatus.UNKNOWN,
                reasoning_units=_units(lineage, "reviewer", raw, key, raw[key])))
    return ReviewerOutput(
        lineage=lineage, identity=Identity(), assessments=assessments, analysis_sections=sections,
        investment_case=_units(lineage, "reviewer", raw, "investment_thesis", raw.get("investment_thesis")),
        risks=_units(lineage, "reviewer", raw, "key_risks", raw.get("key_risks")),
        diligence_priorities=_units(lineage, "reviewer", raw, "diligence_red_flags", raw.get("diligence_red_flags")),
        overall_assessment=raw.get("overall_summary"),
        status=ReviewStatus.PRESENT if raw else ReviewStatus.UNKNOWN,
        policy_versions=_policies(raw),
        metadata=StageMetadata(model=raw.get("model"), prompt_version=raw.get("prompt_version")),
        compatibility=_legacy("reviewer", raw, "legacy_scores_are_not_target_proposals", "unclassified_narrative_has_unknown_reasoning_type", "context_claims_are_not_per_assessment_support"),
    )


def adapt_current_evaluation_to_validation_result(*, user_id: str, payload, lineage: Lineage) -> AssessmentValidationResult:
    raw = _payload(user_id, payload, lineage)
    # Both repository DTO and pure EvaluationResult are supported.
    run = raw.get("evaluation") or raw
    lineage = _bound_lineage(lineage, run, {
        "evaluation_run_id": "evaluation_id", "evidence_snapshot_hash": "evidence_snapshot_hash",
    })
    lineage = _bound_lineage(lineage, run, {"evidence_snapshot_hash": "snapshot_hash"})
    provenance = raw.get("provenance") or {}
    lineage = _bound_lineage(lineage, provenance, {
        "evaluation_run_id": "evaluation_run_id", "evidence_snapshot_hash": "evidence_snapshot_hash",
    })
    policy = _policies(run)
    recommendation = raw.get("recommendation") or {}
    assessments = []
    for item in raw.get("criteria") or []:
        dimension = DIMENSIONS.get(item["criterion"])
        if dimension is None:
            # Future/foreign criteria remain losslessly visible in compatibility.
            continue
        claim_ids = item.get("supporting_claim_ids") or []
        links = [link for link in provenance.get("evidence_links") or [] if link.get("claim_id") in claim_ids]
        assessments.append(ValidatedAssessment(
            dimension=dimension, canonical_criterion_assessment_id=item.get("criterion_assessment_id"),
            validated_score=item.get("score"), score_origin=ScoreOrigin.CANONICAL_EVALUATION,
            score_status=ValidationStatus.CURRENT_EVALUATION,
            # No invented reviewer-assessment reference, validation run, proposed
            # score, aggregate coverage or aggregate cap for pre-Reviewer scoring.
            contradiction_status=(ContradictionStatus.PRESENT if item.get("contradicting_claim_ids") else
                                  ContradictionStatus.NONE_RECORDED if "contradicting_claim_ids" in item else ContradictionStatus.UNKNOWN),
            contradicting_claim_ids=item.get("contradicting_claim_ids") or [],
            policy_flags=item.get("quality_flags") or [],
            human_review_required=recommendation.get("human_review_required"),
            references=References(claim_ids=claim_ids,
                evidence_item_ids=sorted({link["evidence_item_id"] for link in links if link.get("evidence_item_id")}),
                source_ids=sorted({link["source_id"] for link in links if link.get("source_id")})),
            policy_versions=policy,
        ))
    return AssessmentValidationResult(lineage=lineage, policy_versions=policy, assessments=assessments,
        human_review_required=recommendation.get("human_review_required"),
        compatibility=_legacy("evaluation", raw, "pre_reviewer_scoring_not_proposal_validation", "canonical_recommendation_retained_in_compatibility", "exact_claim_caps_and_sufficiency_retained_without_reinterpretation"))


def adapt_current_partner_to_partner_output(*, user_id: str, payload, lineage: Lineage) -> PartnerOutput:
    raw = _payload(user_id, payload, lineage)
    provenance = raw.get("provenance") or {}
    lineage = _bound_lineage(lineage, provenance, {
        "evaluation_run_id": "evaluation_run_id", "evidence_snapshot_hash": "evidence_snapshot_hash",
    })
    return PartnerOutput(
        lineage=lineage, decision=raw.get("recommendation"),
        recommendation_origin=provenance.get("recommendation_origin") or RecommendationOrigin.UNKNOWN_LEGACY,
        rationale=[raw["decision_rationale"]] if raw.get("decision_rationale") is not None else [],
        investment_case=_units(lineage, "partner", raw, "thesis", raw.get("thesis")),
        principal_risks=_units(lineage, "partner", raw, "risks", raw.get("risks")),
        next_steps=[raw["next_action"]] if raw.get("next_action") is not None else [],
        conviction=raw.get("confidence"),
        policy_result=PolicyResult(human_review_required=raw.get("human_review_required"),
            mandate_gate=raw.get("mandate_gate"),
            policy_changed_recommendation=provenance.get("policy_changed_recommendation"),
            guard_changed_recommendation=provenance.get("guard_changed_recommendation")),
        policy_versions=_policies(provenance),
        metadata=StageMetadata(model=provenance.get("partner_model"), prompt_version=raw.get("prompt_version")),
        compatibility=_legacy("partner", raw, "existing_decision_authority_preserved", "unrecorded_assessment_relationships_remain_absent"),
    )


def adapt_current_evidence_review(*, user_id: str, payload, lineage: Lineage) -> ReviewerOutput:
    raw = _payload(user_id, payload, lineage)
    lineage = _bound_lineage(lineage, raw, {"evaluation_run_id": "evaluation_id"})
    return ReviewerOutput(lineage=lineage, identity=Identity(),
        risks=_units(lineage, "evidence_review", raw, "principal_risks", raw.get("principal_risks")),
        unknowns=_units(lineage, "evidence_review", raw, "missing_information", raw.get("missing_information")),
        compatibility=_legacy("evidence_review", raw, "deterministic_evaluation_summary_not_reviewer_assessments"))


def adapt_current_partner_route(*, user_id: str, payload, lineage: Lineage) -> PartnerOutput:
    raw = _payload(user_id, payload, lineage)
    return PartnerOutput(lineage=lineage, recommendation_origin=RecommendationOrigin.DETERMINISTIC_PARTNER,
        rationale=raw.get("rationale") or [],
        policy_result=PolicyResult(human_review_required=raw.get("human_review_required")),
        compatibility=_legacy("partner_route", raw, "canonical_route_not_investment_decision"))


def project_current_payload(*, user_id: str, contract: Envelope) -> dict:
    """Replay captured current JSON only. Never synthesize a legacy decision."""
    uid = require_user_id(user_id, context="pipeline_contract_projection")
    if uid != contract.lineage.user_id:
        raise ValueError("contract tenant mismatch")
    if contract.compatibility is None:
        raise ValueError("no current payload captured; target-to-legacy synthesis is not implemented")
    return _payload(uid, contract.compatibility.original_payload, contract.lineage)
