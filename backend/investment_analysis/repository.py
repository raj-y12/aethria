"""Live analysis boundary over existing immutable evaluation persistence.

Reads a tenant snapshot, releases the connection before model calls, then uses
the publication transaction to verify the same snapshot and persist the
completed review/validation/Partner decision atomically. No second score engine
runs on this path.
"""
from __future__ import annotations
import asyncio
import os
import json
from collections.abc import Callable
from datetime import datetime
from uuid import uuid4
from typing import Any, Dict, Optional

from batch1.context import get_state, set_state, reset_state
from batch1.repository import Batch1Repository
from evaluation_v2.evidence_projection import enriched_claim_evidence_sql
from evaluation_v2.models import EvaluationPolicy
from evaluation_v2.provenance import PipelineBinding, evaluation_provenance
from utils.timeutil import utcnow
from evaluation_v2.service import snapshot_claims, materiality_digest, evaluate_claim_score_eligibility, explain_recommendation_change
from evidence.repository import EvidenceRepository
from evaluation_v2.prerequisites import load_evaluation_prerequisites
from fund_intelligence.repository import FundIntelligenceRepository
from portfolio.cost_control import CostController
from portfolio.repository import PortfolioRepository
from decisions.repository import DecisionRepository
from settings_repository import SettingsRepository
from utils.settings_loader import DEFAULT_SETTINGS
from core.policy_resolver import get_evaluation_rubric
from pipeline_contracts.models import Lineage, Identity, ReviewerOutput
from tenant_context import require_user_id
from .model_gateway import ModelGateway, AnalysisBlocked
from .service import analyze
from .evidence import prepare_factual_evidence
from .models import AnalysisResult
from .validation import validated_rationale
from .dependencies import AnalysisDependencyStatus, DependencyState, inspect_analysis_dependencies

# Completion-token budget for the canonical analysis model gateway.
DEFAULT_MAX_COMPLETION_TOKENS = 16384


def _json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


def _validated_recommendation_drivers(drivers: list[str], judgment_audit: dict) -> list[str]:
    analysis = judgment_audit.get("investment_analysis") or {}
    assessments = (analysis.get("validation") or {}).get("assessments") or []
    return validated_rationale(drivers, assessments)


class EvaluationLifecycleError(RuntimeError):
    """The opportunity lifecycle does not currently permit evaluation."""


