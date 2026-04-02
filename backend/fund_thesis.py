"""
Supabase-backed fund thesis: one thesis document per user, versioned content, strict active resolver.
get_active_thesis persists a default thesis on first access (no in-memory-only fallback).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from tenant_context import require_user_id

logger = logging.getLogger(__name__)

# Deterministic bootstrap mandate (no LLM). Shallow-copied when persisting.
DEFAULT_THESIS_PARSED_JSON: Dict[str, Any] = {
    "sectors": ["B2B SaaS", "Infrastructure", "Developer Tools"],
    "stage_focus": ["Seed", "Series A"],
    "geography": ["US", "Europe"],
    "preferences": [
        "technical founders",
        "capital efficient",
        "high defensibility",
    ],
    "exclusions": [
        "consumer social",
        "speculative crypto",
        "low defensibility ideas",
    ],
    "risk_profile": "moderate",
    "is_default": True,
}


def generate_default_thesis_raw_text() -> str:
    """Canonical default mandate for new tenants (persisted to Supabase, not a runtime stub)."""
    return (
        "We invest in early-stage B2B SaaS and infrastructure startups.\n"
        "Focus on Seed to Series A.\n"
        "Geography: US and Europe.\n"
        "We prioritize strong technical founders and capital-efficient growth.\n"
        "We avoid speculative crypto, consumer social, and low-defensibility ideas.\n"
    )


class FundThesisError(Exception):
    """Base error for thesis resolution or mutation."""


class FundThesisMissingError(FundThesisError):
    """No fund thesis row or no active version for this user."""


class FundThesisIncompleteError(FundThesisError):
    """Reserved for rare integrity failures; never raised for missing embeddings."""


@dataclass(frozen=True)
class ActiveThesis:
    thesis_id: str
    version_id: str
    version_number: int
    raw_text: str
    parsed_json: Dict[str, Any]
    embedding: List[float]
    embedding_model: str

    def as_engine_context(self) -> Dict[str, Any]:
        emb = list(self.embedding or [])
        has_vec = bool(emb)
        model = self.embedding_model if has_vec and (self.embedding_model or "").strip() not in ("", "none") else "none"
        if not has_vec:
            emb = []
            model = "none"
        mode = "embedding" if has_vec else "rule_based"
        return {
            "thesis_id": self.thesis_id,
            "version_id": self.version_id,
            "version_number": self.version_number,
            "raw_text": self.raw_text,
            "parsed_json": dict(self.parsed_json or {}),
            "embedding": emb,
            "embedding_model": model,
            "alignment_mode": mode,
        }


def thesis_has_embeddings(thesis: ActiveThesis) -> bool:
    """True only when a non-empty embedding vector is present (AI-enhanced alignment path)."""
    emb = getattr(thesis, "embedding", None) or []
    return isinstance(emb, list) and len(emb) > 0


def thesis_context_has_embeddings(ctx: Optional[Dict[str, Any]]) -> bool:
    """Engine context dict from ActiveThesis.as_engine_context(); same semantics as thesis_has_embeddings."""
    if not isinstance(ctx, dict):
        return False
    emb = ctx.get("embedding") or []
    return isinstance(emb, list) and len(emb) > 0


RULE_ALIGNMENT_MATCH_THRESHOLD = 6  # 0–10 scale; matches thesis_matches_fund when score >= this
RULE_ALIGNMENT_LOW_CONFIDENCE = 0.25  # 0–1 stored in ReviewInfo when rule-based (no embeddings)


def _as_lower_str_list(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip().lower() for x in v if str(x).strip()]
    if isinstance(v, str) and v.strip():
        return [v.strip().lower()]
    return []


def _scout_text_blob(scout_output: Dict[str, Any]) -> str:
    parts = [
        scout_output.get("name"),
        scout_output.get("one_line"),
        scout_output.get("sector"),
        scout_output.get("problem"),
        scout_output.get("solution"),
        scout_output.get("target_users"),
        scout_output.get("why_now"),
    ]
    return " ".join(str(p) for p in parts if p).lower()


def _stage_normalized(s: Optional[str]) -> str:
    t = (s or "").strip().lower().replace("–", "-").replace("—", "-")
    t = " ".join(t.split())
    return t


def rule_based_thesis_alignment(
    scout_output: Dict[str, Any],
    parsed_json: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Lightweight mandate fit without embeddings or external APIs.
    Returns keys compatible with reviewer_output / ReviewInfo (thesis_alignment_score is 0–1).
    """
    blob = _scout_text_blob(scout_output)
    sectors = _as_lower_str_list(parsed_json.get("sectors"))
    stages = _as_lower_str_list(parsed_json.get("stage_focus"))
    geos = _as_lower_str_list(parsed_json.get("geography"))
    exclusions = _as_lower_str_list(parsed_json.get("exclusions"))
    preferences = _as_lower_str_list(parsed_json.get("preferences"))

    score = 0
    fit: List[str] = []
    dev: List[str] = []

    sector_hit = False
    startup_sector = _stage_normalized(str(scout_output.get("sector") or ""))
    for ts in sectors:
        if not ts:
            continue
        if ts in blob or (startup_sector and (ts in startup_sector or startup_sector in ts)):
            sector_hit = True
            break
    if sector_hit:
        score += 2
        fit.append("Sector overlaps fund thesis targets")
    else:
        dev.append("Sector not clearly in thesis target list")

    stage_raw = scout_output.get("funding_stage")
    st = _stage_normalized(str(stage_raw) if stage_raw is not None else "")
    stage_hit = False
    for tf in stages:
        if not tf:
            continue
        if st and (tf == st or tf in st or st in tf):
            stage_hit = True
            break
    if stage_hit:
        score += 2
        fit.append("Funding stage aligns with thesis stage focus")
    elif st:
        dev.append(f"Stage ({stage_raw}) may be outside thesis stage focus")
    else:
        dev.append("Funding stage unknown vs thesis stage focus")

    geo_aliases = {"us": ["us", "u.s", "united states", "america"], "europe": ["europe", "eu", "uk", "u.k", "emea"]}
    geo_hit = False
    for g in geos:
        if not g:
            continue
        keys = geo_aliases.get(g, [g])
        if any(k in blob for k in keys):
            geo_hit = True
            break
    if geo_hit:
        score += 1
        fit.append("Geography or GTM hints match thesis regions")
    else:
        dev.append("Geography fit unclear vs thesis regions")

    for ex in exclusions:
        if ex and ex in blob:
            score -= 3
            dev.append(f"Possible thesis exclusion match: {ex}")

    pref_hit = False
    for pref in preferences:
        if pref and pref in blob:
            pref_hit = True
            break
    if pref_hit:
        score += 1
        fit.append("Signals match stated thesis preferences")

    score = max(0, min(10, score))
    matches = score >= RULE_ALIGNMENT_MATCH_THRESHOLD
    normalized = round(score / 10.0, 4)

    if not fit:
        fit.append("Rule-based scan: limited explicit matches in scout text")
    if not dev:
        dev.append("No major deviations flagged by rules")

    return {
        "thesis_alignment_score": normalized,
        "thesis_matches_fund": matches,
        "thesis_fit_points": fit[:12],
        "thesis_deviation_points": dev[:12],
        "thesis_alignment_confidence": RULE_ALIGNMENT_LOW_CONFIDENCE,
    }


