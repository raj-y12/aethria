"""Append-only evaluation repository and current-pointer transaction."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from evaluation_v2.provenance import PipelineBinding, evaluation_provenance
from evaluation_v2.models import EvaluationPolicy
from investment_analysis.models import AnalysisResult
from evaluation_v2.evidence_projection import enriched_claim_evidence_sql
from evaluation_v2.service import (
    evaluate_snapshot,
    evaluate_claim_score_eligibility,
    explain_recommendation_change,
    materiality_digest,
    snapshot_claims,
)
from tenant_context import require_user_id
from utils.timeutil import utcnow


def _json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


class EvaluationLifecycleError(RuntimeError):
    """The opportunity lifecycle does not currently permit evaluation."""


class EvaluationRepository:
    def __init__(
        self,
        pool: Any,
        *,
        clock: Callable[[], datetime] = utcnow,
        authority_service: Any = None,
    ):
        self.pool = pool
        self._clock = clock
        self.authority_service = authority_service

    async def _require_write_path(self, *, user_id: str, operation: str) -> None:
        if self.authority_service is not None:
            await self.authority_service.require_write_path(
                user_id=user_id, operation=operation
            )

    @staticmethod
    async def _outbox(conn: Any, *, user_id: str, aggregate_id: str, event_type: str, payload: Dict[str, Any]):
        await conn.execute(
            """
            insert into public.domain_outbox (
              event_id,user_id,aggregate_type,aggregate_id,event_type,event_version,
              payload,publication_attempts,next_attempt_at,created_at
            ) values ($1,$2,'evaluation',$3,$4,1,$5::jsonb,0,now(),now())
            """,
            str(uuid4()), user_id, aggregate_id, event_type, json.dumps(payload),
        )

    async def evaluate(
        self,
        *,
        user_id: str,
        opportunity_id: str,
        actor_id: str,
        trigger_type: str,
        policy: EvaluationPolicy,
        thesis_version_id: Optional[str] = None,
        model_manifest: Optional[Dict[str, Any]] = None,
        prompt_manifest: Optional[Dict[str, Any]] = None,
        judgment_audit: Optional[Dict[str, Any]] = None,
        pipeline_binding: Optional[PipelineBinding] = None,
        prepared_analysis: Optional[AnalysisResult] = None,
        analysis_at: Optional[datetime] = None,
        expected_evaluation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        uid = require_user_id(user_id, context="EvaluationRepository.evaluate")
        if pipeline_binding is not None and pipeline_binding.user_id != uid:
            raise ValueError("pipeline binding tenant mismatch")
        if prepared_analysis is not None:
            if prepared_analysis.reviewer.lineage.user_id != uid or prepared_analysis.reviewer.lineage.opportunity_id != opportunity_id:
                raise ValueError("prepared analysis tenant/opportunity mismatch")
            if prepared_analysis.reviewer.policy_versions.policy_hash != policy.policy_hash:
                raise ValueError("prepared analysis policy mismatch")
            if analysis_at is None:
                raise ValueError("prepared analysis requires its frozen evidence clock")
            judgment_audit = {**(judgment_audit or {}), "investment_analysis": prepared_analysis.model_dump(mode="json")}
        await self._require_write_path(user_id=uid, operation="evaluation creation")
        async with self.pool.acquire() as conn:
            async with conn.transaction(isolation="repeatable_read"):
                if self.authority_service is not None and hasattr(self.authority_service, "assert_write_path_on_connection"):
                    await self.authority_service.assert_write_path_on_connection(conn, user_id=uid, operation="evaluation creation")
                previous = await conn.fetchrow(
                    """
                    select o.service_level, o.decision_state, o.legacy_startup_id,
                           o.workflow_version, o.workflow_state, o.company_id,
                           o.current_evaluation_id,
                           s.agent_trace as source_agent_trace,
                           s.investment_memo_markdown as prior_memo,
                           s.review_info as prior_review_info,
                           s.partner_info as prior_partner_info, r.*
                    from public.opportunities o
                    left join public.startups s
                      on s.user_id = o.user_id and s.startup_id = o.legacy_startup_id::text
                    left join public.recommendations r
                      on r.user_id = o.user_id
                     and r.recommendation_id = o.current_recommendation_id
                    where o.user_id = $1 and o.opportunity_id = $2
                    for update of o
                    """,
                    uid,
                    opportunity_id,
                )
                if previous is None:
                    raise LookupError("Opportunity not found for tenant")
                if prepared_analysis is not None:
                    current_id = previous.get("current_evaluation_id")
                    if (str(current_id) if current_id is not None else None) != expected_evaluation_id:
                        raise EvaluationLifecycleError(
                            "A newer evaluation completed during analysis; retry against the current review"
                        )
                if int(previous.get("service_level") or 0) <= 0:
                    raise EvaluationLifecycleError(
                        "Evaluation is paused for this opportunity"
                    )
                if str(previous.get("decision_state") or "") == "archived":
                    raise EvaluationLifecycleError(
                        "Archived opportunities cannot be evaluated"
                    )
                # Fixed 2026-08-18 (audit HIGH-H7): this guard used to only
                # check for "archived" -- a re-triggered lookup/dispatch on an
                # already-INVESTED opportunity could silently overwrite
                # current_recommendation_id and, further below, unconditionally
                # transition workflow_state back to "ruling_pending" via
                # transition_workflow_on_connection (which itself performs no
                # state-machine legality check), as if the investment decision
                # never happened. decision_state="invested" and a completed/
                # monitoring workflow both represent a human decision already
                # made; re-evaluation must not silently reopen either.
                if str(previous.get("decision_state") or "") == "invested":
                    raise EvaluationLifecycleError(
                        "Invested opportunities cannot be silently re-evaluated"
                    )
                if str(previous.get("workflow_state") or "") in ("completed", "monitoring"):
                    raise EvaluationLifecycleError(
                        "Opportunities with a completed workflow cannot be silently re-evaluated"
                    )
                previous_payload = (
                    dict(previous) if previous.get("recommendation_id") else None
                )
                claims = [
                    dict(row)
                    for row in await conn.fetch(
                        """
                        select * from public.claims
                        where user_id = $1 and opportunity_id = $2
                          and status in ('current','contradicted')
                        order by claim_id
                        """,
                        uid, opportunity_id,
                    )
                ]
                for claim in claims:
                    if isinstance(claim.get("normalized_value"), str):
                        claim["normalized_value"] = json.loads(claim["normalized_value"])
                links = [
                    dict(row)
                    for row in await conn.fetch(
                        enriched_claim_evidence_sql(),
                        uid, opportunity_id,
                    )
                ]
                evaluation_at = analysis_at or self._clock()
                snapshot, digest = snapshot_claims(
                    claims, links, evaluation_at=evaluation_at
                )
                content_digest = materiality_digest(snapshot)
                if prepared_analysis is not None:
                    if digest != prepared_analysis.evaluation.snapshot_hash:
                        raise EvaluationLifecycleError("Evidence changed during analysis; retry against the current snapshot")
                    result = prepared_analysis.evaluation
                    if previous.get("current_evaluation_id"):
                        prior_criteria = await conn.fetch(
                            "select criterion,score,reasoning from public.criterion_assessments where user_id=$1 and evaluation_id=$2",
                            uid, str(previous["current_evaluation_id"]),
                        )
                        prior_by_dimension = {row["criterion"]: row for row in prior_criteria}
                        for criterion in result.criteria:
                            old = prior_by_dimension.get(criterion.criterion)
                            if old is not None:
                                criterion.deterministic_adjustments["change_from_prior_review"] = {
                                    "previous_score": old["score"],
                                    "previous_reasoning": old["reasoning"],
                                    "score_changed": old["score"] != criterion.score,
                                    "reasoning_changed": old["reasoning"] != criterion.reasoning,
                                }
                else:
                    # Retained for historical replay and Phase 0 regression tests.
                    # Live entry points use InvestmentAnalysisRepository.
                    result = evaluate_snapshot(snapshot, policy, evaluation_at=evaluation_at)
                # Lineage is separate from the frozen decision snapshot: adding
                # observability must not alter snapshot hashes or score inputs.
                source_trace = _json(previous.get("source_agent_trace"), {})
                if prepared_analysis is not None and previous.get("legacy_startup_id"):
                    # Cache invalidation must not erase the previous analyst view.
                    # This immutable audit copy is tenant scoped with the run.
                    judgment_audit["superseded_startup_projection"] = {
                        "investment_memo_markdown": previous.get("prior_memo"),
                        "review_info": _json(previous.get("prior_review_info"), None),
                        "partner_info": _json(previous.get("prior_partner_info"), None),
                        "agent_trace": source_trace,
                    }
                source_scout = source_trace.get("scout") or {}
                recorded_binding = pipeline_binding or PipelineBinding(
                    user_id=uid, pipeline_entry_type=trigger_type,
                )
                recorded_binding = recorded_binding.model_copy(update={
                    "pipeline_run_id": recorded_binding.pipeline_run_id or (prepared_analysis.reviewer.lineage.pipeline_run_id if prepared_analysis else None),
                    "company_id": recorded_binding.company_id or (str(previous["company_id"]) if previous.get("company_id") else None),
                    "scout_run_id": recorded_binding.scout_run_id or source_scout.get("scout_run_id"),
                    "source_scout_pipeline_run_id": recorded_binding.source_scout_pipeline_run_id or source_scout.get("pipeline_run_id"),
                })
                recorded_model_manifest = dict(model_manifest or {})
                recorded_model_manifest["pipeline_provenance"] = {
                    "binding": recorded_binding.model_dump(mode="json"),
                    "claim_validation": {
                        str(claim["claim_id"]): evaluate_claim_score_eligibility(
                            claim, policy=policy, evaluation_at=evaluation_at,
                        ).model_dump(mode="json") for claim in snapshot
                    },
                    "evidence_links": [
                        {key: str(link[key]) if link.get(key) is not None else None for key in (
                            "claim_id", "evidence_item_id", "artifact_id", "source_uri", "source_observation_id", "relationship",
                        )} for link in links
                    ],
                }
                evaluation_id = prepared_analysis.reviewer.lineage.evaluation_run_id if prepared_analysis is not None else str(uuid4())
                await conn.execute(
                    """
                    insert into public.evaluation_runs (
                      evaluation_id,user_id,opportunity_id,trigger_type,actor_id,
                      evidence_snapshot_hash,evidence_materiality_digest,
                      claim_snapshot,judgment_audit,thesis_version_id,
                      policy_version_id,policy_hash,rubric_version,
                      partner_rules_version,partner_rules_hash,model_manifest,
                      prompt_manifest,status,supersedes_evaluation_id,started_at,created_at
                    ) values ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9::jsonb,$10,$11,$12,$13,$14,$15,$16::jsonb,$17::jsonb,'running',$18,now(),now())
                    """,
                    evaluation_id, uid, opportunity_id, trigger_type, actor_id,
                    digest, content_digest, json.dumps(snapshot), json.dumps(judgment_audit or {}), thesis_version_id,
                    policy.policy_version_id, policy.policy_hash, policy.rubric_version,
                    policy.partner_rules_version, policy.partner_rules_hash,
                    json.dumps(recorded_model_manifest), json.dumps(prompt_manifest or {}),
                    previous_payload.get("evaluation_id") if previous_payload else None,
                )
                for criterion in result.criteria:
                    await conn.execute(
                        """
                        insert into public.criterion_assessments (
                          criterion_assessment_id,user_id,evaluation_id,criterion,score,
                          confidence,evidence_sufficiency,reasoning,supporting_claim_ids,
                          contradicting_claim_ids,missing_evidence,quality_flags,
                          deterministic_adjustments,created_at
                        ) values ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10::jsonb,$11::jsonb,$12::jsonb,$13::jsonb,now())
                        """,
                        str(uuid4()), uid, evaluation_id, criterion.criterion, criterion.score,
                        criterion.confidence, criterion.evidence_sufficiency, criterion.reasoning,
                        json.dumps(criterion.supporting_claim_ids),
                        json.dumps(criterion.contradicting_claim_ids),
                        json.dumps(criterion.missing_evidence), json.dumps(criterion.quality_flags),
                        json.dumps(criterion.deterministic_adjustments),
                    )
                recommendation_id = str(uuid4())
                recommendation = result.recommendation.model_copy(
                    update={
                        "change_explanation": explain_recommendation_change(
                            previous_payload, result.recommendation
                        )
                    }
                )
                await conn.execute(
                    """
                    insert into public.recommendations (
                      recommendation_id,user_id,opportunity_id,evaluation_id,
                      recommended_state,attention_priority,confidence,decision_drivers,
                      principal_risks,mandate_conflicts,missing_information,
                      change_conditions,human_review_required,previous_recommendation_id,
                      change_explanation,created_at
                    ) values ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9::jsonb,$10::jsonb,$11::jsonb,$12::jsonb,$13,$14,$15,now())
                    """,
                    recommendation_id, uid, opportunity_id, evaluation_id,
                    recommendation.state.value, recommendation.attention_priority,
                    recommendation.confidence, json.dumps(recommendation.decision_drivers),
                    json.dumps(recommendation.principal_risks),
                    json.dumps(recommendation.mandate_conflicts),
                    json.dumps(recommendation.missing_information),
                    json.dumps(recommendation.change_conditions),
                    recommendation.human_review_required,
                    previous_payload.get("recommendation_id") if previous_payload else None,
                    recommendation.change_explanation,
                )
                await conn.execute(
                    "update public.evaluation_runs set status='completed', completed_at=now() where evaluation_id=$1 and user_id=$2 and status='running'",
                    evaluation_id, uid,
                )
                await conn.execute(
                    """
                    update public.opportunities
                    set current_evaluation_id=$3,current_recommendation_id=$4,
                        attention_priority=$5,updated_at=now()
                    where opportunity_id=$1 and user_id=$2
                    """,
                    opportunity_id, uid, evaluation_id, recommendation_id,
                    recommendation.attention_priority,
                )
                if prepared_analysis is not None and previous.get("legacy_startup_id"):
                    from investment_analysis.projection import legacy_stage_projection
                    review_projection, partner_projection, trace_projection = legacy_stage_projection(user_id=uid, analysis=prepared_analysis)
                    await conn.execute(
                        """update public.startups set review_info=$3::jsonb,partner_info=$4::jsonb,
                           agent_trace=(coalesce(agent_trace,'{}'::jsonb) - 'evaluation_manifest') || $5::jsonb,
                           investment_memo_markdown=null,updated_at=now()
                           where user_id=$1 and startup_id=$2""",
                        uid, str(previous["legacy_startup_id"]), json.dumps(review_projection),
                        json.dumps(partner_projection), json.dumps(trace_projection),
                    )
                await self._outbox(
                    conn, user_id=uid, aggregate_id=evaluation_id,
                    event_type="evaluation.completed",
                    payload={
                        "evaluation_id": evaluation_id,
                        "recommendation_id": recommendation_id,
                        "opportunity_id": opportunity_id,
                        "recommended_state": recommendation.state.value,
                        "legacy_startup_id": (
                            str(previous["legacy_startup_id"])
                            if previous.get("legacy_startup_id")
                            else None
                        ),
                        "compatibility_reason": (
                            recommendation.change_explanation
                            or "canonical evaluation completed"
                        ),
                    },
                )
                if self.authority_service is not None and hasattr(getattr(self.authority_service, "repository", None), "transition_workflow_on_connection"):
                    await self.authority_service.repository.transition_workflow_on_connection(
                        conn,
                        user_id=uid, opportunity_id=opportunity_id,
                        expected_version=int(previous.get("workflow_version") or 0),
                        target_state="ruling_pending", transition_id=uuid4(),
                    )
                return {
                    "evaluation_id": evaluation_id,
                    "recommendation_id": recommendation_id,
                    "opportunity_id": opportunity_id,
                    "evidence_snapshot_hash": digest,
                    "evidence_materiality_digest": content_digest,
                    "judgment_audit": judgment_audit or {},
                    "criteria": [item.model_dump(mode="json") for item in result.criteria],
                    "recommendation": recommendation.model_dump(mode="json"),
                    "policy": policy.model_dump(mode="json"),
                    "provenance": evaluation_provenance(
                        user_id=uid,
                        evaluation={
                            "user_id": uid, "evaluation_id": evaluation_id,
                            "opportunity_id": opportunity_id, "evidence_snapshot_hash": digest,
                            "claim_snapshot": snapshot, "model_manifest": recorded_model_manifest,
                            "judgment_audit": judgment_audit or {},
                            "thesis_version_id": thesis_version_id,
                            **policy.model_dump(mode="json"),
                        },
                        criteria=[item.model_dump(mode="json") for item in result.criteria],
                        recommendation=recommendation.model_dump(mode="json"),
                    ),
                }

    async def get_current(self, *, user_id: str, opportunity_id: str) -> Optional[Dict[str, Any]]:
        uid = require_user_id(user_id, context="EvaluationRepository.get_current")
        async with self.pool.acquire() as conn:
            evaluation = await conn.fetchrow(
                """
                select e.* from public.opportunities o
                join public.evaluation_runs e on e.user_id=o.user_id and e.evaluation_id=o.current_evaluation_id
                where o.user_id=$1 and o.opportunity_id=$2
                """,
                uid, opportunity_id,
            )
            if evaluation is None:
                return None
            criteria = await conn.fetch(
                "select * from public.criterion_assessments where user_id=$1 and evaluation_id=$2 order by criterion",
                uid, str(evaluation["evaluation_id"]),
            )
            recommendation = await conn.fetchrow(
                "select * from public.recommendations where user_id=$1 and evaluation_id=$2",
                uid, str(evaluation["evaluation_id"]),
            )
        evaluation_payload = dict(evaluation)
        for key, default in (
            ("claim_snapshot", []),
            ("model_manifest", {}),
            ("prompt_manifest", {}),
            ("judgment_audit", {}),
        ):
            evaluation_payload[key] = _json(evaluation_payload.get(key), default)

        criteria_payload = []
        for row in criteria:
            payload = dict(row)
            for key, default in (
                ("supporting_claim_ids", []),
                ("contradicting_claim_ids", []),
                ("missing_evidence", []),
                ("quality_flags", []),
                ("deterministic_adjustments", {}),
            ):
                payload[key] = _json(payload.get(key), default)
            criteria_payload.append(payload)

        recommendation_payload = dict(recommendation) if recommendation else None
        if recommendation_payload is not None:
            for key in (
                "decision_drivers",
                "principal_risks",
                "mandate_conflicts",
                "missing_information",
                "change_conditions",
            ):
                recommendation_payload[key] = _json(
                    recommendation_payload.get(key), []
                )
        return {
            "evaluation": evaluation_payload,
            "criteria": criteria_payload,
            "recommendation": recommendation_payload,
            "provenance": evaluation_provenance(
                user_id=uid, evaluation=evaluation_payload,
                criteria=criteria_payload, recommendation=recommendation_payload,
            ),
        }

    async def record_failed_refresh(
        self,
        *,
        user_id: str,
        opportunity_id: str,
        actor_id: str,
        trigger_type: str,
        failure_code: str,
        policy: EvaluationPolicy,
    ) -> str:
        """Append a failed attempt without replacing current successful pointers."""
        uid = require_user_id(
            user_id, context="EvaluationRepository.record_failed_refresh"
        )
        evaluation_id = str(uuid4())
        safe_code = str(failure_code or "evaluation_failed").strip()[:100]
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                opportunity = await conn.fetchrow(
                    """
                    select current_evaluation_id from public.opportunities
                    where user_id=$1 and opportunity_id=$2 for update
                    """,
                    uid, opportunity_id,
                )
                if opportunity is None:
                    raise LookupError("Opportunity not found for tenant")
                await conn.execute(
                    """
                    insert into public.evaluation_runs (
                      evaluation_id,user_id,opportunity_id,trigger_type,actor_id,
                      evidence_snapshot_hash,evidence_materiality_digest,
                      claim_snapshot,policy_version_id,
                      policy_hash,rubric_version,partner_rules_version,
                      partner_rules_hash,status,failure_code,supersedes_evaluation_id,
                      started_at,completed_at,created_at
                    ) values ($1,$2,$3,$4,$5,'unavailable','unavailable','[]'::jsonb,$6,$7,$8,$9,$10,'failed',$11,$12,now(),now(),now())
                    """,
                    evaluation_id, uid, opportunity_id, trigger_type, actor_id,
                    policy.policy_version_id, policy.policy_hash, policy.rubric_version,
                    policy.partner_rules_version, policy.partner_rules_hash,
                    safe_code, opportunity.get("current_evaluation_id"),
                )
                await self._outbox(
                    conn, user_id=uid, aggregate_id=evaluation_id,
                    event_type="evaluation.failed",
                    payload={
                        "evaluation_id": evaluation_id,
                        "opportunity_id": opportunity_id,
                        "failure_code": safe_code,
                        "prior_result_preserved": True,
                    },
                )
        return evaluation_id
