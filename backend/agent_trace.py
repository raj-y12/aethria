"""Structured agent handoff trace and deterministic quality gates.

This module is intentionally pure: no storage, network, or LLM calls. It turns
existing scout/reviewer/partner artifacts into a compact audit trail that can be
embedded on a startup row.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse
from uuid import uuid4

from utils.reference_verify import extract_http_urls


_MISSING_LABELS = {
    "founding_team": ("missing founding team", "team missing", "founder missing"),
    "traction": ("missing revenue", "missing traction", "revenue or traction"),
    "competitors": ("competitive landscape unclear", "missing competitors"),
    "valuation": ("missing valuation", "valuation data"),
}
_SERIOUS_FLAGS = {
    "weak_sources",
    "missing_evidence",
    "contested_review",
    "low_signal_confidence",
    "thesis_mismatch",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except Exception:
            return {}
    return {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _settings_fund_config(settings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(settings, dict):
        return {}
    fc = settings.get("fund_config")
    return fc if isinstance(fc, dict) else {}


def _thresholds(settings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    fc = _settings_fund_config(settings)
    raw = fc.get("thresholds")
    return raw if isinstance(raw, dict) else {}


def _risk_policy(settings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    fc = _settings_fund_config(settings)
    raw = fc.get("risk")
    return raw if isinstance(raw, dict) else {}


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _status_from(flags: Iterable[str], blocking: Optional[List[str]] = None) -> str:
    if blocking:
        return "blocked"
    flag_set = set(flags)
    if flag_set & _SERIOUS_FLAGS:
        return "needs_attention"
    if flag_set:
        return "warning"
    return "ok"


def build_evidence_coverage(
    references: Any,
    source_evidence: Any = None,
    gap_reference_urls: Optional[List[str]] = None,
    structured_signals: Any = None,
) -> Dict[str, Any]:
    refs = [str(r).strip() for r in _as_list(references) if str(r).strip()]
    src_ev = [e for e in _as_list(source_evidence) if isinstance(e, dict)]
    gap_urls = [str(u).strip() for u in (gap_reference_urls or []) if str(u).strip()]
    urls: List[str] = []
    for ref in refs:
        urls.extend(extract_http_urls(ref))
    for item in src_ev:
        url = str(item.get("url") or "").strip()
        if url:
            urls.append(url)
    urls.extend(gap_urls)

    hosts: List[str] = []
    for url in urls:
        try:
            host = (urlparse(url).hostname or "").lower().strip(".")
        except Exception:
            host = ""
        if host and host not in hosts:
            hosts.append(host)

    support_labels = sorted(
        {
            str(item.get("supports") or "").strip()
            for item in src_ev
            if str(item.get("supports") or "").strip()
        }
    )
    if gap_urls:
        support_labels.append("Reviewer gap retrieval")

    low_signal_components = _low_confidence_components(structured_signals)
    return {
        "source_count": len(refs),
        "verified_url_count": len({u for u in urls if u}),
        "source_hosts": hosts[:12],
        "support_labels": support_labels[:12],
        "gap_reference_count": len(gap_urls),
        "low_signal_components": low_signal_components[:20],
        "weak_sources": len(refs) < 2 or len({u for u in urls if u}) < 1,
    }


def _low_confidence_components(structured_signals: Any, threshold: float = 0.25) -> List[str]:
    out: List[str] = []
    if not isinstance(structured_signals, dict):
        return out
    for dim, comps in structured_signals.items():
        if not isinstance(comps, dict):
            continue
        for name, cell in comps.items():
            if not isinstance(cell, dict):
                continue
            if _float(cell.get("confidence"), 1.0) <= threshold:
                out.append(f"{dim}.{name}")
    return out


def build_scout_trace(
    scout_output: Any,
    *,
    pipeline_run_id: Optional[str],
    active_thesis: Optional[Dict[str, Any]] = None,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    scout = _as_dict(scout_output)
    evidence = build_evidence_coverage(
        scout.get("references"),
        scout.get("source_evidence"),
    )
    flags: List[str] = []
    warnings: List[str] = []
    if evidence["weak_sources"]:
        flags.append("weak_sources")
        warnings.append("Fewer than two source references or no URL evidence.")
    floor = _float(_thresholds(settings).get("confidenceFloor"), 0.55)
    confidence = _float(scout.get("confidence", scout.get("confidence_score")), 0.5)
    if confidence < floor:
        flags.append("low_scout_confidence")
        warnings.append(f"Scout confidence {confidence:.2f} is below floor {floor:.2f}.")
    if scout.get("origin_type") == "on_demand_lookup" and not active_thesis:
        flags.append("no_active_thesis_for_on_demand_lookup")
        warnings.append("On-demand lookup ran without active thesis gating.")
    missing_evidence: List[str] = []
    resolution_summary: Optional[Dict[str, Any]] = None
    resolution = scout.get("company_resolution")
    resolution_status = scout.get("resolution_status")
    if isinstance(resolution, dict) or resolution_status:
        res = resolution if isinstance(resolution, dict) else {}
        status = str(resolution_status or res.get("resolution_status") or "")
        missing_evidence = [str(m) for m in (res.get("missing_fields") or [])]
        if status and status != "FOUND":
            flags.append(f"resolution_{status.lower()}")
            warnings.append(
                f"Company Resolver status {status}"
                + (f"; missing: {', '.join(missing_evidence)}" if missing_evidence else "")
                + "."
            )
        resolution_summary = {
            "status": status or None,
            "confidence": _float(res.get("confidence"), 0.0) if res else None,
            "website": res.get("website"),
            "linkedin_url": res.get("linkedin_url"),
            "crunchbase_url": res.get("crunchbase_url"),
            "queries_used": list(res.get("queries_used") or [])[:12],
            "evidence_source_count": len(res.get("evidence_sources") or []),
            "missing_fields": missing_evidence,
            "alternative_match_count": len(res.get("alternative_matches") or []),
        }
    trace = {
        "stage": "scout",
        "scout_run_id": str(uuid4()),
        "scout_model": scout.get("model"),
        "scout_prompt_version": scout.get("prompt_version"),
        "status": "completed",
        "pipeline_run_id": pipeline_run_id,
        "recorded_at": _now_iso(),
        "inputs_summary": {
            "name": scout.get("name"),
            "scout_type": scout.get("scout_type"),
            "origin_type": scout.get("origin_type"),
            "thesis_version_id": active_thesis.get("version_id") if active_thesis else None,
        },
        "evidence_coverage": evidence,
        "quality": {
            "status": "warning" if flags else "ok",
            "confidence": confidence,
            "quality_flags": flags,
            "blocking_issues": [],
            "warnings": warnings,
            "missing_evidence": missing_evidence,
            "conflicts": [],
        },
    }
    if resolution_summary is not None:
        trace["resolution"] = resolution_summary
    return trace


def build_review_trace(
    review_output: Any,
    *,
    scout: Any,
    pipeline_run_id: Optional[str],
    gap_reference_urls: Optional[List[str]] = None,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    review = _as_dict(review_output)
    scout_dict = _as_dict(scout)
    evidence = build_evidence_coverage(
        scout_dict.get("references"),
        scout_dict.get("source_evidence"),
        gap_reference_urls=gap_reference_urls,
        structured_signals=review.get("structured_signals"),
    )
    missing = _missing_evidence_from_review(review)
    flags: List[str] = []
    warnings: List[str] = []
    conflicts: List[str] = []
    if evidence["weak_sources"]:
        flags.append("weak_sources")
    if missing:
        flags.append("missing_evidence")
        warnings.append("Reviewer identified missing critical evidence.")
    if bool(review.get("reviewer_disagreement")):
        flags.append("contested_review")
        conflicts.append("Reviewer personas disagreed.")
    if _score_variance_conflict(review.get("score_variance")):
        flags.append("score_variance")
        conflicts.append("Reviewer score variance exceeded materiality threshold.")
    if evidence["low_signal_components"]:
        flags.append("low_signal_confidence")
        warnings.append("Structured scoring contains low-confidence evidence components.")
    if review.get("thesis_matches_fund") is False or _float(review.get("thesis_alignment_score"), 1.0) < 0.3:
        flags.append("thesis_mismatch")
        conflicts.append("Review indicates low fund thesis alignment.")

    context_claim_ids: set[str] = set()
    contexts = _as_dict(_as_dict(review.get("canonical_context_snapshot")).get("contexts"))
    for packet in contexts.values():
        context = _as_dict(packet)
        for claim in _as_list(context.get("claims") or context.get("current_supported_claims")):
            if _as_dict(claim).get("claim_id"):
                context_claim_ids.add(str(claim["claim_id"]))
    confidence = _review_confidence(review, evidence)
    handoff = {
        "status": _status_from(flags),
        "quality_flags": sorted(set(flags)),
        "missing_evidence": missing,
        "conflicts": conflicts,
        "confidence": confidence,
        "human_review_recommended": bool(set(flags) & _SERIOUS_FLAGS),
    }
    return {
        "stage": "reviewer",
        "reviewer_run_id": str(uuid4()),
        "canonical_context_claim_ids": sorted(context_claim_ids),
        "reviewer_model": review.get("model"),
        "reviewer_prompt_version": review.get("prompt_version"),
        "reviewer_prompt_versions": [
            item.get("prompt_version")
            for item in _as_list(review.get("reviews")) if isinstance(item, dict)
        ],
        "score_origin": review.get("score_origin") or "UNKNOWN_LEGACY",
        "legacy_scores": {
            key: review.get(key) for key in (
                "market_score", "product_score", "technical_score",
                "execution_score", "defensibility_score", "confidence_adjusted_score",
            )
        },
        "policy_version_id": review.get("policy_version_id"),
        "policy_hash": review.get("policy_hash"),
        "evaluation_rubric_version": review.get("rubric_version"),
        "status": "completed",
        "pipeline_run_id": pipeline_run_id,
        "recorded_at": _now_iso(),
        "inputs_summary": {
            "verdict": review.get("verdict"),
            "derived_verdict": review.get("derived_verdict"),
            "consensus_verdict": review.get("consensus_verdict"),
            "reviewer_disagreement": bool(review.get("reviewer_disagreement")),
        },
        "evidence_coverage": evidence,
        "quality": {
            **handoff,
            "blocking_issues": [],
            "warnings": warnings,
        },
        "handoff_quality": handoff,
        "settings_policy": {
            "missingDataThreshold": _thresholds(settings).get("missingDataThreshold"),
            "risk": _risk_policy(settings),
        },
    }


def build_partner_trace(
    partner_output: Any,
    *,
    scout: Any,
    review: Any,
    pipeline_run_id: Optional[str],
    handoff_quality: Optional[Dict[str, Any]] = None,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    partner = _as_dict(partner_output)
    scout_dict = _as_dict(scout)
    review_dict = _as_dict(review)
    hq = handoff_quality if isinstance(handoff_quality, dict) else {}
    flags = sorted(set(_as_list(hq.get("quality_flags"))))
    missing = [str(x) for x in _as_list(hq.get("missing_evidence")) if str(x)]
    conflicts = [str(x) for x in _as_list(hq.get("conflicts")) if str(x)]
    human_review = bool(partner.get("human_review_required")) or bool(hq.get("human_review_recommended"))
    quality = {
        "status": "needs_attention" if human_review or flags else "ok",
        "confidence": _float(partner.get("confidence"), 0.5),
        "quality_flags": flags,
        "blocking_issues": [],
        "warnings": ["Partner decision carries quality-gate escalation."] if human_review and flags else [],
        "missing_evidence": missing,
        "conflicts": conflicts,
        "human_review_recommended": human_review,
    }
    return {
        "stage": "partner",
        "partner_run_id": str(uuid4()),
        "partner_prompt_version": partner.get("prompt_version"),
        "provenance": partner.get("provenance"),
        "recommendation_origin": (
            _as_dict(partner.get("provenance")).get("recommendation_origin")
            or "UNKNOWN_LEGACY"
        ),
        "status": "completed",
        "pipeline_run_id": pipeline_run_id,
        "recorded_at": _now_iso(),
        "inputs_summary": {
            "recommendation": partner.get("recommendation"),
            "confidence": partner.get("confidence"),
            "human_review_required": human_review,
            "decision_drivers": partner.get("decision_drivers") or [],
        },
        "quality": quality,
        "explainability": _build_explainability(
            partner,
            scout_dict,
            review_dict,
            hq,
            settings,
        ),
    }


def merge_stage_trace(
    existing_trace: Optional[Dict[str, Any]],
    stage_key: str,
    stage_trace: Dict[str, Any],
) -> Dict[str, Any]:
    trace = dict(existing_trace or {})
    trace["version"] = str(trace.get("version") or "1")
    trace[stage_key] = stage_trace
    trace["updated_at"] = _now_iso()
    return trace


def handoff_quality_from_trace(agent_trace: Any) -> Dict[str, Any]:
    trace = agent_trace if isinstance(agent_trace, dict) else {}
    merged = {
        "status": "ok",
        "quality_flags": [],
        "missing_evidence": [],
        "conflicts": [],
        "confidence": None,
        "human_review_recommended": False,
    }
    for key in ("scout", "reviewer"):
        stage = trace.get(key)
        if not isinstance(stage, dict):
            continue
        q = stage.get("handoff_quality") if isinstance(stage.get("handoff_quality"), dict) else stage.get("quality")
        if not isinstance(q, dict):
            continue
        merged["quality_flags"].extend(str(x) for x in _as_list(q.get("quality_flags")) if str(x))
        merged["missing_evidence"].extend(str(x) for x in _as_list(q.get("missing_evidence")) if str(x))
        merged["conflicts"].extend(str(x) for x in _as_list(q.get("conflicts")) if str(x))
        merged["human_review_recommended"] = bool(merged["human_review_recommended"] or q.get("human_review_recommended"))
        conf = q.get("confidence")
        if isinstance(conf, (int, float)):
            current = merged.get("confidence")
            merged["confidence"] = float(conf) if current is None else min(float(current), float(conf))
    merged["quality_flags"] = sorted(set(merged["quality_flags"]))
    merged["missing_evidence"] = sorted(set(merged["missing_evidence"]))
    merged["conflicts"] = sorted(set(merged["conflicts"]))
    merged["status"] = _status_from(merged["quality_flags"])
    if merged["status"] == "needs_attention":
        merged["human_review_recommended"] = True
    return merged


def _missing_evidence_from_review(review: Dict[str, Any]) -> List[str]:
    texts: List[str] = []
    for key in ("diligence_red_flags", "key_risks"):
        texts.extend(str(x).lower() for x in _as_list(review.get(key)))
    blob = " ".join(texts)
    missing = []
    for label, phrases in _MISSING_LABELS.items():
        if any(p in blob for p in phrases):
            missing.append(label)
    return missing


def _score_variance_conflict(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return any(_float(v, 0.0) >= 4.0 for v in raw.values())


def _review_confidence(review: Dict[str, Any], evidence: Dict[str, Any]) -> float:
    vals: List[float] = []
    for key in (
        "thesis_alignment_confidence",
        "confidence_adjusted_score",
    ):
        v = review.get(key)
        if isinstance(v, (int, float)):
            vals.append(float(v) / 10.0 if key == "confidence_adjusted_score" and float(v) > 1 else float(v))
    if evidence["low_signal_components"]:
        vals.append(0.35)
    if evidence["weak_sources"]:
        vals.append(0.45)
    return round(max(0.0, min(1.0, min(vals) if vals else 0.6)), 4)


def _build_explainability(
    partner: Dict[str, Any],
    scout: Dict[str, Any],
    review: Dict[str, Any],
    handoff_quality: Dict[str, Any],
    settings: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    recommendation = str(partner.get("recommendation") or "MONITOR")
    drivers = [str(x) for x in _as_list(partner.get("decision_drivers")) if str(x)]
    flags = [str(x) for x in _as_list(handoff_quality.get("quality_flags")) if str(x)]
    thesis = str(scout.get("primary_thesis") or scout.get("one_line") or "").strip()
    score_reasoning = review.get("score_reasoning") if isinstance(review.get("score_reasoning"), dict) else {}
    thresholds = _thresholds(settings)
    summary_parts = [f"{recommendation} recommendation"]
    if drivers:
        summary_parts.append(f"driven by {', '.join(drivers[:4])}")
    if flags:
        summary_parts.append(f"quality flags: {', '.join(sorted(set(flags))[:4])}")
    if thesis:
        summary_parts.append(f"scout thesis: {thesis[:160]}")
    return {
        "summary": "; ".join(summary_parts) + ".",
        "scout_thesis": thesis or None,
        "review_score_reasoning": score_reasoning,
        "reviewer_disagreement": bool(review.get("reviewer_disagreement")),
        "thesis_alignment_score": review.get("thesis_alignment_score"),
        "decision_drivers": drivers,
        "quality_flags": sorted(set(flags)),
        "settings_thresholds": {
            k: thresholds.get(k)
            for k in ("autoPass", "monitor", "escalation", "partnerReview", "confidenceFloor", "missingDataThreshold")
            if k in thresholds
        },
    }
