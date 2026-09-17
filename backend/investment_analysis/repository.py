"""Live analysis boundary over existing immutable evaluation persistence.

Reads a tenant snapshot, releases the connection before model calls, then uses
EvaluationRepository's transaction to verify the same snapshot and persist the
completed review/validation/Partner decision atomically. No second score engine
runs on this path.
"""
from __future__ import annotations
import asyncio
import os
from typing import Any

from batch1.context import get_state, set_state, reset_state
from batch1.repository import Batch1Repository
from evaluation_v2.repository import EvaluationRepository, EvaluationLifecycleError, _json
from evaluation_v2.evidence_projection import enriched_claim_evidence_sql
from evaluation_v2.service import snapshot_claims
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
from semantic_evaluation.repository import SemanticEvaluationRepository
from tenant_context import require_user_id
from .model_gateway import ModelGateway, AnalysisBlocked
from .service import analyze
from .evidence import prepare_factual_evidence
from .models import AnalysisResult
from .dependencies import AnalysisDependencyStatus, DependencyState, inspect_analysis_dependencies

# Default completion-token budget for this repository's own ModelGateway
# construction. Deliberately independent of reviewer/base.py's identically-named
# constant: that one feeds the legacy Reviewer's own retry-budget doubling
# (REVIEWER_MAX_COMPLETION_TOKENS), which this path does not use.
DEFAULT_MAX_COMPLETION_TOKENS = 16384


class InvestmentAnalysisRepository(EvaluationRepository):
    def __init__(self, pool: Any, *, generate=None, prerequisites_loader=None, cost_controller=None,
                 evidence_preparer=prepare_factual_evidence, **kwargs):
        super().__init__(pool, **kwargs)
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
                                   research=research if review_mode == "full" else None,
                                   semantic_evaluation_repository=SemanticEvaluationRepository(self.pool))
            current_prerequisites = await self._prerequisites(uid)
            if (current_prerequisites.policy != policy
                    or current_prerequisites.thesis_version_id != thesis_version_id
                    or current_prerequisites.fund_config != prerequisites.fund_config
                    or current_prerequisites.thesis_context != prerequisites.thesis_context):
                raise AnalysisBlocked(
                    "analysis_dependencies_changed",
                    "Published policy or fund context changed during analysis; retry with current prerequisites.",
                )
            return await super().evaluate(user_id=uid, opportunity_id=opportunity_id, actor_id=actor_id,
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
