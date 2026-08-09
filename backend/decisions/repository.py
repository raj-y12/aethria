"""Transactional append-only rulings and approval-gated workflow actions."""

from __future__ import annotations

import json
import hashlib
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from decisions.models import (
    HumanRulingInput,
    HumanRulingRecord,
    WorkflowActionRecord,
    WorkflowActionStatus,
    WorkflowActionType,
)
from decisions.service import (
    build_workflow_draft,
    classify_override,
    ruling_to_opportunity_state,
)
from decisions.interpretation import build_ruling_interpretation_draft
from tenant_context import require_user_id
from utils.db_rows import db_row


def _json(value: Any, default: Any):
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


class DecisionRepository:
    def __init__(self, pool: Any, *, authority_service: Any = None, portfolio_repository: Any = None):
        self.pool = pool
        self.authority_service = authority_service
        self.portfolio_repository = portfolio_repository

    async def _require_write_path(self, *, user_id: str, operation: str) -> None:
        if self.authority_service is not None:
            await self.authority_service.require_write_path(
                user_id=user_id, operation=operation
            )

    @staticmethod
    async def _outbox(conn, *, user_id, aggregate_type, aggregate_id, event_type, payload):
        await conn.execute(
            """
            insert into public.domain_outbox (
              event_id,user_id,aggregate_type,aggregate_id,event_type,event_version,
              payload,publication_attempts,next_attempt_at,created_at
            ) values ($1,$2,$3,$4,$5,1,$6::jsonb,0,now(),now())
            """,
            str(uuid4()), user_id, aggregate_type, aggregate_id, event_type, json.dumps(payload),
        )

    async def _ruling_interpretation_context(
        self, conn: Any, *, user_id: str, recommendation_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        if not recommendation_id:
            return None
        row = await conn.fetchrow(
            """
            select r.recommendation_id, r.recommended_state,
                   e.evaluation_id, e.claim_snapshot
            from public.recommendations r
            left join public.evaluation_runs e
              on e.user_id=r.user_id and e.evaluation_id=r.evaluation_id
            where r.user_id=$1 and r.recommendation_id=$2
            """,
            user_id,
            recommendation_id,
        )
        if row is None:
            return None
        context = dict(row)
        context["claim_snapshot"] = _json(context.get("claim_snapshot"), [])
        return context

    async def _create_ruling_interpretation(
        self,
        conn: Any,
        *,
        user_id: str,
        ruling_id: str,
        opportunity_id: str,
        recommendation_id: Optional[str],
        rationale: str,
        decision: str,
        investor_confidence: float,
        risk_acknowledgement: Optional[str],
        mandate_exception: Optional[str],
        override_type: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        context = await self._ruling_interpretation_context(
            conn, user_id=user_id, recommendation_id=recommendation_id
        )
        if context is None:
            return None
        draft = build_ruling_interpretation_draft(
            rationale=rationale,
            decision=decision,
            investor_confidence=investor_confidence,
            risk_acknowledgement=risk_acknowledgement,
            mandate_exception=mandate_exception,
            override_type=override_type,
            context=context,
        )
        if draft is None:
            return None
        interpretation_id = str(uuid4())
        payload = {
            **draft,
            "interpretation_id": interpretation_id,
            "ruling_id": ruling_id,
            "opportunity_id": opportunity_id,
            "recommendation_id": recommendation_id,
            "evaluation_id": context.get("evaluation_id"),
            "version": 1,
            "rationale_sha256": hashlib.sha256(rationale.encode()).hexdigest(),
        }
        await conn.execute(
            """
            insert into public.ruling_interpretations (
              interpretation_id,user_id,ruling_id,opportunity_id,recommendation_id,
              evaluation_id,version,source,status,rationale_sha256,extraction_confidence,
              positive_factors,negative_factors,accepted_risks,decisive_factors,
              overridden_criteria,strategic_exception,agreement_with_aethria,human_confidence,
              evidence_influence,provenance,created_at
            ) values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb,$13::jsonb,
              $14::jsonb,$15::jsonb,$16::jsonb,$17::jsonb,$18,$19,$20::jsonb,$21::jsonb,now())
            """,
            interpretation_id, user_id, ruling_id, opportunity_id, recommendation_id,
            context.get("evaluation_id"), 1, draft["source"], draft["status"],
            payload["rationale_sha256"], draft["extraction_confidence"],
            json.dumps(draft["positive_factors"]), json.dumps(draft["negative_factors"]),
            json.dumps(draft["accepted_risks"]), json.dumps(draft["decisive_factors"]),
            json.dumps(draft["overridden_criteria"]), json.dumps(draft["strategic_exception"]),
            draft["agreement_with_aethria"], draft["human_confidence"],
            json.dumps(draft["evidence_influence"]), json.dumps(draft["provenance"]),
        )
        return payload

    async def create_ruling(self, ruling: HumanRulingInput, *, actor_id: str) -> Dict[str, Any]:
        uid = require_user_id(ruling.user_id, context="DecisionRepository.create_ruling")
        await self._require_write_path(user_id=uid, operation="human ruling creation")
        actor = str(actor_id or "").strip()
        if not actor:
            raise ValueError("actor_id is required")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                if self.authority_service is not None and hasattr(self.authority_service, "assert_write_path_on_connection"):
                    await self.authority_service.assert_write_path_on_connection(conn, user_id=uid, operation="human ruling creation")
                opportunity = await conn.fetchrow(
                    """
                    select o.current_ruling_id,o.current_recommendation_id,o.legacy_startup_id,o.company_id,
                           o.workflow_version,o.decision_state,r.missing_information,
                           r.recommended_state
                    from public.opportunities o
                    left join public.recommendations r
                      on r.user_id=o.user_id and r.recommendation_id=coalesce($3::uuid,o.current_recommendation_id)
                    where o.user_id=$1 and o.opportunity_id=$2
                      and ($3::uuid is null or r.opportunity_id=o.opportunity_id)
                    for update of o
                    """,
                    uid, ruling.opportunity_id, ruling.recommendation_id,
                )
                if opportunity is None:
                    raise LookupError("Opportunity or recommendation not found for tenant")
                recommendation_id = ruling.recommendation_id or opportunity.get("current_recommendation_id")
                ruling_id = str(uuid4())
                row = await conn.fetchrow(
                    """
                    insert into public.human_rulings (
                      ruling_id,user_id,opportunity_id,recommendation_id,decision,
                      rationale,risk_acknowledgement,mandate_exception,
                      investor_confidence,actor_id,prior_ruling_id,created_at
                    ) values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,now()) returning *
                    """,
                    ruling_id, uid, ruling.opportunity_id, recommendation_id,
                    ruling.decision.value, ruling.rationale, ruling.risk_acknowledgement,
                    ruling.mandate_exception, ruling.investor_confidence, actor,
                    opportunity.get("current_ruling_id"),
                )
                override = classify_override(
                    recommendation=opportunity.get("recommended_state"),
                    ruling=ruling.decision,
                    requested=ruling.override_type,
                )
                if override is not None:
                    await conn.execute(
                        """
                        insert into public.override_signals (
                          override_signal_id,user_id,opportunity_id,ruling_id,
                          recommendation_id,recommendation_state,ruling_decision,
                          override_type,note,created_at
                        ) values ($1,$2,$3,$4,$5,$6,$7,$8,$9,now())
                        """,
                        str(uuid4()), uid, ruling.opportunity_id, ruling_id,
                        recommendation_id, opportunity.get("recommended_state"),
                        ruling.decision.value, override.value, ruling.override_note,
                    )
                interpretation = await self._create_ruling_interpretation(
                    conn,
                    user_id=uid,
                    ruling_id=ruling_id,
                    opportunity_id=ruling.opportunity_id,
                    recommendation_id=recommendation_id,
                    rationale=ruling.rationale,
                    decision=ruling.decision.value,
                    investor_confidence=ruling.investor_confidence,
                    risk_acknowledgement=ruling.risk_acknowledgement,
                    mandate_exception=ruling.mandate_exception,
                    override_type=override.value if override else None,
                )
                await conn.execute(
                    """
                    update public.opportunities
                    set current_ruling_id=$3,decision_state=$4,updated_at=now()
                    where opportunity_id=$1 and user_id=$2
                    """,
                    ruling.opportunity_id, uid, ruling_id,
                    ruling_to_opportunity_state(ruling.decision),
                )
                if ruling.decision.value == "pass":
                    await conn.execute(
                        """
                        update public.workflow_actions
                        set status='cancelled', updated_at=now()
                        where user_id=$1 and opportunity_id=$2
                          and status in ('draft','pending_approval','approved','running')
                        """,
                        uid, ruling.opportunity_id,
                    )
                if ruling.decision.value == "invest":
                    if self.portfolio_repository is None:
                        raise RuntimeError("Canonical portfolio repository is required for INVEST rulings")
                    await self.portfolio_repository.create_position_on_connection(
                        conn,
                        user_id=uid,
                        opportunity_id=ruling.opportunity_id,
                        company_id=str(opportunity["company_id"]),
                        ruling_id=ruling_id,
                        rationale=ruling.rationale,
                        investor_confidence=ruling.investor_confidence,
                    )
                    await self._outbox(
                        conn, user_id=uid, aggregate_type="portfolio_position",
                        aggregate_id=ruling.opportunity_id,
                        event_type="portfolio_position.created",
                        payload={
                            "opportunity_id": ruling.opportunity_id,
                            "ruling_id": ruling_id,
                            "decision": "invest",
                            "compatibility_reason": "explicit human INVEST ruling",
                        },
                    )
                if ruling.decision.value == "monitor":
                    await self._insert_action(
                        conn, user_id=uid, opportunity_id=ruling.opportunity_id,
                        action_type=WorkflowActionType.SCHEDULE_MONITOR_REVIEW,
                        trigger_type="human_ruling", trigger_id=ruling_id,
                        missing_evidence=[], due_at=None,
                    )
                if ruling.decision.value == "advance":
                    missing_evidence = _json(opportunity.get("missing_information"), [])
                    await self._insert_action(
                        conn, user_id=uid, opportunity_id=ruling.opportunity_id,
                        action_type=WorkflowActionType.PREPARE_DILIGENCE_QUESTIONS,
                        trigger_type="human_ruling", trigger_id=ruling_id,
                        missing_evidence=missing_evidence if isinstance(missing_evidence, list) else [], due_at=None,
                    )
                await self._outbox(
                    conn, user_id=uid, aggregate_type="human_ruling",
                    aggregate_id=ruling_id, event_type="human_ruling.created",
                    payload={
                        "ruling_id": ruling_id,
                        "opportunity_id": ruling.opportunity_id,
                        "decision": ruling.decision.value,
                        "override_type": override.value if override else None,
                        "legacy_startup_id": (
                            str(opportunity["legacy_startup_id"])
                            if opportunity.get("legacy_startup_id")
                            else None
                        ),
                        "rationale": ruling.rationale,
                        "compatibility_reason": ruling.rationale,
                    },
                )
                if self.authority_service is not None and hasattr(getattr(self.authority_service, "repository", None), "transition_workflow_on_connection"):
                    target_state = {
                        "advance": "evidence_active",
                        "monitor": "monitoring",
                        "pass": "completed",
                    }.get(ruling.decision.value, "completed")
                    await self.authority_service.repository.transition_workflow_on_connection(
                        conn,
                        user_id=uid, opportunity_id=ruling.opportunity_id,
                        expected_version=int(opportunity.get("workflow_version") or 0),
                        target_state=target_state,
                        transition_id=uuid4(),
                    )
                payload = dict(row)
                payload["override_type"] = override.value if override else None
                payload["interpretation"] = interpretation
                return payload

    async def create_investment_transition(
        self, *, user_id: str, opportunity_id: str, rationale: str,
        investor_confidence: float, actor_id: str,
    ) -> Dict[str, Any]:
        """Create an idempotent post-diligence INVEST transition and position."""
        uid = require_user_id(user_id, context="DecisionRepository.create_investment_transition")
        await self._require_write_path(user_id=uid, operation="investment transition")
        if self.portfolio_repository is None:
            raise RuntimeError("Canonical portfolio repository is required for investment transitions")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                if self.authority_service is not None and hasattr(self.authority_service, "assert_write_path_on_connection"):
                    await self.authority_service.assert_write_path_on_connection(conn, user_id=uid, operation="investment transition")
                opportunity = await conn.fetchrow(
                    """
                    select current_ruling_id,current_recommendation_id,legacy_startup_id,company_id,decision_state,workflow_version
                    from public.opportunities where user_id=$1 and opportunity_id=$2 for update
                    """, uid, opportunity_id,
                )
                if opportunity is None:
                    raise LookupError("Opportunity not found for tenant")
                if str(opportunity.get("decision_state") or "") != "advance":
                    raise ValueError("Investment transition requires an opportunity previously advanced to diligence")
                existing = await conn.fetchrow(
                    "select * from public.canonical_portfolio_positions where user_id=$1 and opportunity_id=$2",
                    uid, opportunity_id,
                )
                if existing is not None:
                    result = db_row(existing)
                    result.update({"decision": "invest", "idempotent": True})
                    return result
                ruling_id = str(uuid4())
                row = await conn.fetchrow(
                    """
                    insert into public.human_rulings (
                      ruling_id,user_id,opportunity_id,recommendation_id,decision,
                      rationale,investor_confidence,actor_id,prior_ruling_id,ruling_context,created_at
                    ) values ($1,$2,$3,$4,'invest',$5,$6,$7,$8,'investment_transition',now()) returning *
                    """,
                    ruling_id, uid, opportunity_id, opportunity.get("current_recommendation_id"),
                    rationale, investor_confidence, actor_id, opportunity.get("current_ruling_id"),
                )
                interpretation = await self._create_ruling_interpretation(
                    conn,
                    user_id=uid,
                    ruling_id=ruling_id,
                    opportunity_id=opportunity_id,
                    recommendation_id=opportunity.get("current_recommendation_id"),
                    rationale=rationale,
                    decision="invest",
                    investor_confidence=investor_confidence,
                    risk_acknowledgement=None,
                    mandate_exception=None,
                    override_type=None,
                )
                await conn.execute(
                    """update public.opportunities set current_ruling_id=$3,decision_state='invested',updated_at=now()
                    where opportunity_id=$1 and user_id=$2""", opportunity_id, uid, ruling_id,
                )
                position = await self.portfolio_repository.create_position_on_connection(
                    conn, user_id=uid, opportunity_id=opportunity_id,
                    company_id=str(opportunity["company_id"]), ruling_id=ruling_id,
                    rationale=rationale, investor_confidence=investor_confidence,
                )
                await self._outbox(
                    conn, user_id=uid, aggregate_type="human_ruling", aggregate_id=ruling_id,
                    event_type="human_ruling.created",
                    payload={
                        "ruling_id": ruling_id,
                        "opportunity_id": opportunity_id,
                        "decision": "invest",
                        "ruling_context": "investment_transition",
                        "rationale": rationale,
                    },
                )
                await self._outbox(
                    conn, user_id=uid, aggregate_type="portfolio_position", aggregate_id=opportunity_id,
                    event_type="portfolio_position.created",
                    payload={"opportunity_id": opportunity_id, "ruling_id": ruling_id, "decision": "invest"},
                )
                if self.authority_service is not None and hasattr(getattr(self.authority_service, "repository", None), "transition_workflow_on_connection"):
                    await self.authority_service.repository.transition_workflow_on_connection(
                        conn,
                        user_id=uid,
                        opportunity_id=opportunity_id,
                        expected_version=int(opportunity.get("workflow_version") or 0),
                        target_state="completed",
                        transition_id=uuid4(),
                    )
                result = db_row(row)
                result.update({
                    "decision": "invest", "position": position, "idempotent": False,
                    "interpretation": interpretation,
                })
                return result

    async def list_rulings(
        self,
        *,
        user_id: str,
        opportunity_id: str,
        limit: int = 50,
    ) -> list[HumanRulingRecord]:
        uid = require_user_id(user_id, context="DecisionRepository.list_rulings")
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select hr.*, os.override_type, os.note as override_note
                from public.human_rulings hr
                left join public.override_signals os
                  on os.user_id=hr.user_id and os.ruling_id=hr.ruling_id
                where hr.user_id=$1 and hr.opportunity_id=$2
                order by hr.created_at desc limit $3
                """,
                uid,
                opportunity_id,
                max(1, min(int(limit), 100)),
            )
        return [HumanRulingRecord.model_validate(db_row(row)) for row in rows]

    async def correct_ruling_interpretation(
        self,
        *,
        user_id: str,
        ruling_id: str,
        correction: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Append an operator correction without mutating the ruling or prior interpretation."""
        uid = require_user_id(
            user_id, context="DecisionRepository.correct_ruling_interpretation"
        )
        await self._require_write_path(user_id=uid, operation="ruling interpretation correction")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                ruling = await conn.fetchrow(
                    """
                    select hr.ruling_id, hr.opportunity_id, hr.recommendation_id,
                           hr.rationale, r.evaluation_id
                    from public.human_rulings hr
                    left join public.recommendations r
                      on r.user_id=hr.user_id and r.recommendation_id=hr.recommendation_id
                    where hr.user_id=$1 and hr.ruling_id=$2
                    """,
                    uid,
                    ruling_id,
                )
                if ruling is None:
                    raise LookupError("Ruling not found for tenant")
                previous = await conn.fetchrow(
                    """
                    select * from public.ruling_interpretations
                    where user_id=$1 and ruling_id=$2
                    order by version desc limit 1
                    """,
                    uid,
                    ruling_id,
                )
                if previous is None:
                    raise LookupError("Ruling interpretation not found for tenant")
                context = await self._ruling_interpretation_context(
                    conn,
                    user_id=uid,
                    recommendation_id=ruling.get("recommendation_id"),
                )
                claim_ids = set()
                evidence_ids = set()
                if context:
                    for claim in context.get("claim_snapshot") or []:
                        if claim.get("claim_id"):
                            claim_ids.add(str(claim["claim_id"]))
                        evidence_ids.update(
                            str(item) for item in claim.get("supporting_evidence_ids") or []
                        )
                        evidence_ids.update(
                            str(item) for item in claim.get("contradicting_evidence_ids") or []
                        )
                influence = correction.get("evidence_influence") or {
                    "status": "unknown", "references": [], "limitations": []
                }
                for reference in influence.get("references") or []:
                    reference_id = str(reference.get("reference_id"))
                    allowed = claim_ids if reference.get("reference_type") == "claim" else evidence_ids
                    if reference_id not in allowed:
                        raise ValueError("Correction references evidence outside the decision-time snapshot")
                version = int(previous["version"]) + 1
                interpretation_id = str(uuid4())
                payload = {
                    "interpretation_id": interpretation_id,
                    "ruling_id": ruling_id,
                    "opportunity_id": ruling["opportunity_id"],
                    "recommendation_id": ruling.get("recommendation_id"),
                    "evaluation_id": ruling.get("evaluation_id"),
                    "version": version,
                    "source": "operator_correction",
                    "status": "complete",
                    "rationale_sha256": hashlib.sha256(str(ruling["rationale"]).encode()).hexdigest(),
                    "extraction_confidence": 1.0,
                    **correction,
                    "supersedes_interpretation_id": previous["interpretation_id"],
                }
                await conn.execute(
                    """
                    insert into public.ruling_interpretations (
                      interpretation_id,user_id,ruling_id,opportunity_id,recommendation_id,
                      evaluation_id,version,source,status,rationale_sha256,extraction_confidence,
                      positive_factors,negative_factors,accepted_risks,decisive_factors,
                      overridden_criteria,strategic_exception,agreement_with_aethria,human_confidence,
                      evidence_influence,provenance,correction_note,supersedes_interpretation_id,created_at
                    ) values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb,$13::jsonb,
                      $14::jsonb,$15::jsonb,$16::jsonb,$17::jsonb,$18,$19,$20::jsonb,$21::jsonb,
                      $22,$23,now())
                    """,
                    interpretation_id, uid, ruling_id, ruling["opportunity_id"],
                    ruling.get("recommendation_id"), ruling.get("evaluation_id"), version,
                    payload["source"], payload["status"], payload["rationale_sha256"],
                    payload["extraction_confidence"], json.dumps(payload.get("positive_factors", [])),
                    json.dumps(payload.get("negative_factors", [])), json.dumps(payload.get("accepted_risks", [])),
                    json.dumps(payload.get("decisive_factors", [])), json.dumps(payload.get("overridden_criteria", [])),
                    json.dumps(payload.get("strategic_exception")), payload["agreement_with_aethria"],
                    payload.get("human_confidence"), json.dumps(payload["evidence_influence"]),
                    json.dumps(payload.get("provenance", {"source": "operator_correction"})),
                    payload.get("correction_note"), payload["supersedes_interpretation_id"],
                )
                return payload

    async def _insert_action(
        self,
        conn: Any,
        *,
        user_id: str,
        opportunity_id: str,
        action_type: WorkflowActionType,
        trigger_type: str,
        trigger_id: Optional[str],
        missing_evidence: list[str],
        due_at: Optional[datetime],
        external_destination: Optional[str] = None,
        export_context: Optional[Dict[str, Any]] = None,
    ) -> WorkflowActionRecord:
        generated = build_workflow_draft(
            action_type, missing_evidence, export_context=export_context
        )
        requires_approval = bool(generated.get("requires_approval"))
        status = (
            WorkflowActionStatus.PENDING_APPROVAL
            if requires_approval
            else WorkflowActionStatus.COMPLETED
        )
        row = await conn.fetchrow(
            """
            insert into public.workflow_actions (
              workflow_action_id,user_id,opportunity_id,action_type,trigger_type,
              trigger_id,status,generated_content,missing_evidence,requires_approval,
              due_at,completed_at,external_destination,created_at,updated_at
            ) values ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9::jsonb,$10,$11,
              case when $7='completed' then now() else null end,$12,now(),now())
            returning *
            """,
            str(uuid4()), user_id, opportunity_id, action_type.value, trigger_type,
            trigger_id, status.value, json.dumps(generated), json.dumps(missing_evidence),
            requires_approval, due_at, external_destination,
        )
        payload = db_row(row)
        payload["generated_content"] = _json(payload.get("generated_content"), {})
        payload["approved_content"] = _json(payload.get("approved_content"), None)
        payload["missing_evidence"] = _json(payload.get("missing_evidence"), [])
        return WorkflowActionRecord.model_validate(payload)

    async def _load_export_context(
        self, conn: Any, *, user_id: str, opportunity_id: str
    ) -> Dict[str, Any]:
        """Gather the canonical facts a CRM row needs. Read-only."""
        company = await conn.fetchrow(
            """
            select c.canonical_name, c.canonical_domain, o.current_ruling_id
            from public.opportunities o
            join public.companies c on c.user_id=o.user_id and c.company_id=o.company_id
            where o.user_id=$1 and o.opportunity_id=$2
            """,
            user_id, opportunity_id,
        )
        position = await conn.fetchrow(
            "select entered_at, ruling_id from public.canonical_portfolio_positions where user_id=$1 and opportunity_id=$2",
            user_id, opportunity_id,
        )
        # Precedence: the ruling the position was actually created from, else
        # the opportunity's current ruling (covers exporting a non-holding,
        # e.g. a PASS), else no ruling at all.
        ruling_id = (
            position["ruling_id"] if position and position.get("ruling_id")
            else (company.get("current_ruling_id") if company else None)
        )
        ruling = None
        if ruling_id:
            ruling = await conn.fetchrow(
                """
                select hr.decision, hr.rationale, hr.investor_confidence, hr.created_at, os.override_type
                from public.human_rulings hr
                left join public.override_signals os
                  on os.user_id=hr.user_id and os.ruling_id=hr.ruling_id
                where hr.user_id=$1 and hr.ruling_id=$2
                """,
                user_id, ruling_id,
            )
        outcomes = await conn.fetch(
            """
            select outcome_type, valence, summary, observed_at
            from public.outcome_observations
            where user_id=$1 and opportunity_id=$2
            order by observed_at
            """,
            user_id, opportunity_id,
        )
        return {
            "company": dict(company) if company else {},
            "ruling": dict(ruling) if ruling else {},
            "position": dict(position) if position else None,
            "outcomes": [dict(row) for row in outcomes],
        }

    async def create_action(
        self,
        *,
        user_id: str,
        opportunity_id: str,
        action_type: WorkflowActionType | str,
        trigger_type: str = "operator",
        trigger_id: Optional[str] = None,
        due_at: Optional[datetime] = None,
        external_destination: Optional[str] = None,
    ) -> WorkflowActionRecord:
        uid = require_user_id(user_id, context="DecisionRepository.create_action")
        await self._require_write_path(user_id=uid, operation="workflow action creation")
        action = WorkflowActionType(action_type)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                if self.authority_service is not None and hasattr(self.authority_service, "assert_write_path_on_connection"):
                    await self.authority_service.assert_write_path_on_connection(conn, user_id=uid, operation="workflow action creation")
                recommendation = await conn.fetchrow(
                    """
                    select r.missing_information,o.legacy_startup_id from public.opportunities o
                    left join public.recommendations r
                      on r.user_id=o.user_id and r.recommendation_id=o.current_recommendation_id
                    where o.user_id=$1 and o.opportunity_id=$2 for update of o
                    """,
                    uid, opportunity_id,
                )
                if recommendation is None:
                    raise LookupError("Opportunity not found for tenant")
                gaps = _json(recommendation.get("missing_information"), [])
                export_context = None
                if action is WorkflowActionType.EXPORT_TO_CRM:
                    export_context = await self._load_export_context(
                        conn, user_id=uid, opportunity_id=opportunity_id
                    )
                record = await self._insert_action(
                    conn, user_id=uid, opportunity_id=opportunity_id,
                    action_type=action, trigger_type=trigger_type, trigger_id=trigger_id,
                    missing_evidence=gaps, due_at=due_at,
                    external_destination=external_destination,
                    export_context=export_context,
                )
                await self._outbox(
                    conn, user_id=uid, aggregate_type="workflow_action",
                    aggregate_id=record.workflow_action_id,
                    event_type="workflow_action.created",
                    payload={
                        "workflow_action_id": record.workflow_action_id,
                        "opportunity_id": opportunity_id,
                        "action_type": action.value,
                        "requires_approval": record.requires_approval,
                        "legacy_startup_id": (
                            str(recommendation["legacy_startup_id"])
                            if recommendation.get("legacy_startup_id")
                            else None
                        ),
                        "compatibility_reason": (
                            f"workflow action created: {action.value}"
                        ),
                    },
                )
                return record

    async def approve_action(
        self,
        *,
        user_id: str,
        workflow_action_id: str,
        approved_by: str,
        approved_content: Optional[Dict[str, Any]] = None,
    ) -> WorkflowActionRecord:
        uid = require_user_id(user_id, context="DecisionRepository.approve_action")
        await self._require_write_path(user_id=uid, operation="workflow action approval")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                if self.authority_service is not None and hasattr(self.authority_service, "assert_write_path_on_connection"):
                    await self.authority_service.assert_write_path_on_connection(conn, user_id=uid, operation="workflow action approval")
                row = await conn.fetchrow(
                    """
                    update public.workflow_actions as wa
                    set status='approved',approved_by=$3,approved_at=now(),
                        approved_content=coalesce($4::jsonb,generated_content),updated_at=now()
                    from public.opportunities as o
                    where wa.workflow_action_id=$1 and wa.user_id=$2
                      and wa.opportunity_id=o.opportunity_id and o.user_id=wa.user_id
                      and wa.status='pending_approval' and wa.requires_approval=true
                    returning wa.*,o.legacy_startup_id
                    """,
                    workflow_action_id, uid, approved_by,
                    json.dumps(approved_content) if approved_content is not None else None,
                )
                if row is None:
                    raise LookupError("Pending action not found for tenant")
                payload = db_row(row)
                legacy_startup_id = payload.pop("legacy_startup_id", None)
                payload["generated_content"] = _json(payload.get("generated_content"), {})
                payload["approved_content"] = _json(payload.get("approved_content"), None)
                payload["missing_evidence"] = _json(payload.get("missing_evidence"), [])
                record = WorkflowActionRecord.model_validate(payload)
                await self._outbox(
                    conn, user_id=uid, aggregate_type="workflow_action",
                    aggregate_id=workflow_action_id,
                    event_type="workflow_action.approved",
                    payload={
                        "workflow_action_id": workflow_action_id,
                        "approved_by": approved_by,
                        "external_write_performed": False,
                        "opportunity_id": record.opportunity_id,
                        "action_type": record.action_type.value,
                        "legacy_startup_id": (
                            str(legacy_startup_id) if legacy_startup_id else None
                        ),
                        "compatibility_reason": (
                            f"workflow action approved: {record.action_type.value}"
                        ),
                    },
                )
                return record

    async def list_actions(self, *, user_id: str, opportunity_id: str, limit: int = 100):
        uid = require_user_id(user_id, context="DecisionRepository.list_actions")
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select * from public.workflow_actions
                where user_id=$1 and opportunity_id=$2 order by created_at desc limit $3
                """,
                uid, opportunity_id, max(1, min(int(limit), 200)),
            )
        output = []
        for row in rows:
            payload = db_row(row)
            payload["generated_content"] = _json(payload.get("generated_content"), {})
            payload["approved_content"] = _json(payload.get("approved_content"), None)
            payload["missing_evidence"] = _json(payload.get("missing_evidence"), [])
            output.append(WorkflowActionRecord.model_validate(payload))
        return output
