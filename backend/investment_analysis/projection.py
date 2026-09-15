"""One-way display projection of persisted analysis, never another authority."""
from models import ReviewInfo, PartnerInfo, PartnerSnapshot, PartnerProvenance
from tenant_context import require_user_id
from .models import AnalysisResult, PartnerAction


def legacy_stage_projection(*, user_id: str, analysis: AnalysisResult) -> tuple[dict, dict, dict]:
    uid = require_user_id(user_id, context="investment_compatibility_projection")
    for stage in (analysis.reviewer, analysis.validation, analysis.partner):
        if stage.lineage.user_id != uid:
            raise ValueError("investment projection tenant mismatch")
    review, partner = analysis.reviewer, analysis.partner
    dimensions = {item.dimension.value: item for item in review.assessments}
    sections = {item.name.value: [unit.text for unit in item.reasoning_units] for item in review.analysis_sections}
    policy = review.policy_versions
    review_info = ReviewInfo(
        overall_summary=review.overall_assessment or "Analysis unavailable",
        verdict=None, key_risks=[item.text for item in review.risks],
        diligence_red_flags=[item.text for item in review.diligence_priorities],
        investment_thesis=[item.text for item in review.investment_case],
        team_analysis=sections.get("TEAM"), competition_analysis=sections.get("COMPETITION"),
        business_model_analysis=sections.get("BUSINESS_MODEL"),
        policy_version_id=policy.policy_version, policy_hash=policy.policy_hash,
        rubric_version=policy.rubric_version, fund_thesis_version_id=policy.thesis_version_id,
        prompt_version=review.metadata.prompt_version,
        **{key.lower() + "_reasoning": [unit.text for unit in item.reasoning_units]
           for key, item in dimensions.items() if key in {"MARKET", "PRODUCT", "EXECUTION", "DEFENSIBILITY"}},
        technical_reasoning=[unit.text for unit in dimensions["TECHNOLOGY"].reasoning_units] if "TECHNOLOGY" in dimensions else None,
    )
    def conclusion(name):
        return dimensions[name].conclusion if name in dimensions else "Not assessed; further evidence is needed."
    recommendation = {PartnerAction.ADVANCE: "INVEST", PartnerAction.PASS: "PASS",
                      PartnerAction.MONITOR: "MONITOR", PartnerAction.MORE_DILIGENCE: "MONITOR"}[partner.operational_action]
    partner_info = PartnerInfo(
        thesis=partner.judgment.investment_case,
        why_this_matters=review.overall_assessment or "Further analysis required.",
        snapshot=PartnerSnapshot(one_liner=review.identity.name or "Company"),
        market_insight=conclusion("MARKET"), product_edge=conclusion("PRODUCT"),
        risks=partner.judgment.principal_risks, recommendation=recommendation,
        decision_rationale="\n".join(partner.judgment.rationale + partner.constraints),
        confidence=partner.judgment.confidence, next_action="\n".join(partner.judgment.next_steps) or "Review the completed investment assessment.",
        human_review_required=partner.human_review_required, prompt_version=partner.prompt_version,
        provenance=PartnerProvenance(
            original_recommendation_origin="PARTNER_ANALYSIS", recommendation_origin="PARTNER_ANALYSIS",
            partner_recommendation=recommendation,
            canonical_recommendation=analysis.evaluation.recommendation.state.value,
            evaluation_run_id=partner.lineage.evaluation_run_id,
            evidence_snapshot_hash=partner.lineage.evidence_snapshot_hash,
            policy_version=policy.policy_version, partner_rules_version=policy.partner_rules_version,
            partner_model=partner.model, human_review_required=partner.human_review_required,
            policy_changed_recommendation=partner.operational_action != partner.judgment.action,
        ),
    )
    trace = {
        "reviewer": {"stage": "reviewer", "status": "completed", "reviewer_run_id": review.lineage.reviewer_run_id,
                     "reused": analysis.review_reused,
                     "pipeline_run_id": review.lineage.pipeline_run_id, "reviewer_model": review.metadata.model,
                     "reviewer_prompt_version": review.metadata.prompt_version, "score_origin": "REVIEWER_ASSESSMENT",
                     "evaluation_run_id": review.lineage.evaluation_run_id},
        "partner": {"stage": "partner", "status": "completed", "partner_run_id": partner.lineage.partner_run_id,
                    "pipeline_run_id": partner.lineage.pipeline_run_id, "partner_model": partner.model,
                    "partner_prompt_version": partner.prompt_version, "provenance": partner_info.provenance.model_dump(mode="json"),
                    "judgment_action": partner.judgment.action.value, "operational_action": partner.operational_action.value},
    }
    return review_info.model_dump(mode="json"), partner_info.model_dump(mode="json"), trace
