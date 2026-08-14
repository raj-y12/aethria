"""Versioned, provider-neutral projection for external CRM operations.

The projection is intentionally a current-state view. It contains stable
canonical IDs and bounded summaries, never raw prompt, claim-ledger, or agent
trace structures.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from tenant_context import require_user_id


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _state(value: Any) -> str | None:
    text = _text(value)
    return text.upper() if text else None


def _founder(value: Mapping[str, Any]) -> dict[str, Any]:
    status = _text(value.get("identity_status")) or ("resolved" if value.get("person_id") else "unresolved")
    return {
        "person_id": _text(value.get("person_id")),
        "name": _text(value.get("name") or value.get("canonical_name")),
        "current_role": _text(value.get("current_role") or value.get("role")),
        "relevant_prior_experience": [
            str(item).strip() for item in (value.get("relevant_prior_experience") or value.get("previous_employment") or [])
            if str(item).strip()
        ][:5],
        "identity_status": status,
    }


def build_crm_projection_v1(
    *,
    user_id: str,
    company: Mapping[str, Any],
    opportunity: Mapping[str, Any],
    recommendation: Mapping[str, Any] | None = None,
    ruling: Mapping[str, Any] | None = None,
    evaluation: Mapping[str, Any] | None = None,
    founders: Sequence[Mapping[str, Any]] = (),
    memo: Mapping[str, Any] | None = None,
    provenance: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    uid = require_user_id(user_id, context="build_crm_projection_v1")
    company_id = _text(company.get("company_id"))
    opportunity_id = _text(opportunity.get("opportunity_id"))
    if not company_id or not opportunity_id:
        raise ValueError("CRM projection requires canonical company_id and opportunity_id")

    selected_sources = []
    for source in provenance[:10]:
        url = _text(source.get("source_url") or source.get("source_uri"))
        if url:
            selected_sources.append({"url": url, "source_type": _text(source.get("source_type")) or "unknown"})

    rec = None
    if recommendation:
        rec = {
            "aethria_recommendation_id": _text(recommendation.get("recommendation_id")),
            "state": _state(recommendation.get("recommended_state") or recommendation.get("state")),
            "confidence": recommendation.get("confidence"),
            "strengths": [str(item).strip() for item in (recommendation.get("decision_drivers") or []) if str(item).strip()][:5],
            "risks": [str(item).strip() for item in (recommendation.get("principal_risks") or []) if str(item).strip()][:5],
        }
    human = None
    if ruling:
        human = {
            "aethria_ruling_id": _text(ruling.get("ruling_id")),
            "decision": _state(ruling.get("decision")),
            "recorded_at": _text(ruling.get("created_at")),
        }
    return {
        "schema_version": "crm_projection_v1",
        "tenant_id": uid,
        "company": {
            "aethria_company_id": company_id,
            "external_company_id": _text(company.get("external_company_id")),
            "name": _text(company.get("canonical_name")),
            "canonical_domain": _text(company.get("canonical_domain")),
            "sector": _text(company.get("sector")),
            "geography": _text(company.get("geography") or company.get("location")),
        },
        "opportunity": {
            "aethria_opportunity_id": opportunity_id,
            "external_opportunity_id": _text(opportunity.get("external_opportunity_id")),
            "workflow_status": _text(opportunity.get("workflow_state") or opportunity.get("decision_state")),
            "stage": _text(opportunity.get("stage")),
        },
        "founders": [_founder(item) for item in founders[:10]],
        "recommendation": rec,
        "human_ruling": human,
        "fund_fit": _text((recommendation or {}).get("thesis_alignment") or (recommendation or {}).get("fund_fit")),
        "evaluation": {
            "aethria_evaluation_id": _text((evaluation or {}).get("evaluation_id")),
            "completed_at": _text((evaluation or {}).get("completed_at") or (evaluation or {}).get("created_at")),
        } if evaluation else None,
        "memo": {
            "memo_id": _text((memo or {}).get("memo_id")),
            "reference": _text((memo or {}).get("url") or (memo or {}).get("reference")),
        } if memo else None,
        "provenance": {"source_count": len(selected_sources), "selected_sources": selected_sources},
        "last_updated_at": _text(opportunity.get("updated_at") or (evaluation or {}).get("completed_at")),
    }