def _resolve_active_thesis_unsafe(client: Any, uid: str) -> ActiveThesis:
    """
    Load active thesis for uid (already validated).
    Missing or empty embeddings resolve to [] (pipeline still runs); see TODO for async enrichment.
    """
    try:
        tr = (
            client.table("fund_thesis")
            .select("id,active_version_id")
            .eq("user_id", uid)
            .limit(1)
            .execute()
        )
    except Exception as e:
        logger.warning("get_active_thesis fund_thesis query failed: %s", e)
        raise FundThesisMissingError("fund_thesis query failed") from e

    rows = getattr(tr, "data", None) or []
    if not rows:
        raise FundThesisMissingError("no fund_thesis row for user")
    thesis_id = str(rows[0].get("id") or "").strip()
    av = rows[0].get("active_version_id")
    version_id = str(av).strip() if av else ""
    if not thesis_id or not version_id:
        raise FundThesisMissingError("no active_version_id on fund_thesis")

    try:
        vr = (
            client.table("fund_thesis_versions")
            .select("id,thesis_id,version_number,raw_text,parsed_json,is_active,user_id")
            .eq("id", version_id)
            .eq("user_id", uid)
            .limit(1)
            .execute()
        )
    except Exception as e:
        logger.warning("get_active_thesis version query failed: %s", e)
        raise FundThesisMissingError("fund_thesis_versions query failed") from e

    vrows = getattr(vr, "data", None) or []
    if not vrows:
        raise FundThesisMissingError("active version row not found")
    v = vrows[0]
    if str(v.get("thesis_id") or "") != thesis_id:
        raise FundThesisMissingError("version does not belong to thesis")
    vn = v.get("version_number")
    try:
        version_number = int(vn) if vn is not None else 0
    except (TypeError, ValueError):
        version_number = 0
    raw_text = str(v.get("raw_text") or "")
    pj = v.get("parsed_json")
    parsed_json: Dict[str, Any] = pj if isinstance(pj, dict) else {}

    embedding: List[float] = []
    model = "none"
    try:
        er = (
            client.table("fund_thesis_embeddings")
            .select("embedding_vector,model,user_id,version_id")
            .eq("version_id", version_id)
            .eq("user_id", uid)
            .limit(1)
            .execute()
        )
    except Exception as e:
        logger.warning("get_active_thesis embedding query failed (continuing without vector): %s", e)
        embedding = []
        model = "none"
    else:
        erows = getattr(er, "data", None) or []
        if not erows:
            # TODO: enqueue background job to generate embedding when row missing
            embedding = []
            model = "none"
        else:
            ev = erows[0].get("embedding_vector")
            model = str(erows[0].get("model") or "none")
            if isinstance(ev, list):
                for x in ev:
                    try:
                        embedding.append(float(x))
                    except (TypeError, ValueError):
                        continue
            elif isinstance(ev, dict) and "values" in ev:
                for x in ev.get("values") or []:
                    try:
                        embedding.append(float(x))
                    except (TypeError, ValueError):
                        continue
            if not embedding:
                # TODO: background job to backfill embeddings when OPENAI_API_KEY becomes available
                model = "none"

    # Guarantee safe defaults: no vector → empty list + model "none"
    if not embedding:
        embedding = []
        model = "none"

    return ActiveThesis(
        thesis_id=thesis_id,
        version_id=version_id,
        version_number=version_number,
        raw_text=raw_text,
        parsed_json=parsed_json,
        embedding=embedding,
        embedding_model=model or "none",
    )


