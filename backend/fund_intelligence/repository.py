"""Transactional repository for attributed, proposal-only institutional learning."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional
from uuid import uuid4

from fund_intelligence.models import (
    PolicyProposalStatus,
    PolicyVersionStatus,
    ProposalReviewAction,
)
from fund_intelligence.service import build_override_pattern, can_publish, override_attribution
from tenant_context import require_user_id
from utils.db_rows import db_row


def _json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


def _public_row(row: Any) -> Dict[str, Any]:
    payload = db_row(row)
    for key, default in (
        ("detail", {}),
        ("limitations", []),
        ("proposed_policy_patch", {}),
        ("policy_patch", {}),
        ("opportunity_examples", []),
        ("estimated_effect", {}),
    ):
        if key in payload:
            payload[key] = _json(payload[key], default)
    return payload


class FundIntelligenceRepository:
    def __init__(self, pool: Any):
        self.pool = pool

    @staticmethod
    async def _outbox(
        conn: Any,
        *,
        user_id: str,
        aggregate_id: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> None:
        await conn.execute(
            """
            insert into public.domain_outbox (
              event_id,user_id,aggregate_type,aggregate_id,event_type,event_version,
              payload,publication_attempts,next_attempt_at,created_at
            ) values ($1,$2,'fund_intelligence',$3,$4,1,$5::jsonb,0,now(),now())
            """,
            str(uuid4()), user_id, aggregate_id, event_type, json.dumps(payload),
        )

    async def derive_override_patterns(self, *, user_id: str) -> Dict[str, Any]:
        uid = require_user_id(user_id, context="FundIntelligenceRepository.derive_override_patterns")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                minimum = await conn.fetchval(
                    """
                    insert into public.fund_intelligence_settings (user_id)
                    values ($1) on conflict (user_id) do update set user_id=excluded.user_id
                    returning minimum_override_sample
                    """,
                    uid,
                )
                overrides = await conn.fetch(
                    """
                    select override_signal_id,opportunity_id,override_type,note,created_at
                    from public.override_signals where user_id=$1 order by created_at
                    """,
                    uid,
                )
                signal_by_source: Dict[str, str] = {}
                for source in overrides:
                    signal_id = str(uuid4())
                    row = await conn.fetchrow(
                        """
                        insert into public.learning_signals (
                          learning_signal_id,user_id,opportunity_id,source_type,source_id,
                          signal_type,attribution,strength,detail,observed_at,created_at
                        ) values ($1,$2,$3,'override_signal',$4,'human_override',$5,1,$6::jsonb,$7,now())
                        on conflict (user_id,source_type,source_id,signal_type) do nothing
                        returning learning_signal_id
                        """,
                        signal_id, uid, source["opportunity_id"], source["override_signal_id"],
                        override_attribution(str(source["override_type"])).value,
                        json.dumps({"override_type": str(source["override_type"]), "note_present": bool(source.get("note"))}),
                        source["created_at"],
                    )
                    if row is None:
                        resolved = await conn.fetchval(
                            """
                            select learning_signal_id from public.learning_signals
                            where user_id=$1 and source_type='override_signal' and source_id=$2
                              and signal_type='human_override'
                            """,
                            uid, source["override_signal_id"],
                        )
                        signal_by_source[str(source["override_signal_id"])] = str(resolved)
                    else:
                        signal_by_source[str(source["override_signal_id"])] = str(row["learning_signal_id"])

                grouped: Dict[str, list[Any]] = {}
                for source in overrides:
                    grouped.setdefault(str(source["override_type"]), []).append(source)
                proposals = []
                observations = []
                for override_type, sources in sorted(grouped.items()):
                    signal_ids = [signal_by_source[str(source["override_signal_id"])] for source in sources]
                    opportunity_ids = [str(source["opportunity_id"]) for source in sources]
                    pattern = build_override_pattern(
                        override_type=override_type,
                        signal_ids=signal_ids,
                        opportunity_ids=opportunity_ids,
                        minimum_sample_size=int(minimum),
                    )
                    observations.append(pattern.model_dump(mode="json"))
                    canonical = json.dumps(
                        {"override_type": override_type, "signal_ids": sorted(signal_ids)},
                        sort_keys=True, separators=(",", ":"),
                    )
                    fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
                    proposal_id = str(uuid4())
                    first_at = min(source["created_at"] for source in sources)
                    last_at = max(source["created_at"] for source in sources)
                    status = (
                        PolicyProposalStatus.READY_FOR_REVIEW
                        if pattern.ready_for_proposal
                        else PolicyProposalStatus.DRAFT
                    )
                    row = await conn.fetchrow(
                        """
                        insert into public.policy_proposals (
                          policy_proposal_id,user_id,proposal_fingerprint,pattern_summary,
                          attribution,sample_size,sample_period_start,sample_period_end,
                          confidence,limitations,proposed_policy_patch,status,created_at,updated_at
                        ) values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11::jsonb,$12,now(),now())
                        on conflict (user_id,proposal_fingerprint) do nothing returning *
                        """,
                        proposal_id, uid, fingerprint,
                        f"{pattern.sample_size} attributed {override_type.replace('_', ' ')} overrides",
                        pattern.attribution.value, pattern.sample_size, first_at, last_at,
                        min(0.9, pattern.sample_size / max(int(minimum), 1) * 0.6),
                        json.dumps(pattern.limitations), json.dumps(pattern.proposed_patch), status.value,
                    )
                    if row is None:
                        row = await conn.fetchrow(
                            "select * from public.policy_proposals where user_id=$1 and proposal_fingerprint=$2",
                            uid, fingerprint,
                        )
                    for signal_id in signal_ids:
                        await conn.execute(
                            """
                            insert into public.proposal_signal_links (
                              proposal_signal_link_id,user_id,policy_proposal_id,
                              learning_signal_id,relationship,created_at
                            ) values ($1,$2,$3,$4,'supports',now())
                            on conflict (user_id,policy_proposal_id,learning_signal_id) do nothing
                            """,
                            str(uuid4()), uid, row["policy_proposal_id"], signal_id,
                        )
                    proposals.append(_public_row(row))
                return {"observations": observations, "proposals": proposals}

    async def list_proposals(
        self, *, user_id: str, status: Optional[PolicyProposalStatus | str] = None, limit: int = 100
    ) -> list[Dict[str, Any]]:
        uid = require_user_id(user_id, context="FundIntelligenceRepository.list_proposals")
        normalized = PolicyProposalStatus(status).value if status else None
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                select * from public.policy_proposals
                where user_id=$1 and ($2::text is null or status=$2)
                order by created_at desc limit $3
                """,
                uid, normalized, max(1, min(int(limit), 200)),
            )
        return [_public_row(row) for row in rows]

    async def get_proposal(self, *, user_id: str, policy_proposal_id: str) -> Optional[Dict[str, Any]]:
        uid = require_user_id(user_id, context="FundIntelligenceRepository.get_proposal")
        async with self.pool.acquire() as conn:
            proposal = await conn.fetchrow(
                "select * from public.policy_proposals where user_id=$1 and policy_proposal_id=$2",
                uid, policy_proposal_id,
            )
            if proposal is None:
                return None
            signals = await conn.fetch(
                """
                select s.* from public.learning_signals s
                join public.proposal_signal_links l
                  on l.user_id=s.user_id and l.learning_signal_id=s.learning_signal_id
                where l.user_id=$1 and l.policy_proposal_id=$2 order by s.observed_at
                """,
                uid, policy_proposal_id,
            )
            previews = await conn.fetch(
                """
                select * from public.policy_impact_previews
                where user_id=$1 and policy_proposal_id=$2 order by created_at desc limit 10
                """,
                uid, policy_proposal_id,
            )
            versions = await conn.fetch(
                """
                select * from public.governed_policy_versions
                where user_id=$1 and policy_proposal_id=$2 order by created_at desc
                """,
                uid, policy_proposal_id,
            )
        return {
            "proposal": _public_row(proposal),
            "signals": [_public_row(row) for row in signals],
            "impact_previews": [_public_row(row) for row in previews],
            "policy_versions": [_public_row(row) for row in versions],
        }

    async def preview_impact(
        self, *, user_id: str, policy_proposal_id: str, actor_id: str
    ) -> Dict[str, Any]:
        uid = require_user_id(user_id, context="FundIntelligenceRepository.preview_impact")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                proposal = await conn.fetchrow(
                    "select * from public.policy_proposals where user_id=$1 and policy_proposal_id=$2",
                    uid, policy_proposal_id,
                )
                if proposal is None:
                    raise LookupError("Proposal not found for tenant")
                limit = await conn.fetchval(
                    "select coalesce((select preview_row_limit from public.fund_intelligence_settings where user_id=$1),200)",
                    uid,
                )
                examples = await conn.fetch(
                    """
                    select distinct o.opportunity_id,o.decision_state,o.attention_priority
                    from public.learning_signals s
                    join public.proposal_signal_links l
                      on l.user_id=s.user_id and l.learning_signal_id=s.learning_signal_id
                    join public.opportunities o
                      on o.user_id=s.user_id and o.opportunity_id=s.opportunity_id
                    where l.user_id=$1 and l.policy_proposal_id=$2
                    order by o.attention_priority desc limit $3
                    """,
                    uid, policy_proposal_id, int(limit),
                )
                row = await conn.fetchrow(
                    """
                    insert into public.policy_impact_previews (
                      policy_impact_preview_id,user_id,policy_proposal_id,sample_size,
                      affected_opportunity_count,opportunity_examples,estimated_effect,
                      limitations,created_by,created_at
                    ) values ($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb,$8::jsonb,$9,now()) returning *
                    """,
                    str(uuid4()), uid, policy_proposal_id, int(proposal["sample_size"]),
                    len(examples), json.dumps([dict(item) for item in examples], default=str),
                    json.dumps({"mode": "bounded_replay", "result": "flag_for_operator_review", "automatic_rescore": False}),
                    json.dumps(_json(proposal["limitations"], [])),
                    actor_id,
                )
                return _public_row(row)

    async def review_proposal(
        self,
        *,
        user_id: str,
        policy_proposal_id: str,
        actor_id: str,
        action: ProposalReviewAction | str,
        rationale: str,
        edited_policy_patch: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        uid = require_user_id(user_id, context="FundIntelligenceRepository.review_proposal")
        review = ProposalReviewAction(action)
        status = {
            ProposalReviewAction.ACCEPT: PolicyProposalStatus.ACCEPTED,
            ProposalReviewAction.EDIT_AND_ACCEPT: PolicyProposalStatus.EDITED_AND_ACCEPTED,
            ProposalReviewAction.REJECT: PolicyProposalStatus.REJECTED,
            ProposalReviewAction.DEFER: PolicyProposalStatus.DEFERRED,
        }[review]
        if review is ProposalReviewAction.EDIT_AND_ACCEPT and not edited_policy_patch:
            raise ValueError("edited_policy_patch is required for edit_and_accept")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                proposal = await conn.fetchrow(
                    """
                    select * from public.policy_proposals where user_id=$1 and policy_proposal_id=$2
                    for update
                    """,
                    uid, policy_proposal_id,
                )
                if proposal is None:
                    raise LookupError("Proposal not found for tenant")
                current = PolicyProposalStatus(str(proposal["status"]))
                if current not in {
                    PolicyProposalStatus.DRAFT,
                    PolicyProposalStatus.READY_FOR_REVIEW,
                    PolicyProposalStatus.DEFERRED,
                }:
                    raise RuntimeError("Proposal has already received a terminal review")
                patch = edited_policy_patch or _json(proposal["proposed_policy_patch"], {})
                version = None
                if status in {PolicyProposalStatus.ACCEPTED, PolicyProposalStatus.EDITED_AND_ACCEPTED}:
                    version = await conn.fetchrow(
                        """
                        insert into public.governed_policy_versions (
                          governed_policy_version_id,user_id,policy_proposal_id,policy_patch,
                          status,created_by,created_at
                        ) values ($1,$2,$3,$4::jsonb,'draft',$5,now()) returning *
                        """,
                        str(uuid4()), uid, policy_proposal_id, json.dumps(patch), actor_id,
                    )
                row = await conn.fetchrow(
                    """
                    update public.policy_proposals
                    set status=$3,reviewer_rationale=$4,reviewed_by=$5,reviewed_at=now(),
                        proposed_policy_patch=$6::jsonb,resulting_policy_version_id=$7,updated_at=now()
                    where user_id=$1 and policy_proposal_id=$2 returning *
                    """,
                    uid, policy_proposal_id, status.value, rationale, actor_id,
                    json.dumps(patch), version["governed_policy_version_id"] if version else None,
                )
                await self._outbox(
                    conn, user_id=uid, aggregate_id=policy_proposal_id,
                    event_type="policy_proposal.reviewed",
                    payload={"policy_proposal_id": policy_proposal_id, "status": status.value, "actor_id": actor_id},
                )
                return {
                    "proposal": _public_row(row),
                    "policy_version": _public_row(version) if version else None,
                    "production_policy_changed": False,
                }

    async def get_publishable_version(
        self, *, user_id: str, governed_policy_version_id: str
    ) -> Dict[str, Any]:
        uid = require_user_id(user_id, context="FundIntelligenceRepository.get_publishable_version")
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select v.*,p.status as proposal_status from public.governed_policy_versions v
                join public.policy_proposals p
                  on p.user_id=v.user_id and p.policy_proposal_id=v.policy_proposal_id
                where v.user_id=$1 and v.governed_policy_version_id=$2
                """,
                uid, governed_policy_version_id,
            )
        if row is None:
            raise LookupError("Policy version not found for tenant")
        if not can_publish(str(row["proposal_status"]), str(row["status"])):
            raise RuntimeError("Only an accepted draft policy version can be published")
        return _public_row(row)

    async def mark_published(
        self,
        *,
        user_id: str,
        governed_policy_version_id: str,
        actor_id: str,
        published_policy_id: str,
        published_policy_hash: str,
    ) -> Dict[str, Any]:
        uid = require_user_id(user_id, context="FundIntelligenceRepository.mark_published")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    update public.governed_policy_versions v
                    set status='published',published_by=$3,published_policy_id=$4,
                        published_policy_hash=$5,published_at=now()
                    from public.policy_proposals p
                    where v.user_id=$1 and v.governed_policy_version_id=$2
                      and p.user_id=v.user_id and p.policy_proposal_id=v.policy_proposal_id
                      and v.status='draft' and p.status in ('accepted','edited_and_accepted')
                    returning v.*
                    """,
                    uid, governed_policy_version_id, actor_id,
                    published_policy_id, published_policy_hash,
                )
                if row is None:
                    raise RuntimeError("Policy version is no longer publishable")
                await conn.execute(
                    """
                    update public.governed_policy_versions set status='superseded'
                    where user_id=$1 and governed_policy_version_id<>$2 and status='published'
                    """,
                    uid, governed_policy_version_id,
                )
                await self._outbox(
                    conn, user_id=uid, aggregate_id=governed_policy_version_id,
                    event_type="governed_policy_version.published",
                    payload={"governed_policy_version_id": governed_policy_version_id, "published_by": actor_id, "published_policy_id": published_policy_id},
                )
                return _public_row(row)
