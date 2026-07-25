"""One-way canonical-event projection into the legacy startups read model.

The authority tables remain the source of truth.  This module only creates a
small, display-oriented patch for the legacy ``startups`` row and never writes
canonical current pointers or authority records.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping
from authority.models import ProjectionReceipt
from tenant_context import require_user_id
from utils.partner_codes import legacy_partner_from_institutional_recommendation


COMPATIBILITY_CONSUMER = "startups_compatibility"


class ProjectionTenantMismatch(ValueError):
    """An event payload tried to project data owned by another tenant."""


class UnresolvedLegacyProjection(RuntimeError):
    """An authority event has no tenant-scoped legacy startup projection."""

class ProjectionDeferred(RuntimeError):
    """Projection is temporarily disallowed; the outbox event must be retried."""


@dataclass(frozen=True)
class LegacyProjectionPatch:
    """A deliberately bounded update to one legacy startup display row."""

    startup_id: str
    patch: dict[str, Any]


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key} is required for a legacy compatibility projection")
    return value


def _optional_text(payload: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return None


def _canonical_ids(payload: Mapping[str, Any]) -> dict[str, str]:
    return {
        f"canonical_{key}": value
        for key in (
            "company_id",
            "opportunity_id",
            "evaluation_id",
            "recommendation_id",
            "ruling_id",
            "memo_id",
            "workflow_action_id",
        )
        if (value := _optional_text(payload, key))
    }


def _recommendation_display(state: str) -> str:
    """Use the central compatibility map so legacy rows remain model-valid."""
    aliases = {
        "yes": "ADVANCE",
        "invest": "ADVANCE",
        "no": "PASS",
        "maybe": "MONITOR",
        "review": "INSUFFICIENT_EVIDENCE",
        "pending": "INSUFFICIENT_EVIDENCE",
    }
    canonical = aliases.get(state.strip().lower(), state.strip().upper())
    return legacy_partner_from_institutional_recommendation(canonical).value


def legacy_patch_for_event(
    event_type: str, payload: Mapping[str, Any]
) -> LegacyProjectionPatch | None:
    """Return the pure legacy read-model patch for a canonical authority event.

    Unknown events intentionally have no compatibility side effect.  The caller
    may still publish them to the domain event bus.
    """
    if not isinstance(payload, Mapping):
        raise ValueError("authority event payload must be an object")
    startup_id = _optional_text(payload, "legacy_startup_id", "startup_id")
    if not startup_id:
        # Canonical events that have no legacy row are still valid canonical
        # events; they simply have nothing to project.
        return None

    canonical = _canonical_ids(payload)
    event = str(event_type or "").strip()
    if event in {"observation_resolved", "identity_case.resolved", "identity.resolved"}:
        identity = {**canonical, "canonical_identity_status": "resolved"}
        if (reason := _optional_text(payload, "compatibility_reason", "reason", "resolution_reason")):
            identity["canonical_identity_reason"] = reason
        return LegacyProjectionPatch(startup_id, {"scout_info": identity})

    if event in {"evaluation.completed", "evaluation.created"}:
        evaluation = {**canonical, "canonical_evaluation_status": "completed"}
        if (reason := _optional_text(payload, "compatibility_reason", "reason", "rationale", "summary")):
            evaluation["canonical_evaluation_reason"] = reason
        patch: dict[str, Any] = {"review_info": evaluation}
        state = _optional_text(payload, "recommended_state", "state")
        if state:
            patch["partner_info"] = {
                **canonical,
                "recommendation": _recommendation_display(state),
                "canonical_recommendation_state": state.lower(),
            }
        return LegacyProjectionPatch(startup_id, patch)

    if event in {"recommendation.created", "recommendation.updated"}:
        state = _required_text(payload, "state")
        partner = {
            **canonical,
            "recommendation": _recommendation_display(state),
            "canonical_recommendation_state": state.lower(),
        }
        if (reason := _optional_text(payload, "compatibility_reason", "reason", "rationale", "change_explanation")):
            partner["canonical_recommendation_reason"] = reason
        if state.strip().lower() == "insufficient_evidence":
            partner["human_review_required"] = True
        return LegacyProjectionPatch(startup_id, {"partner_info": partner})

    if event == "human_ruling.created":
        decision = _required_text(payload, "decision").upper()
        resolution = {
            "decision": decision,
            "notes": _optional_text(payload, "rationale", "reason") or "",
            **canonical,
        }
        if (rationale := _optional_text(payload, "rationale", "compatibility_reason", "reason")):
            resolution["canonical_ruling_rationale"] = rationale
        return LegacyProjectionPatch(startup_id, {"human_resolution": resolution})

    if event in {"memo.created", "memo.generated", "investment_memo.created"}:
        memo = _optional_text(payload, "markdown", "investment_memo_markdown", "content")
        trace = {**canonical, "canonical_memo_event": event}
        if (reason := _optional_text(payload, "compatibility_reason", "reason", "rationale")):
            trace["canonical_memo_reason"] = reason
        patch = {"agent_trace": trace}
        if memo is not None:
            patch["investment_memo_markdown"] = memo
        return LegacyProjectionPatch(startup_id, patch)

    if event in {"opportunity.workflow_changed", "workflow_action.created", "workflow_action.approved"}:
        workflow = {**canonical, "canonical_workflow_event": event}
        for key in ("workflow_state", "workflow_version", "block_code"):
            if payload.get(key) is not None:
                workflow[f"canonical_{key}"] = payload[key]
        if (reason := _optional_text(payload, "compatibility_reason", "reason", "rationale")):
            workflow["canonical_workflow_reason"] = reason
        return LegacyProjectionPatch(startup_id, {"agent_trace": {"authority_projection": workflow}})

    return None


def is_authority_projection_event(event_type: str) -> bool:
    return str(event_type or "").strip() in {
        "observation_resolved",
        "identity_case.resolved",
        "identity.resolved",
        "evaluation.completed",
        "evaluation.created",
        "recommendation.created",
        "recommendation.updated",
        "human_ruling.created",
        "memo.created",
        "memo.generated",
        "investment_memo.created",
        "opportunity.workflow_changed",
        "workflow_action.created",
        "workflow_action.approved",
    }


def _projection_hash(patch: LegacyProjectionPatch) -> str:
    encoded = json.dumps(
        {"startup_id": patch.startup_id, "patch": patch.patch},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


class AuthorityProjectionConsumer:
    """Receipt-first, tenant-scoped consumer over an atomic projection repository."""

    def __init__(
        self,
        repository: Any,
        *,
        consumer: str = COMPATIBILITY_CONSUMER,
        authority_service: Any = None,
    ):
        self.repository = repository
        self.consumer = consumer
        self.authority_service = authority_service

    async def apply(
        self,
        *,
        user_id: str,
        event_id: str,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> ProjectionReceipt | Any | None:
        uid = require_user_id(user_id, context="AuthorityProjectionConsumer.apply")
        if self.authority_service is not None:
            authority = await self.authority_service.authority(user_id=uid)
            if not authority.legacy_projection_allowed:
                return None
        if not isinstance(payload, Mapping):
            raise ValueError("authority event payload must be an object")
        embedded_user_id = _optional_text(payload, "user_id")
        if embedded_user_id and embedded_user_id != uid:
            raise ProjectionTenantMismatch("authority event payload tenant mismatch")
        patch = legacy_patch_for_event(event_type, payload)
        if patch is None:
            if is_authority_projection_event(event_type):
                raise UnresolvedLegacyProjection(
                    "authority event has no resolvable legacy startup projection"
                )
            return None
        existing = await self.repository.get_projection_receipt(
            user_id=uid, event_id=str(event_id), consumer=self.consumer
        )
        if existing is not None:
            return existing
        # The repository operation owns the one database transaction: it claims
        # the unique receipt and applies *only* this display patch, rolling both
        # back if either step fails.
        return await self.repository.apply_legacy_projection(
            user_id=uid,
            event_id=str(event_id),
            consumer=self.consumer,
            aggregate_type=str(aggregate_type),
            aggregate_id=str(aggregate_id),
            patch=patch,
            projection_hash=_projection_hash(patch),
        )

    async def replay(
        self,
        *,
        user_id: str,
        event_id: str | None = None,
        opportunity_id: str | None = None,
    ) -> int:
        uid = require_user_id(user_id, context="AuthorityProjectionConsumer.replay")
        if event_id:
            event = await self.repository.get_outbox_event(user_id=uid, event_id=str(event_id))
            events = [] if event is None else [event]
        else:
            events = await self.repository.list_pending_authority_events(
                user_id=uid, opportunity_id=opportunity_id
            )
        applied = 0
        for event in events:
            existing = await self.repository.get_projection_receipt(
                user_id=uid,
                event_id=str(event.event_id),
                consumer=self.consumer,
            )
            if existing is not None:
                continue
            receipt = await self.apply(
                user_id=event.user_id,
                event_id=event.event_id,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                event_type=event.event_type,
                payload=event.payload,
            )
            if receipt is not None:
                applied += 1
        return applied
