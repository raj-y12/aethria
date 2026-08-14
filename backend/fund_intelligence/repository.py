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
from fund_thesis_repository import FundThesisRepository
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
        self.thesis_repository = FundThesisRepository(pool)

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

    async def get_observations(
        self,
        *,
        user_id: str,
        sector: Optional[str] = None,
        stage: Optional[str] = None,
        geography: Optional[str] = None,
        thesis_version_id: Optional[str] = None,
        date_from: Any = None,
        date_to: Any = None,
        observation_type: Optional[str] = None,
    ) -> list[Dict[str, Any]]:
        """Build descriptive observations from canonical historical decision episodes."""
        from fund_intelligence.observations import build_observations

        uid = require_user_id(user_id, context="FundIntelligenceRepository.get_observations")
        async with self.pool.acquire() as conn:
            evaluations = await conn.fetch(
                """
                select evaluation_id, opportunity_id, claim_snapshot,
                       thesis_version_id, policy_version_id, created_at, completed_at
                from public.evaluation_runs
                where user_id=$1 and status='completed'
                order by coalesce(completed_at, created_at), created_at, evaluation_id
                limit 5000
                """,
                uid,
            )
            recommendations = await conn.fetch(
                """
                select recommendation_id, evaluation_id, recommended_state, created_at
                from public.recommendations
                where user_id=$1
                order by created_at, recommendation_id
                limit 10000
                """,
                uid,
            )
            rulings = await conn.fetch(
                """
                select hr.ruling_id, hr.recommendation_id, hr.decision, hr.created_at,
                       os.override_type
                from public.human_rulings hr
                left join public.override_signals os
                  on os.user_id=hr.user_id and os.ruling_id=hr.ruling_id
                where hr.user_id=$1
                order by hr.created_at, hr.ruling_id
                limit 10000
                """,
                uid,
            )
            interpretations = await conn.fetch(
                """
                select ruling_id, version, positive_factors, negative_factors,
                       accepted_risks, decisive_factors, overridden_criteria,
                       interpretation_id, source, created_at, provenance
                from public.ruling_interpretations
                where user_id=$1
                order by ruling_id, version
                limit 10000
                """,
                uid,
            )
            criteria = await conn.fetch(
                """
                select ca.evaluation_id, ca.criterion, ca.score, ca.confidence,
                       ca.evidence_sufficiency
                from public.criterion_assessments ca
                join public.evaluation_runs e
                  on e.user_id=ca.user_id and e.evaluation_id=ca.evaluation_id
                where ca.user_id=$1 and e.status='completed'
                order by ca.evaluation_id, ca.criterion
                limit 40000
                """,
                uid,
            )

        def json_value(value: Any, default: Any) -> Any:
            return _json(value, default)

        recommendations_by_id: Dict[str, Dict[str, Any]] = {}
        for row in recommendations:
            item = dict(row)
            recommendations_by_id[str(item["recommendation_id"])] = item
        rulings_by_recommendation: Dict[str, Dict[str, Any]] = {}
        for row in rulings:
            item = dict(row)
            recommendation_id = item.get("recommendation_id")
            if recommendation_id:
                rulings_by_recommendation[str(recommendation_id)] = item
        interpretations_by_ruling: Dict[str, Dict[str, Any]] = {}
        for row in interpretations:
            item = dict(row)
            interpretations_by_ruling[str(item["ruling_id"])] = {
                **item,
                "positive_factors": json_value(item.get("positive_factors"), []),
                "negative_factors": json_value(item.get("negative_factors"), []),
                "accepted_risks": json_value(item.get("accepted_risks"), []),
                "decisive_factors": json_value(item.get("decisive_factors"), []),
                "overridden_criteria": json_value(item.get("overridden_criteria"), []),
                "provenance": json_value(item.get("provenance"), {}),
            }
        criteria_by_evaluation: Dict[str, list[Dict[str, Any]]] = {}
        for row in criteria:
            item = dict(row)
            criteria_by_evaluation.setdefault(str(item["evaluation_id"]), []).append({
                key: value for key, value in item.items() if key != "evaluation_id"
            })

        aliases = {
            "sector": {"sector", "industry", "category"},
            "stage": {"stage", "funding_stage"},
            "geography": {"geography", "location", "country"},
        }
        episodes: list[Dict[str, Any]] = []
        for raw in evaluations:
            evaluation = dict(raw)
            dimensions: Dict[str, str] = {}
            for claim in json_value(evaluation.get("claim_snapshot"), []):
                if not isinstance(claim, dict):
                    continue
                claim_type = str(claim.get("claim_type") or "").strip().lower()
                value = str(claim.get("normalized_value") or claim.get("display_text") or "").strip().lower()
                for dimension, names in aliases.items():
                    if claim_type in names and value and dimension not in dimensions:
                        dimensions[dimension] = value
            recommendation = next(
                (item for item in recommendations_by_id.values()
                 if str(item.get("evaluation_id")) == str(evaluation["evaluation_id"])),
                None,
            )
            ruling = (
                rulings_by_recommendation.get(str(recommendation["recommendation_id"]))
                if recommendation else None
            )
            episodes.append({
                "evaluation_id": str(evaluation["evaluation_id"]),
                "opportunity_id": str(evaluation.get("opportunity_id") or ""),
                "decision_time": evaluation.get("completed_at") or evaluation.get("created_at"),
                "thesis_version_id": evaluation.get("thesis_version_id"),
                "policy_version_id": evaluation.get("policy_version_id"),
                "dimensions": dimensions,
                "criteria": criteria_by_evaluation.get(str(evaluation["evaluation_id"]), []),
                "recommendation": recommendation,
                "ruling": {
                    **ruling,
                    "interpretation": interpretations_by_ruling.get(str(ruling["ruling_id"])),
                } if ruling else None,
                "interpretation": interpretations_by_ruling.get(str(ruling["ruling_id"])) if ruling else None,
            })
        return build_observations(
            episodes, sector=sector, stage=stage, geography=geography,
            thesis_version_id=thesis_version_id, date_from=date_from, date_to=date_to,
            observation_type=observation_type,
        )

    async def get_hypotheses(
        self,
        *,
        user_id: str,
        sector: Optional[str] = None,
        stage: Optional[str] = None,
        geography: Optional[str] = None,
        thesis_version_id: Optional[str] = None,
        date_from: Any = None,
        date_to: Any = None,
        hypothesis_family: Optional[str] = None,
    ) -> list[Dict[str, Any]]:
        """Build descriptive hypotheses from the deterministic observation projection."""
        from fund_intelligence.hypotheses import build_hypotheses

        observations = await self.get_observations(
            user_id=user_id, sector=sector, stage=stage, geography=geography,
            thesis_version_id=thesis_version_id, date_from=date_from, date_to=date_to,
        )
        return build_hypotheses(observations, hypothesis_family=hypothesis_family)

    async def get_replay_preview(
        self, *, user_id: str, hypothesis_id: str
    ) -> Optional[Dict[str, Any]]:
        """Return a tenant-scoped, fail-closed replayability preview."""
        from fund_intelligence.replay import build_replay_preview

        uid = require_user_id(user_id, context="FundIntelligenceRepository.get_replay_preview")
        hypotheses = await self.get_hypotheses(user_id=uid)
        hypothesis = next(
            (item for item in hypotheses if str(item.get("hypothesis_id")) == str(hypothesis_id)),
            None,
        )
        return build_replay_preview(hypothesis) if hypothesis else None

    async def get_counterfactual_proposals(
        self,
        *,
        user_id: str,
        sector: Optional[str] = None,
        stage: Optional[str] = None,
        geography: Optional[str] = None,
        thesis_version_id: Optional[str] = None,
        date_from: Any = None,
        date_to: Any = None,
        hypothesis_family: Optional[str] = None,
    ) -> list[Dict[str, Any]]:
        """Generate tenant-scoped draft counterfactuals without persistence or publication."""
        from fund_intelligence.proposals import build_counterfactual_proposals

        uid = require_user_id(
            user_id, context="FundIntelligenceRepository.get_counterfactual_proposals"
        )
        hypotheses = await self.get_hypotheses(
            user_id=uid, sector=sector, stage=stage, geography=geography,
            thesis_version_id=thesis_version_id, date_from=date_from, date_to=date_to,
            hypothesis_family=hypothesis_family,
        )
        return build_counterfactual_proposals(hypotheses)

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
        self,
        *,
        user_id: str,
        policy_proposal_id: str,
        actor_id: str,
        policy_hash: str,
        config_hash: str,
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
                    json.dumps({"mode": "bounded_replay", "result": "flag_for_operator_review", "automatic_rescore": False, "policy_hash": policy_hash, "config_hash": config_hash}),
                    json.dumps(_json(proposal["limitations"], [])),
                    actor_id,
                )
                if row is None:
                    return {
                        "governed_policy_version_id": version_id,
                        "publication_source": "settings",
                        "policy_hash": str(policy_hash),
                        "status": "published",
                    }
                return _public_row(row)

    async def review_proposal(
        self,
        *,
        user_id: str,
        policy_proposal_id: str,
        actor_id: str,
        action: ProposalReviewAction | str,
        rationale: str,
        resulting_fund_config: Optional[Dict[str, Any]] = None,
        policy_hash: Optional[str] = None,
        config_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        uid = require_user_id(user_id, context="FundIntelligenceRepository.review_proposal")
        review = ProposalReviewAction(action)
        status = {
            ProposalReviewAction.ACCEPT: PolicyProposalStatus.ACCEPTED,
            ProposalReviewAction.EDIT_AND_ACCEPT: PolicyProposalStatus.EDITED_AND_ACCEPTED,
            ProposalReviewAction.REJECT: PolicyProposalStatus.REJECTED,
            ProposalReviewAction.DEFER: PolicyProposalStatus.DEFERRED,
        }[review]
        accepting = status in {
            PolicyProposalStatus.ACCEPTED,
            PolicyProposalStatus.EDITED_AND_ACCEPTED,
        }
        if accepting and (
            not resulting_fund_config
            or not str(policy_hash or "").strip()
            or not str(config_hash or "").strip()
        ):
            raise ValueError(
                "resulting_fund_config, policy_hash, and config_hash are required for acceptance"
            )
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
                version = None
                if accepting:
                    preview = await conn.fetchrow(
                        """
                        select estimated_effect from public.policy_impact_previews
                        where user_id=$1 and policy_proposal_id=$2
                        order by created_at desc limit 1
                        """,
                        uid,
                        policy_proposal_id,
                    )
                    preview_effect = _json(
                        preview.get("estimated_effect") if preview else None, {}
                    )
                    if (
                        preview_effect.get("policy_hash") != policy_hash
                        or preview_effect.get("config_hash") != config_hash
                    ):
                        raise RuntimeError(
                            "Acceptance requires a current impact preview for the exact resulting policy"
                        )
                    version = await conn.fetchrow(
                        """
                        insert into public.governed_policy_versions (
                          governed_policy_version_id,user_id,policy_proposal_id,policy_patch,
                          policy_hash,status,created_by,created_at
                        ) values ($1,$2,$3,$4::jsonb,$5,'draft',$6,now()) returning *
                        """,
                        str(uuid4()), uid, policy_proposal_id,
                        json.dumps(resulting_fund_config), policy_hash, actor_id,
                    )
                row = await conn.fetchrow(
                    """
                    update public.policy_proposals
                    set status=$3,reviewer_rationale=$4,reviewed_by=$5,reviewed_at=now(),
                        resulting_policy_version_id=$6,updated_at=now()
                    where user_id=$1 and policy_proposal_id=$2 returning *
                    """,
                    uid, policy_proposal_id, status.value, rationale, actor_id,
                    version["governed_policy_version_id"] if version else None,
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
    ) -> Dict[str, Any]:
        uid = require_user_id(user_id, context="FundIntelligenceRepository.mark_published")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("select pg_advisory_xact_lock(hashtext($1))", uid)
                publishable = await conn.fetchrow(
                    """
                    select v.governed_policy_version_id
                    from public.governed_policy_versions v
                    join public.policy_proposals p
                      on p.user_id=v.user_id
                     and p.policy_proposal_id=v.policy_proposal_id
                    where v.user_id=$1 and v.governed_policy_version_id=$2
                      and v.status='draft'
                      and p.status in ('accepted','edited_and_accepted')
                    for update of v
                    """,
                    uid,
                    governed_policy_version_id,
                )
                if publishable is None:
                    raise RuntimeError("Policy version is no longer publishable")
                await conn.execute(
                    """
                    update public.governed_policy_versions set status='superseded'
                    where user_id=$1 and governed_policy_version_id<>$2
                      and status='published'
                    """,
                    uid,
                    governed_policy_version_id,
                )
                row = await conn.fetchrow(
                    """
                    update public.governed_policy_versions
                    set status='published',published_by=$3,published_policy_id=$4,
                        published_policy_hash=policy_hash,published_at=now()
                    where user_id=$1 and governed_policy_version_id=$2
                      and status='draft'
                    returning *
                    """,
                    uid, governed_policy_version_id, actor_id,
                    governed_policy_version_id,
                )
                if row is None:
                    raise RuntimeError("Policy version is no longer publishable")
                await self._update_settings_policy_pointer(conn, uid, row)
                await self._outbox(
                    conn, user_id=uid, aggregate_id=governed_policy_version_id,
                    event_type="governed_policy_version.published",
                    payload={
                        "governed_policy_version_id": governed_policy_version_id,
                        "published_by": actor_id,
                        "published_policy_id": governed_policy_version_id,
                        "policy_hash": str(row["policy_hash"]),
                        "fund_config": _json(row["policy_patch"], {}),
                    },
                )
                return _public_row(row)

    async def get_active_published_policy(self, *, user_id: str) -> Dict[str, Any]:
        uid = require_user_id(
            user_id,
            context="FundIntelligenceRepository.get_active_published_policy",
        )
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                select * from public.governed_policy_versions
                where user_id=$1 and status='published'
                order by published_at desc limit 1
                """,
                uid,
            )
        if row is None:
            raise LookupError("Published governed policy not found for tenant")
        return _public_row(row)

    async def publish_settings_policy(
        self,
        *,
        user_id: str,
        actor_id: str,
        fund_config: Dict[str, Any],
        policy_hash: str,
        expected_policy_id: Optional[str] = None,
        expected_policy_hash: Optional[str] = None,
        governed_policy_version_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Atomically publish an operator Settings policy into the same authority."""
        uid = require_user_id(
            user_id,
            context="FundIntelligenceRepository.publish_settings_policy",
        )
        version_id = governed_policy_version_id or str(uuid4())
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("select pg_advisory_xact_lock(hashtext($1))", uid)
                settings = await self._lock_settings(conn, uid)
                current_fund_config = settings.get("fund_config") if isinstance(settings.get("fund_config"), dict) else {}
                current_id = str(current_fund_config.get("activePolicyVersionId") or "").strip()
                current_hash = str(current_fund_config.get("publishedPolicyHash") or "").strip()
                if expected_policy_id is not None and current_id != str(expected_policy_id or "").strip():
                    raise RuntimeError("Expected active policy identity is stale")
                if expected_policy_hash is not None and current_hash != str(expected_policy_hash or "").strip():
                    raise RuntimeError("Expected active policy hash is stale")
                existing_by_id = await conn.fetchrow(
                    "select * from public.governed_policy_versions where user_id=$1 and governed_policy_version_id=$2",
                    uid, version_id,
                )
                if existing_by_id is not None:
                    if str(existing_by_id["policy_hash"] or "") != str(policy_hash) or _json(existing_by_id["policy_patch"], {}) != fund_config:
                        raise RuntimeError("Policy identity is already bound to a different payload")
                    await self._update_settings_policy_pointer(conn, uid, existing_by_id)
                    return _public_row(existing_by_id)
                existing_same = await conn.fetchrow(
                    """
                    select * from public.governed_policy_versions
                    where user_id=$1 and status='published' and policy_hash=$2
                      and policy_patch=$3::jsonb
                    order by published_at desc limit 1
                    """,
                    uid, str(policy_hash), json.dumps(fund_config),
                )
                if existing_same is not None:
                    await self._update_settings_policy_pointer(conn, uid, existing_same)
                    return _public_row(existing_same)
                await conn.execute(
                    """
                    update public.governed_policy_versions set status='superseded'
                    where user_id=$1 and status='published'
                    """,
                    uid,
                )
                row = await conn.fetchrow(
                    """
                    insert into public.governed_policy_versions (
                      governed_policy_version_id,user_id,policy_proposal_id,
                      publication_source,policy_patch,policy_hash,status,created_by,
                      published_by,published_policy_id,published_policy_hash,
                      created_at,published_at
                    ) values (
                      $1,$2,null,'settings',$3::jsonb,$4,'published',$5,$5,$6,$4,
                      now(),now()
                    ) returning *
                    """,
                    version_id,
                    uid,
                    json.dumps(fund_config),
                    str(policy_hash),
                    actor_id,
                    version_id,
                )
                await self._update_settings_policy_pointer(conn, uid, row)
                await self._outbox(
                    conn,
                    user_id=uid,
                    aggregate_id=version_id,
                    event_type="governed_policy_version.published",
                    payload={
                        "governed_policy_version_id": version_id,
                        "published_by": actor_id,
                        "published_policy_id": version_id,
                        "policy_hash": str(policy_hash),
                        "fund_config": fund_config,
                    },
                )
                if row is None:
                    return {
                        "governed_policy_version_id": version_id,
                        "publication_source": "settings",
                        "policy_hash": str(policy_hash),
                        "status": "published",
                    }
                return _public_row(row)

    @staticmethod
    async def _lock_settings(conn: Any, user_id: str) -> Dict[str, Any]:
        await conn.execute(
            "insert into public.settings (user_id,key,data) values ($1,$1,'{}'::jsonb) on conflict (user_id,key) do nothing",
            user_id,
        )
        row = await conn.fetchrow(
            "select data from public.settings where user_id=$1 and key=$1 for update",
            user_id,
        )
        if row is None:
            return {}
        try:
            value = row["data"]
        except (KeyError, TypeError):
            return {}
        return _json(value, {})

    @classmethod
    async def _update_settings_policy_pointer(
        cls, conn: Any, user_id: str, policy: Any
    ) -> None:
        if policy is None:
            return
        settings = await cls._lock_settings(conn, user_id)
        fund_config = dict(settings.get("fund_config") or {})
        policy_id = str(
            policy.get("published_policy_id")
            or policy.get("governed_policy_version_id")
        )
        policy_hash = str(
            policy.get("published_policy_hash")
            or policy.get("policy_hash")
            or ""
        )
        published_at = policy.get("published_at") or policy.get("created_at")
        fund_config.update(
            {
                "activePolicyVersionId": policy_id,
                "publishedPolicyHash": policy_hash,
                "draftPolicyHash": policy_hash,
                "lastPublishedAt": published_at.isoformat() if hasattr(published_at, "isoformat") else published_at,
            }
        )
        settings["fund_config"] = fund_config
        await conn.execute(
            "update public.settings set data=$3::jsonb where user_id=$1 and key=$2",
            user_id, user_id, json.dumps(settings, default=str),
        )