def _bootstrap_default_thesis_or_raise(client: Any, uid: str) -> None:
    """
    Persist first thesis + version without OpenAI (hardcoded parsed_json, no embedding API).
    Idempotent with concurrent get_active_thesis.
    """
    from fund_thesis_ops import create_fund_thesis_version_for_user

    raw = generate_default_thesis_raw_text()
    try:
        create_fund_thesis_version_for_user(
            client,
            user_id=uid,
            raw_text=raw,
            api_key="",
            parsed_json_override=dict(DEFAULT_THESIS_PARSED_JSON),
            skip_embedding=True,
            pipeline_run_id=None,
        )
    except Exception as e:
        try:
            _resolve_active_thesis_unsafe(client, uid)
        except (FundThesisMissingError, FundThesisIncompleteError):
            logger.exception(
                "[FundThesis] Auto-create default thesis failed for user_id=%s",
                uid[:24],
            )
            raise FundThesisMissingError(f"default thesis bootstrap failed: {e}") from e
        logger.info(
            "[FundThesis] Default thesis created by concurrent request; resolved for user_id=%s",
            uid[:24],
        )
        return

    logger.info("[FundThesis] Auto-created default thesis for user_id=%s", uid[:24])


def get_active_thesis(client: Any, user_id: str) -> ActiveThesis:
    """
    Resolve fund_thesis row and active version from Supabase. Embeddings optional ([] if absent).

    On FundThesisMissingError only: persists a deterministic default thesis (no OpenAI), then returns it.
    """
    uid = require_user_id(user_id, context="get_active_thesis")
    try:
        return _resolve_active_thesis_unsafe(client, uid)
    except FundThesisMissingError:
        try:
            return _resolve_active_thesis_unsafe(client, uid)
        except FundThesisMissingError:
            pass
        _bootstrap_default_thesis_or_raise(client, uid)
        return _resolve_active_thesis_unsafe(client, uid)


