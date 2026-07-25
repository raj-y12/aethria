"""Transactional append-only rulings and approval-gated workflow actions."""

from __future__ import annotations

import json
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
    def __init__(self, pool: Any, *, authority_service: Any = None):
        self.pool = pool
        self.authority_service = authority_service

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

    async def create_ruling(self, ruling: HumanRulingInput, *, actor_id: str) -> Dict[str, Any]:
        uid = require_user_id(ruling.user_id, context="DecisionRepository.create_ruling")
        await self._require_write_path(user_id=uid, operation="human ruling creation")
        actor = str(actor_id or "").strip()
        if not actor:
            raise ValueError("actor_id is required")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                opportunity = await conn.fetchrow(
                    """
                    select o.current_ruling_id,o.current_recommendation_id,o.legacy_startup_id,
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
                await conn.execute(
                    """
                    update public.opportunities
                    set current_ruling_id=$3,decision_state=$4,updated_at=now()
                    where opportunity_id=$1 and user_id=$2
                    """,
                    ruling.opportunity_id, uid, ruling_id,
                    ruling_to_opportunity_state(ruling.decision),
                )
                if ruling.decision.value == "monitor":
                    await self._insert_action(
                        conn, user_id=uid, opportunity_id=ruling.opportunity_id,
                        action_type=WorkflowActionType.SCHEDULE_MONITOR_REVIEW,
                        trigger_type="human_ruling", trigger_id=ruling_id,
                        missing_evidence=[], due_at=None,
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
                payload = dict(row)
                payload["override_type"] = override.value if override else None
                return payload

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
    ) -> WorkflowActionRecord:
        generated = build_workflow_draft(action_type, missing_evidence)
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
        action = WorkflowActionType(action_type)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
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
                record = await self._insert_action(
                    conn, user_id=uid, opportunity_id=opportunity_id,
                    action_type=action, trigger_type=trigger_type, trigger_id=trigger_id,
                    missing_evidence=gaps, due_at=due_at,
                    external_destination=external_destination,
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
        async with self.pool.acquire() as conn:
            async with conn.transaction():
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
