"""One analysis sequence: factual packet → Reviewer → validation → Partner.

The caller owns evidence retrieval and persistence. Model calls are injected so
behavioral evaluation is deterministic and the database need not stay locked
while models work.
"""
from __future__ import annotations
from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime
from hashlib import sha256
import json
from typing import Awaitable, Callable
from uuid import uuid4

from pydantic import BaseModel
from tenant_context import require_user_id
from pipeline_state import pipeline_stage_log
from evaluation_v2.models import EvaluationPolicy, EvaluationResult, RecommendationResult, RecommendationState
from evaluation_v2.service import decisive_policy_outcome, materiality_digest
from identity.ownership_gate import check_ownership_conflict
from evaluation_v2.provenance import ScoreOrigin
from pipeline_contracts.models import (
    Identity, Lineage, PolicyVersions, StageMetadata, ReasoningUnit,
    ReviewerOutput, ReviewerAssessment, AnalysisSection, ReviewStatus, ReasoningType,
)
from .models import ReviewerDraft, PartnerDraft, PartnerAction, PartnerDecision, AnalysisResult
from .prompts import REVIEWER_PROMPT, PARTNER_PROMPT, REVIEWER_PROMPT_VERSION, PARTNER_PROMPT_VERSION
from .validation import validate_assessments
from .model_gateway import AnalysisBlocked
from .mandate import check_sector_exclusions
from .grounding import ground_financial_text, reviewer_evidence

Generate = Callable[[str, str, dict, type[BaseModel]], Awaitable[BaseModel]]

# Historical scored-claim payloads remain stored for audit; they cannot become
# the new Reviewer's analytical starting point.
_OPINION_FIELDS = {"criterion_score", "score_band", "score_justification", "score", "recommendation", "primary_thesis", "key_assumptions", "investment_thesis", "conviction_level"}


def reviewer_dimension_name(value: str) -> str:
    """Translate published criterion names into ReviewerDraft enum values."""
    return {"technical": "TECHNOLOGY"}.get(str(value).strip().lower(), str(value).strip().upper())


def factual_packet(snapshot: list[dict]) -> list[dict]:
    def clean(value):
        if isinstance(value, dict):
            return {key: clean(item) for key, item in value.items() if key not in _OPINION_FIELDS}
        if isinstance(value, list):
            return [clean(item) for item in value]
        return value
    return clean(deepcopy(snapshot))