class InvestmentAnalysisRepository:
    def __init__(self, pool: Any, *, generate=None, prerequisites_loader=None, cost_controller=None,
                 evidence_preparer=prepare_factual_evidence, clock: Callable[[], datetime] = utcnow,
                 authority_service=None):
        self.pool = pool
        self._clock = clock
        self.authority_service = authority_service
        self.generate = generate
        self.cost_controller = cost_controller
        self.prerequisites_loader = prerequisites_loader
        self.evidence_preparer = evidence_preparer

    async def _snapshot(self, conn, uid, opportunity_id):
        claims = [dict(row) for row in await conn.fetch(
            """select c.* from public.claims c join public.opportunities o
               on o.user_id=c.user_id and o.opportunity_id=c.opportunity_id and o.company_id=c.company_id
               where c.user_id=$1 and c.opportunity_id=$2 and c.status in ('current','contradicted') order by c.claim_id""", uid, opportunity_id)]
        for claim in claims:
            claim["normalized_value"] = _json(claim.get("normalized_value"), {})
        links = [dict(row) for row in await conn.fetch(enriched_claim_evidence_sql(), uid, opportunity_id)]
        analysis_at = self._clock()
        snapshot, digest = snapshot_claims(claims, links, evaluation_at=analysis_at)
        return snapshot, digest, analysis_at

    async def _prerequisites(self, uid):
        prerequisites = (await self.prerequisites_loader(uid) if self.prerequisites_loader is not None else
                         await load_evaluation_prerequisites(user_id=uid, fund_intelligence_repository=FundIntelligenceRepository(self.pool)))
        prerequisites.require_tenant(uid, context="investment_analysis")
        return prerequisites

    async def inspect_dependencies(self, *, user_id: str, opportunity_id: str, record: dict):
        uid = require_user_id(user_id, context="InvestmentAnalysisRepository.inspect_dependencies")
        evaluation = record.get("evaluation") or {}
        raw = (evaluation.get("judgment_audit") or {}).get("investment_analysis")
        if not raw:
            return AnalysisDependencyStatus(state=DependencyState.UNKNOWN,
                message="Historical evaluation; refresh to produce a current investment review.").model_dump(mode="json")
        analysis = AnalysisResult.model_validate(raw)
        if analysis.reviewer.lineage.user_id != uid or analysis.reviewer.lineage.opportunity_id != opportunity_id:
            raise ValueError("analysis tenant/opportunity mismatch")
        prerequisites = await self._prerequisites(uid)
        async with self.pool.acquire() as conn:
            async with conn.transaction(isolation="repeatable_read"):
                snapshot, _, clock = await self._snapshot(conn, uid, opportunity_id)
                identity_row = await conn.fetchrow("""select c.canonical_name,c.canonical_domain,s.scout_info->>'name' as observed_name
                    from opportunities o join companies c on c.user_id=o.user_id and c.company_id=o.company_id
                    left join startups s on s.user_id=o.user_id and s.startup_id=o.legacy_startup_id::text
                    where o.user_id=$1 and o.opportunity_id=$2""", uid, opportunity_id)
        if identity_row:
            from investment_analysis.grounding import grounding_company_name
            current_name = grounding_company_name(identity_row["canonical_name"], identity_row["canonical_domain"], identity_row["observed_name"])
            if analysis.reviewer.identity.name != current_name:
                return AnalysisDependencyStatus(state=DependencyState.STALE, reasons=["identity_context_changed"],
                    message="The company identity used for this review is incomplete. Refresh the full review before relying on its historical conclusions.").model_dump(mode="json")
        return inspect_analysis_dependencies(user_id=uid, opportunity_id=opportunity_id,
            analysis=analysis, snapshot=snapshot, prior_snapshot=evaluation.get("claim_snapshot") or [],
            policy=prerequisites.policy, thesis_version_id=prerequisites.thesis_version_id,
            evaluation_at=clock).model_dump(mode="json")

    async def evaluate(self, *, user_id: str, opportunity_id: str, actor_id: str,
                       trigger_type: str, policy, thesis_version_id=None,
                       pipeline_binding=None, review_mode="full", **kwargs):
        uid = require_user_id(user_id, context="InvestmentAnalysisRepository.evaluate")
        if review_mode not in {"full", "partner_only"}:
            raise ValueError("unknown investment analysis mode")
        if pipeline_binding is not None and pipeline_binding.user_id != uid:
            raise ValueError("pipeline binding tenant mismatch")
        if {"prepared_analysis", "analysis_at", "expected_evaluation_id"}.intersection(kwargs):
            raise ValueError("live callers cannot supply precomputed authority")
        await self._require_write_path(user_id=uid, operation="investment analysis")
        if self.generate is None and not os.getenv("OPENAI_API_KEY", ""):
            raise AnalysisBlocked("analysis_model_unconfigured", "Investment analysis requires a configured model provider.")
        async with self.pool.acquire() as conn:
            async with conn.transaction(isolation="repeatable_read"):
                company = await conn.fetchrow(
                    """select o.company_id, c.canonical_name, c.canonical_domain, o.current_evaluation_id,
                              o.service_level,o.decision_state,o.workflow_state,s.scout_info->>'name' as observed_name
                       from public.opportunities o join public.companies c
                       on c.company_id=o.company_id and c.user_id=o.user_id
                       left join public.startups s on s.user_id=o.user_id and s.startup_id=o.legacy_startup_id::text
                       where o.user_id=$1 and o.opportunity_id=$2""", uid, opportunity_id)
                if company is None:
                    raise LookupError("Opportunity not found for tenant")
                if int(company.get("service_level") or 0) <= 0 or company.get("decision_state") in {"archived", "invested"} or company.get("workflow_state") in {"completed", "monitoring"}:
                    raise EvaluationLifecycleError("Opportunity lifecycle does not allow investment analysis")
                snapshot, digest, analysis_at = await self._snapshot(conn, uid, opportunity_id)
        from investment_analysis.grounding import grounding_company_name
        company = dict(company)
        company["canonical_name"] = grounding_company_name(company["canonical_name"],
            company.get("canonical_domain"), company.get("observed_name"))
        # Context comes from explicit tenant repositories, never from Scout's
        # investment thesis or compatibility recommendation.
        prerequisites = await self._prerequisites(uid)
        if prerequisites.policy != policy or prerequisites.thesis_version_id != thesis_version_id:
            raise AnalysisBlocked("analysis_dependencies_changed", "Published policy or fund thesis changed; retry with current prerequisites.")
        preparation = {"status": "partner_only_reuse", "claims_created": 0}
        if review_mode == "full":
            try:
                preparation = await self.evidence_preparer(
                    user_id=uid, company_id=str(company["company_id"]), opportunity_id=opportunity_id,
                    company_name=company["canonical_name"], company_website=company.get("canonical_domain"),
                    snapshot=snapshot, policy=policy, evaluation_at=analysis_at,
                    evidence_repository=EvidenceRepository(self.pool),
                )
            except Exception as exc:
                raise AnalysisBlocked("evidence_preparation_failed", "Factual evidence preparation did not complete; retry when the evidence provider is available.") from exc
            if preparation["claims_created"]:
                async with self.pool.acquire() as conn:
                    async with conn.transaction(isolation="repeatable_read"):
                        snapshot, digest, analysis_at = await self._snapshot(conn, uid, opportunity_id)
        settings = await SettingsRepository(self.pool).get(uid) or DEFAULT_SETTINGS
        prior = await self.get_current(user_id=uid, opportunity_id=opportunity_id)
        reused_review = None
        prior_snapshot = None
        if review_mode == "partner_only":
            previous_evaluation = (prior or {}).get("evaluation") or {}
            previous_analysis = (previous_evaluation.get("judgment_audit") or {}).get("investment_analysis") or {}
            if not previous_analysis.get("reviewer"):
                raise AnalysisBlocked("analysis_dependencies_changed", "A completed investment review is required before Partner-only refresh.")
            reused_review = ReviewerOutput.model_validate(previous_analysis["reviewer"])
            prior_snapshot = previous_evaluation.get("claim_snapshot")
        context = {
            "evidence_preparation": preparation,
            "thesis_version_id": thesis_version_id,
            "fund_thesis": prerequisites.thesis_context,
            "fund_configuration": prerequisites.fund_config,
            "prior_decision": (prior or {}).get("recommendation"),
        }
        prior_identity = (((prior or {}).get("evaluation", {}).get("judgment_audit") or {})
                          .get("investment_analysis", {}).get("reviewer", {}).get("identity", {}))
        if prior_identity and prior_identity.get("name") != company["canonical_name"]:
            context["prior_decision"] = None
        positions = await PortfolioRepository(self.pool).list_positions(user_id=uid, limit=50)
        rulings = await DecisionRepository(self.pool).list_rulings(user_id=uid, opportunity_id=opportunity_id, limit=20)
        context["portfolio"] = [
            {key: position.get(key) for key in ("position_id", "company_id", "canonical_name", "entry_rationale", "investor_confidence", "entered_at")}
            for position in positions
        ]
        context["portfolio_scope"] = "Up to 50 most recent active positions; do not assume this is the entire fund."
        context["analyst_rulings"] = [ruling.model_dump(mode="json") for ruling in rulings]
        context["analyst_context_rule"] = "Prior rulings and override notes are attributed analyst judgments, not factual corrections or new evidence."
        rubric = get_evaluation_rubric()
        context["analytical_rubric"] = {
            "version": rubric.get("version"),
            "scoring_overview": rubric.get("scoring_overview"),
            "score_bands": rubric.get("score_bands"),
            "dimensions": [
                {key: value for key, value in dimension.items() if key in {"id", "name", "question", "definition"}}
                for dimension in rubric.get("dimensions", [])
            ],
            "fund_rubric": prerequisites.fund_config.get("rubric"),
        }
        reviewer_model = os.getenv("REVIEWER_MODEL", "gpt-5-nano")
        partner_model = os.getenv("PARTNER_MODEL", "gpt-5-nano")
        lineage = Lineage(user_id=uid, company_id=str(company["company_id"]), opportunity_id=opportunity_id,
                          pipeline_run_id=pipeline_binding.pipeline_run_id if pipeline_binding else None,
                          scout_run_id=pipeline_binding.scout_run_id if pipeline_binding else None,
                          evidence_snapshot_hash=digest)
        gateway = None
        state_token = None
        budget_repository = None
        try:
            generate = self.generate
            if generate is None:
                state = get_state()
                if state is not None and state.user_id != uid:
                    raise ValueError("analysis budget state tenant mismatch")
                if state is None:
                    budget_repository = Batch1Repository(self.pool)
                    state = await budget_repository.load_state(uid)
                    state_token = set_state(state)
                controller = self.cost_controller or CostController(user_id=uid, settings=settings,
                                            enforce_limits=bool((settings.get("cost_budget") or {}).get("enabled", False)))
                gateway = ModelGateway(user_id=uid, api_key=os.getenv("OPENAI_API_KEY", ""),
                                       reviewer_model=reviewer_model, partner_model=partner_model,
                                       cost_controller=controller, max_completion_tokens=DEFAULT_MAX_COMPLETION_TOKENS)
                generate = gateway
            async def research(questions):
                nonlocal snapshot, digest, analysis_at
                try:
                    await self.evidence_preparer(
                        user_id=uid, company_id=str(company["company_id"]), opportunity_id=opportunity_id,
                        company_name=company["canonical_name"], company_website=company.get("canonical_domain"),
                        snapshot=snapshot, policy=policy, evaluation_at=analysis_at, questions=questions,
                        evidence_repository=EvidenceRepository(self.pool),
                    )
                except Exception as exc:
                    raise AnalysisBlocked("evidence_preparation_failed", "Targeted factual research did not complete; retry when the evidence provider is available.") from exc
                async with self.pool.acquire() as conn:
                    async with conn.transaction(isolation="repeatable_read"):
                        snapshot, digest, analysis_at = await self._snapshot(conn, uid, opportunity_id)
                return snapshot, analysis_at

            result = await analyze(user_id=uid, lineage=lineage, identity=Identity(name=company["canonical_name"], website=company.get("canonical_domain")),
                                   snapshot=snapshot, policy=policy, context=context, generate=generate,
                                   evaluation_at=analysis_at, reviewer_model=reviewer_model, partner_model=partner_model,
                                   prior_review=reused_review, prior_snapshot=prior_snapshot,
                                   research=research if review_mode == "full" else None)
            current_prerequisites = await self._prerequisites(uid)
            if (current_prerequisites.policy != policy
                    or current_prerequisites.thesis_version_id != thesis_version_id
                    or current_prerequisites.fund_config != prerequisites.fund_config
                    or current_prerequisites.thesis_context != prerequisites.thesis_context):
                raise AnalysisBlocked(
                    "analysis_dependencies_changed",
                    "Published policy or fund context changed during analysis; retry with current prerequisites.",
                )
            return await self._publish(user_id=uid, opportunity_id=opportunity_id, actor_id=actor_id,
                                          trigger_type=trigger_type, policy=policy, thesis_version_id=thesis_version_id,
                                          pipeline_binding=pipeline_binding, prepared_analysis=result,
                                          analysis_at=analysis_at,
                                          expected_evaluation_id=str(company["current_evaluation_id"]) if company.get("current_evaluation_id") else None,
                                          **kwargs)
        finally:
            if gateway is not None:
                await asyncio.to_thread(gateway.close)
            if budget_repository is not None:
                try:
                    await budget_repository.persist_state(state)
                finally:
                    reset_state(state_token)

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

    async def _publish(
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
        prepared_analysis: AnalysisResult,
        analysis_at: datetime,
        expected_evaluation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        uid = require_user_id(user_id, context="InvestmentAnalysisRepository.evaluate")
        if pipeline_binding is not None and pipeline_binding.user_id != uid:
            raise ValueError("pipeline binding tenant mismatch")
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
                evaluation_at = analysis_at
                snapshot, digest = snapshot_claims(
                    claims, links, evaluation_at=evaluation_at
                )
                content_digest = materiality_digest(snapshot)
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
                # Lineage is separate from the frozen decision snapshot: adding
                # observability must not alter snapshot hashes or score inputs.
                source_trace = _json(previous.get("source_agent_trace"), {})
                if previous.get("legacy_startup_id"):
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
                    "pipeline_run_id": recorded_binding.pipeline_run_id or prepared_analysis.reviewer.lineage.pipeline_run_id,
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
                evaluation_id = prepared_analysis.reviewer.lineage.evaluation_run_id
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
                if previous.get("legacy_startup_id"):
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
        uid = require_user_id(user_id, context="InvestmentAnalysisRepository.get_current")
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
            recommendation_payload["decision_drivers"] = _validated_recommendation_drivers(
                recommendation_payload["decision_drivers"], evaluation_payload["judgment_audit"])
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
            user_id, context="InvestmentAnalysisRepository.record_failed_refresh"
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