def count_user_startups(client: Any, user_id: str) -> int:
    uid = require_user_id(user_id, context="count_user_startups")
    try:
        r = (
            client.table("startups")
            .select("startup_id", count="exact")
            .eq("user_id", uid)
            .limit(1)
            .execute()
        )
        return int(getattr(r, "count", None) or 0)
    except Exception as e:
        logger.warning("count_user_startups failed: %s", e)
        return 0


def insert_thesis_pipeline_link(
    client: Any,
    *,
    user_id: str,
    thesis_version_id: str,
    pipeline_run_id: Optional[str],
    affected_startups_count: int = 0,
) -> None:
    uid = require_user_id(user_id, context="insert_thesis_pipeline_link")
    row: Dict[str, Any] = {
        "user_id": uid,
        "thesis_version_id": thesis_version_id.strip(),
        "affected_startups_count": max(0, int(affected_startups_count)),
    }
    pr = (pipeline_run_id or "").strip()
    if pr:
        row["pipeline_run_id"] = pr
    client.table("fund_thesis_pipeline_link").insert(row).execute()


def _review_thesis_fields(ri: Any) -> tuple[Optional[float], Optional[bool], Optional[str]]:
    if not isinstance(ri, dict):
        return None, None, None
    score_raw = ri.get("thesis_alignment_score")
    score: Optional[float] = None
    if score_raw is not None:
        try:
            score = float(score_raw)
        except (TypeError, ValueError):
            score = None
    matches = ri.get("thesis_matches_fund")
    if isinstance(matches, bool):
        mb = matches
    elif isinstance(matches, str):
        mb = matches.lower() in ("true", "1", "yes")
    else:
        mb = None
    vid = ri.get("fund_thesis_version_id")
    version_id = str(vid).strip() if vid else None
    return score, mb, version_id or None


def compute_thesis_alignment_stats(
    client: Any,
    user_id: str,
    *,
    active_version_id: str,
    previous_version_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Scan startups.review_info for thesis alignment fields (best-effort, bounded page size).
    """
    uid = require_user_id(user_id, context="compute_thesis_alignment_stats")
    active_version_id = active_version_id.strip()
    prev = (previous_version_id or "").strip() or None

    scores_active: List[float] = []
    scores_prev: List[float] = []
    match_active = 0
    total_active = 0
    try:
        r = (
            client.table("startups")
            .select("review_info")
            .eq("user_id", uid)
            .not_.is_("review_info", "null")
            .limit(2000)
            .execute()
        )
        rows = getattr(r, "data", None) or []
    except Exception as e:
        logger.warning("compute_thesis_alignment_stats failed: %s", e)
        return {
            "reviewed_with_thesis_count": 0,
            "pct_matching_thesis": None,
            "avg_alignment_score": None,
            "drift_vs_previous": None,
            "embedding_dimensions": None,
        }

    for row in rows:
        ri = row.get("review_info")
        score, matches, vid = _review_thesis_fields(ri)
        if vid != active_version_id:
            continue
        total_active += 1
        if score is not None:
            scores_active.append(score)
        if matches is True or (matches is None and score is not None and score >= 0.6):
            match_active += 1

    if prev:
        for row in rows:
            ri = row.get("review_info")
            score, _, vid = _review_thesis_fields(ri)
            if vid == prev and score is not None:
                scores_prev.append(score)

    pct = (100.0 * match_active / total_active) if total_active else None
    avg_a = sum(scores_active) / len(scores_active) if scores_active else None
    avg_p = sum(scores_prev) / len(scores_prev) if scores_prev else None
    drift = (avg_a - avg_p) if (avg_a is not None and avg_p is not None) else None

    return {
        "reviewed_with_thesis_count": total_active,
        "pct_matching_thesis": round(pct, 1) if pct is not None else None,
        "avg_alignment_score": round(avg_a, 3) if avg_a is not None else None,
        "drift_vs_previous": round(drift, 3) if drift is not None else None,
    }