def _bind_review(draft: ReviewerDraft, *, lineage: Lineage, identity: Identity,
                 policy: PolicyVersions, snapshot: list[dict], model: str | None,
                 claim_aliases: dict[str, str] | None = None) -> ReviewerOutput:
    known = {str(claim["claim_id"]): claim for claim in snapshot}
    used_dimensions = [item.dimension for item in draft.assessments]
    if len(set(used_dimensions)) != len(used_dimensions):
        raise ValueError("Reviewer repeated a scoring dimension")

    def units(items):
        result = []
        for item in items:
            refs = item.references.model_copy(update={"claim_ids": [
                (claim_aliases or {}).get(key, key) for key in item.references.claim_ids]})
            claim_ids = [claim_id for claim_id in refs.claim_ids if str(claim_id) in known]
            unsupported_claim = len(claim_ids) != len(refs.claim_ids)
            if unsupported_claim and not known:
                raise ValueError("Reviewer cited a claim outside the tenant snapshot")
            if unsupported_claim:
                refs = refs.model_copy(update={"claim_ids": claim_ids, "evidence_item_ids": [], "source_ids": []})
            linked_evidence = {evidence_id for key in refs.claim_ids for evidence_id in
                               (known[key].get("supporting_evidence_ids") or []) + (known[key].get("contradicting_evidence_ids") or [])}
            evidence_aliases = {
                str(alias): str(link["evidence_item_id"])
                for key in refs.claim_ids
                for link in known[key].get("evidence_relationships") or []
                if link.get("evidence_item_id") in linked_evidence
                for alias in (link.get("evidence_item_id"), link.get("artifact_id"), link.get("source_id"), link.get("source_uri"), link.get("uri"), link.get("url"))
                if alias
            }
            resolved_evidence_ids = {evidence_aliases.get(str(evidence_id), str(evidence_id)) for evidence_id in refs.evidence_item_ids}
            unsupported_evidence = not resolved_evidence_ids.issubset(linked_evidence)
            if unsupported_evidence:
                refs = refs.model_copy(update={"evidence_item_ids": [], "source_ids": []})
            else:
                refs = refs.model_copy(update={"evidence_item_ids": sorted(resolved_evidence_ids)})
            linked_sources = {str(link["artifact_id"]) for key in refs.claim_ids
                              for link in known[key].get("evidence_relationships") or []
                              if link.get("artifact_id") and link.get("evidence_item_id") in linked_evidence}
            source_aliases = {
                str(alias): str(link["artifact_id"])
                for key in refs.claim_ids
                for link in known[key].get("evidence_relationships") or []
                if link.get("artifact_id") and link.get("evidence_item_id") in linked_evidence
                for alias in (link.get("artifact_id"), link.get("source_id"), link.get("source_uri"), link.get("uri"), link.get("url"))
                if alias
            }
            resolved_source_ids = {source_aliases.get(str(source_id), str(source_id)) for source_id in refs.source_ids}
            if not resolved_source_ids.issubset(linked_sources):
                raise ValueError("Reviewer cited a source not linked to its cited claims")
            refs = refs.model_copy(update={"source_ids": sorted(resolved_source_ids)})
            reasoning_type = ReasoningType.UNKNOWN if unsupported_claim or unsupported_evidence else item.type
            if reasoning_type.value in {"FACT", "INFERENCE"} and not refs.claim_ids:
                reasoning_type = ReasoningType.UNKNOWN
            if reasoning_type in {ReasoningType.FACT, ReasoningType.INFERENCE}:
                # The model selects claims; the server supplies their exact
                # already-validated evidence relationships, without invented IDs.
                refs = refs.model_copy(update={"evidence_item_ids": sorted(linked_evidence),
                                               "source_ids": sorted(linked_sources)})
            referenced_claims = [known[key] for key in refs.claim_ids if key in known]
            grounded_text = ground_financial_text(item.text, referenced_claims)
            result.append(ReasoningUnit(reasoning_unit_id=str(uuid4()), type=reasoning_type,
                                        text=("Unverified: " + grounded_text if reasoning_type == ReasoningType.UNKNOWN
                                              and not grounded_text.lower().startswith(("unknown", "unverified")) else grounded_text), references=refs))
        return result

    assessments = [ReviewerAssessment(
        assessment_id=str(uuid4()), dimension=item.dimension, conclusion=item.conclusion,
        proposed_score=item.proposed_score, score_origin=ScoreOrigin.REVIEWER_ASSESSMENT,
        score_rationale=ground_financial_text(item.score_rationale, [known[key] for key in {
            (claim_aliases or {}).get(claim_id, claim_id)
            for unit in item.reasoning for claim_id in unit.references.claim_ids
            if (claim_aliases or {}).get(claim_id, claim_id) in known
        }]) + (" Why not higher: " + "; ".join(item.limitations) if item.limitations else "")
                        + (" Unknown: " + "; ".join(item.unknowns) if item.unknowns else ""),
        confidence=item.confidence, reasoning_units=units(item.reasoning), status=ReviewStatus.PRESENT,
    ) for item in draft.assessments]
    return ReviewerOutput(
        lineage=lineage, identity=identity, policy_versions=policy,
        metadata=StageMetadata(model=model, prompt_version=REVIEWER_PROMPT_VERSION),
        assessments=assessments,
        analysis_sections=[AnalysisSection(name=item.name, status=item.status, reasoning_units=units(item.reasoning)) for item in draft.analysis_sections],
        investment_case=units(draft.investment_case), risks=units(draft.risks),
        unknowns=units(draft.unknowns), contradictions=units(draft.contradictions),
        diligence_priorities=units(draft.diligence_priorities),
        overall_assessment=ground_financial_text(draft.overall_assessment, list(known.values())),
        status=ReviewStatus.PRESENT,
    )


async def analyze(*, user_id: str, lineage: Lineage, identity: Identity,
                  snapshot: list[dict], policy: EvaluationPolicy, context: dict,
                  generate: Generate, evaluation_at: datetime,
                  reviewer_model: str | None = None, partner_model: str | None = None,
                  prior_review: ReviewerOutput | None = None,
                  prior_snapshot: list[dict] | None = None,
                  research: Callable[[list[str]], Awaitable[tuple[list[dict], datetime]]] | None = None) -> AnalysisResult:
    uid = require_user_id(user_id, context="investment_analysis")
    if lineage.user_id != uid:
        raise ValueError("analysis tenant mismatch")
    # Source reads must already have been tenant scoped. Reject any contradictory
    # embedded ownership rather than trusting user-supplied identifiers.
    for claim in snapshot:
        if claim.get("user_id") not in (None, uid):
            raise ValueError("claim tenant mismatch")
        for field in ("company_id", "opportunity_id"):
            expected = getattr(lineage, field)
            if claim.get(field) is not None and str(claim[field]) != str(expected):
                raise ValueError(f"claim {field} mismatch")
    digest = sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if lineage.evidence_snapshot_hash not in (None, digest):
        raise ValueError("analysis snapshot mismatch")
    lineage = lineage.model_copy(update={"pipeline_run_id": lineage.pipeline_run_id or str(uuid4()), "reviewer_run_id": str(uuid4()), "evaluation_run_id": str(uuid4()), "evidence_snapshot_hash": digest})
    trace = []

    def record(stage, status):
        trace.append({"stage": stage, "status": status})
        pipeline_stage_log(lineage.pipeline_run_id, startup_id="", user_id=uid, stage=stage, phase=status)

    @contextmanager
    def track(stage):
        record(stage, "STARTED")
        try:
            yield
        except AnalysisBlocked:
            record(stage, "BLOCKED")
            raise
        except Exception:
            record(stage, "FAILED")
            raise
        record(stage, "DONE")
    versions = PolicyVersions(policy_version=policy.policy_version_id, policy_hash=policy.policy_hash,
                              rubric_version=policy.rubric_version, partner_rules_version=policy.partner_rules_version,
                              thesis_version_id=context.get("thesis_version_id"))
    research_audit = {}
    packet_audit = {}
    # Retain the complete configuration in the immutable audit, but do not
    # feed retired score-to-action thresholds to either analytical stage.
    model_context = deepcopy(context)
    configuration = model_context.get("fund_configuration")
    if isinstance(configuration, dict):
        configuration.pop("thresholds", None)
        configuration.pop("scoreBands", None)
    reviewer_context = deepcopy(model_context)
    reviewer_context.pop("prior_decision", None)

    async def review_once(*, research_attempted=False):
        with track("reviewer"):
            packet, selected, aliases = reviewer_evidence(factual_packet(snapshot), company_name=identity.name or "",
                                                          company_website=identity.website)
            selected_ids = {row["claim_id"] for row in selected}
            excluded_ids = [row["claim_id"] for row in snapshot if row["claim_id"] not in selected_ids]
            if excluded_ids:
                packet_audit.update(claim_aliases=aliases, excluded_claim_ids=excluded_ids,
                                    reason="Duplicate, unrelated source, or unverified founder identity.")
            draft = ReviewerDraft.model_validate(await generate("reviewer", REVIEWER_PROMPT, {
                "company": identity.model_dump(mode="json"), "factual_evidence": packet,
                "fund_context": reviewer_context, "research_attempted": research_attempted,
                "rubric": {
                    "version": policy.rubric_version,
                    "criteria": [{"dimension": reviewer_dimension_name(rule.criterion), "weight": rule.weight, "required": rule.required}
                                 for rule in policy.criteria],
                    "analytical_guidance": context.get("analytical_rubric"),
                },
            }, ReviewerDraft))
            return draft, _bind_review(draft, lineage=lineage, identity=identity, policy=versions,
                                       snapshot=selected, model=reviewer_model, claim_aliases=aliases)
    if prior_review is not None:
        if (prior_review.lineage.user_id != uid
                or prior_review.lineage.opportunity_id != lineage.opportunity_id
                or prior_review.lineage.company_id != lineage.company_id):
            raise ValueError("prior review tenant/opportunity mismatch")
        if prior_snapshot is None:
            raise ValueError("prior review requires its immutable evidence snapshot")
        previous_digest = sha256(json.dumps(prior_snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if (prior_review.lineage.evidence_snapshot_hash != previous_digest
                or materiality_digest(prior_snapshot) != materiality_digest(snapshot)
                or prior_review.metadata.prompt_version != REVIEWER_PROMPT_VERSION
                or prior_review.policy_versions != versions):
            raise AnalysisBlocked("analysis_dependencies_changed", "Prior review dependencies changed; a full review is required.")
        # Reasoning and assessment IDs are reused, with an explicit original
        # Reviewer run. Validation gets a new run and freshness clock below.
        review = prior_review.model_copy(update={"lineage": lineage.model_copy(update={
            "reviewer_run_id": prior_review.lineage.reviewer_run_id,
        })})
    else:
        draft, review = await review_once()
        questions = list(dict.fromkeys(question.strip() for question in draft.research_questions if question.strip()))
        if questions and research is not None:
            with track("targeted_research"):
                updated, updated_at = await research(questions)
                if any(claim.get("user_id") not in (None, uid) for claim in updated):
                    raise ValueError("research snapshot tenant mismatch")
                changed = materiality_digest(updated) != materiality_digest(snapshot)
                research_audit = {"questions": questions, "new_evidence": changed,
                                  "initial_review": review.model_dump(mode="json")}
                snapshot, evaluation_at = updated, updated_at
                digest = sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                lineage = lineage.model_copy(update={"evidence_snapshot_hash": digest,
                    "reviewer_run_id": str(uuid4()) if changed else lineage.reviewer_run_id})
                review = review.model_copy(update={"lineage": lineage})
            if changed:
                draft, review = await review_once(research_attempted=True)
                questions = list(dict.fromkeys(question.strip() for question in draft.research_questions if question.strip()))
        # Unanswered or additional requests remain explicit diligence; never
        # launch an unbounded research loop or tell Partner the answers exist.
        for question in questions:
            review.diligence_priorities.append(ReasoningUnit(
                reasoning_unit_id=str(uuid4()), type=ReasoningType.UNKNOWN,
                text=f"Further factual diligence: {question}",
            ))
    if prior_review is not None:
        record("reviewer", "SKIPPED")
    _, admitted_snapshot, _ = reviewer_evidence(factual_packet(snapshot), company_name=identity.name or "",
                                                company_website=identity.website)
    if prior_review is not None and len(admitted_snapshot) != len(snapshot):
        raise AnalysisBlocked("analysis_dependencies_changed", "Evidence identity admission changed; a full review is required.")
    with track("validation"):
        validation, criteria = validate_assessments(user_id=uid, review=review, snapshot=admitted_snapshot,
                                                    policy=policy, evaluation_at=evaluation_at)
    with track("partner"):
        assessment_aliases = {f"A{index + 1}": item.assessment_id for index, item in enumerate(review.assessments)}
        handles = {value: key for key, value in assessment_aliases.items()}
        partner_review = review.model_dump(mode="json")
        partner_validation = validation.model_dump(mode="json")
        for field in ("lineage", "policy_versions", "metadata"):
            partner_review.pop(field, None)
            partner_validation.pop(field, None)
        for item in partner_review["assessments"]:
            item["assessment_id"] = handles[item["assessment_id"]]
        for item in partner_validation["assessments"]:
            item["reviewer_assessment_id"] = handles.get(item["reviewer_assessment_id"], item["reviewer_assessment_id"])
        decision = PartnerDraft.model_validate(await generate("partner", PARTNER_PROMPT, {
            "company": identity.model_dump(mode="json"), "review": partner_review,
            "validated_assessments": partner_validation, "fund_context": model_context,
            "factual_evidence": reviewer_evidence(factual_packet(snapshot), company_name=identity.name or "",
                                                  company_website=identity.website)[0],
        }, PartnerDraft))
        decision = decision.model_copy(update={"assessment_ids": [
            assessment_aliases.get(key, key) for key in decision.assessment_ids]})
        known_assessments = {item.assessment_id for item in review.assessments}
        if not set(decision.assessment_ids).issubset(known_assessments):
            raise ValueError("Partner cited an assessment outside this review")
        if review.assessments and not decision.assessment_ids:
            raise ValueError("Partner must identify the assessments behind its decision")
        action = decision.action
        safety_state, risks, mandate_conflicts, uncertain, contradictions = decisive_policy_outcome(
            admitted_snapshot, policy, evaluation_at=evaluation_at)
        constraints = []
        sector_conflicts, sector_unknowns = check_sector_exclusions(
            snapshot=admitted_snapshot, fund_config=context.get("fund_configuration") or {},
            policy=policy, evaluation_at=evaluation_at,
        )
        mandate_conflicts.extend(sector_conflicts)
        uncertain.extend(sector_unknowns)
        if sector_conflicts:
            action = PartnerAction.PASS
            constraints.extend(sector_conflicts)
        if safety_state == RecommendationState.PASS:
            action = PartnerAction.PASS
            constraints.extend(mandate_conflicts + risks)
        supported_weight = sum(rule.weight for rule, criterion in zip(policy.criteria, criteria) if criterion.score is not None)
        required_missing = any(rule.required and criterion.score is None for rule, criterion in zip(policy.criteria, criteria))
        if action == PartnerAction.ADVANCE and (required_missing or supported_weight < policy.minimum_scored_weight or uncertain or contradictions or any(item.contradicting_claim_ids for item in criteria)):
            action = PartnerAction.MORE_DILIGENCE
            constraints.append("Evidence policy requires further diligence before advancing.")
        ownership_conflict = check_ownership_conflict(
            {"one_line": "\n".join(str(claim.get("display_text") or "") for claim in admitted_snapshot)}, {},
            company_name=identity.name,
        )
        if ownership_conflict and action != PartnerAction.PASS:
            action = PartnerAction.MORE_DILIGENCE
            constraints.append("Company ownership or acquisition status requires independent verification before advancing.")
        human_review = bool(validation.human_review_required or constraints or action in {PartnerAction.MORE_DILIGENCE, PartnerAction.ADVANCE})
        partner = PartnerDecision(lineage=validation.lineage.model_copy(update={"partner_run_id": str(uuid4())}),
            judgment=decision, operational_action=action, constraints=constraints,
            human_review_required=human_review, prompt_version=PARTNER_PROMPT_VERSION, model=partner_model)
        state = {PartnerAction.ADVANCE: RecommendationState.ADVANCE, PartnerAction.PASS: RecommendationState.PASS,
                 PartnerAction.MONITOR: RecommendationState.MONITOR, PartnerAction.MORE_DILIGENCE: RecommendationState.INSUFFICIENT_EVIDENCE}[action]
        recommendation = RecommendationResult(
            state=state, confidence=decision.confidence,
            decision_drivers=decision.rationale, principal_risks=decision.principal_risks + risks,
            mandate_conflicts=mandate_conflicts,
            missing_information=[text for item in criteria for text in item.missing_evidence] + uncertain,
            change_conditions=decision.next_steps, human_review_required=human_review,
        )
    audit_context = {**deepcopy(context), **({"targeted_research": research_audit} if research_audit else {}),
                     **({"evidence_packet": packet_audit} if packet_audit else {})}
    return AnalysisResult(trace=trace, review_reused=prior_review is not None, context_snapshot=audit_context, reviewer=review, validation=validation, partner=partner,
        evaluation=EvaluationResult(snapshot_hash=digest, criteria=criteria, recommendation=recommendation))
