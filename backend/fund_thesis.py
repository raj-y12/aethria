"""
Supabase-backed fund thesis: one thesis document per user, versioned content, strict active resolver.
get_active_thesis persists a default thesis on first access (no in-memory-only fallback).
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from tenant_context import require_user_id
from utils.deal_context import scout_text_blob_lower

logger = logging.getLogger(__name__)
_TRANSIENT_ERRNOS = (35, 11)  # EAGAIN variants across platforms


def _is_transient_transport_error(err: Exception) -> bool:
    if isinstance(err, OSError) and getattr(err, "errno", None) in _TRANSIENT_ERRNOS:
        return True
    msg = str(err).lower()
    return "resource temporarily unavailable" in msg or "readerror" in msg

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
    """No fund thesis row or no active version for this user (definitely absent, not a query error)."""


class FundThesisQueryError(FundThesisError):
    """Transient or unexpected error while querying thesis tables; state is unknown."""


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
    thesis_updated_at: Optional[str] = None

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


# Known embedding dimensions, so the metadata path can report dimension without
# re-pulling the full embedding_vector (~1536 floats) from Supabase.
_EMBED_MODEL_DIMS: Dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


@dataclass(frozen=True)
class ActiveThesisMeta:
    """
    Lightweight resolved thesis: everything except the embedding_vector itself.
    Used by metadata-only callers (e.g. /api/fund-thesis/runtime) so the ~1536-float
    vector is never re-pulled when only mode / dimension / version info is needed.
    """
    thesis_id: str
    version_id: str
    version_number: int
    raw_text: str
    parsed_json: Dict[str, Any]
    has_embeddings: bool
    embedding_model: str
    embedding_dim: int
    thesis_updated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Per-request / per-cycle resolved-thesis cache.
#
# get_active_thesis() issues a 3-query triad (fund_thesis -> versions -> embeddings)
# and is called many times within seconds during a single pipeline cycle / lookup,
# and again on every /api/fund-thesis/runtime poll. The active thesis is immutable
# within such a window, so we collapse the burst with a short-TTL cache keyed by
# user_id. Mutations (create/activate version, bootstrap re-link) invalidate it,
# so staleness is bounded by TTL *and* cleared immediately on any write.
# ---------------------------------------------------------------------------
_thesis_cache_lock = threading.Lock()
_thesis_full_cache: Dict[str, Tuple[float, Optional["ActiveThesis"]]] = {}
_thesis_meta_cache: Dict[str, Tuple[float, Optional["ActiveThesisMeta"]]] = {}


def _thesis_cache_ttl() -> float:
    """Cache window in seconds (env-tunable). <= 0 disables caching entirely."""
    try:
        return float(os.getenv("FUND_THESIS_CACHE_TTL_SECONDS", "10"))
    except (TypeError, ValueError):
        return 10.0


def invalidate_thesis_cache(user_id: Optional[str] = None) -> None:
    """Drop cached thesis entries. Call after any thesis write. None clears all users."""
    with _thesis_cache_lock:
        if user_id:
            _thesis_full_cache.pop(user_id, None)
            _thesis_meta_cache.pop(user_id, None)
        else:
            _thesis_full_cache.clear()
            _thesis_meta_cache.clear()


def _meta_from_active(active: "ActiveThesis") -> "ActiveThesisMeta":
    has = thesis_has_embeddings(active)
    return ActiveThesisMeta(
        thesis_id=active.thesis_id,
        version_id=active.version_id,
        version_number=active.version_number,
        raw_text=active.raw_text,
        parsed_json=active.parsed_json,
        has_embeddings=has,
        embedding_model=active.embedding_model if has else "none",
        embedding_dim=len(active.embedding) if has else 0,
        thesis_updated_at=active.thesis_updated_at,
    )


def _cache_store_full(uid: str, value: Optional["ActiveThesis"]) -> None:
    # Never cache "missing" (None): it is rare, transient (pre-bootstrap), and caching
    # it would make a post-bootstrap re-resolve return a stale None.
    if value is None:
        return
    ttl = _thesis_cache_ttl()
    if ttl <= 0:
        return
    expires = time.monotonic() + ttl
    with _thesis_cache_lock:
        _thesis_full_cache[uid] = (expires, value)
        # A full resolve supersedes any cached metadata for the same window.
        _thesis_meta_cache[uid] = (expires, _meta_from_active(value))


def _cache_store_meta(uid: str, value: Optional["ActiveThesisMeta"]) -> None:
    if value is None:
        return
    ttl = _thesis_cache_ttl()
    if ttl <= 0:
        return
    with _thesis_cache_lock:
        _thesis_meta_cache[uid] = (time.monotonic() + ttl, value)


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
    return scout_text_blob_lower(scout_output)


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
    # An empty deviations list IS "no deviations". Padding it with a filler
    # sentence made every consumer treat the absence as content — the memo's
    # focal question rendered "Mandate gap to resolve: No major deviations
    # flagged by rules", directly under a "Mandate misaligned" banner.

    return {
        "thesis_alignment_score": normalized,
        "thesis_matches_fund": matches,
        "thesis_fit_points": fit[:12],
        "thesis_deviation_points": dev[:12],
        "thesis_alignment_confidence": RULE_ALIGNMENT_LOW_CONFIDENCE,
    }


STRUCTURED_THESIS_FIT_CATEGORIES = ("sector", "stage", "geography")


def compute_structured_thesis_fit(
    scout_output: Dict[str, Any], parsed_json: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Deterministic replacement for Scout's self-reported confidence (product
    decision, 2026-08-19): the model was asked to invent a bare 0-1 number
    with no rubric, so two identical companies could legitimately score
    differently between calls. This matches Scout's own structured fields
    (sector, funding_stage, location) against the mandate's structured
    categories (sectors, stage_focus, geography) -- no LLM judgment involved,
    same inputs always produce the same result.

    Scoped to 3 categories the mandate provides cleanly today. check_size /
    business_model / minimum_traction / ownership_target exist in the
    mandate too but Scout doesn't extract matching structured fields for
    them yet -- adding those as self-reported yes/no would just reintroduce
    the same self-report problem across more fields, so they're deliberately
    left out until Scout's extraction schema can back them for real.
    """
    sectors = _as_lower_str_list(parsed_json.get("sectors"))
    stages = _as_lower_str_list(parsed_json.get("stage_focus"))
    geos = _as_lower_str_list(parsed_json.get("geography"))

    startup_sector = _stage_normalized(str(scout_output.get("sector") or ""))
    sector_matched = bool(startup_sector) and any(
        ts and (ts in startup_sector or startup_sector in ts) for ts in sectors
    )

    stage_raw = scout_output.get("funding_stage")
    startup_stage = _stage_normalized(str(stage_raw) if stage_raw is not None else "")
    stage_matched = bool(startup_stage) and any(
        tf and (tf == startup_stage or tf in startup_stage or startup_stage in tf) for tf in stages
    )

    geo_aliases = {"us": ["us", "u.s", "united states", "america"], "europe": ["europe", "eu", "uk", "u.k", "emea"]}
    location = str(scout_output.get("location") or "").strip().lower()
    geo_matched = False
    if location:
        for g in geos:
            if not g:
                continue
            keys = geo_aliases.get(g, [g])
            if any(k in location for k in keys):
                geo_matched = True
                break

    results = [
        {"category": "sector", "matched": sector_matched},
        {"category": "stage", "matched": stage_matched},
        {"category": "geography", "matched": geo_matched},
    ]
    matched_count = sum(1 for r in results if r["matched"])
    return {
        "matched_categories": matched_count,
        "total_categories": len(STRUCTURED_THESIS_FIT_CATEGORIES),
        "category_results": results,
    }


def _resolve_thesis_version_unsafe(
    client: Any, uid: str
) -> Tuple[str, str, int, str, Dict[str, Any], Optional[str]]:
    """
    Resolve the active thesis version row (no embedding query).
    Shared by the full and metadata-only resolvers.
    Returns (thesis_id, version_id, version_number, raw_text, parsed_json, thesis_updated_at).
    """
    try:
        tr = (
            client.table("fund_thesis")
            .select("id,active_version_id,updated_at")
            .eq("user_id", uid)
            .limit(1)
            .execute()
        )
    except Exception as e:
        if _is_transient_transport_error(e):
            logger.debug("get_active_thesis fund_thesis transient failure: %s", e)
        else:
            logger.warning("get_active_thesis fund_thesis query failed: %s", e)
        raise FundThesisQueryError("fund_thesis query failed") from e

    rows = getattr(tr, "data", None) or []
    if not rows:
        raise FundThesisMissingError("no fund_thesis row for user")
    thesis_id = str(rows[0].get("id") or "").strip()
    av = rows[0].get("active_version_id")
    version_id = str(av).strip() if av else ""
    ua = rows[0].get("updated_at")
    thesis_updated_at = str(ua) if ua else None
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
        if _is_transient_transport_error(e):
            logger.debug("get_active_thesis version transient failure: %s", e)
        else:
            logger.warning("get_active_thesis version query failed: %s", e)
        raise FundThesisQueryError("fund_thesis_versions query failed") from e

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
    return thesis_id, version_id, version_number, raw_text, parsed_json, thesis_updated_at


def _resolve_active_thesis_meta_unsafe(client: Any, uid: str) -> ActiveThesisMeta:
    """
    Metadata-only resolve: never pulls embedding_vector. Selects just `model` from
    fund_thesis_embeddings to derive has_embeddings / dimension cheaply.
    """
    (
        thesis_id,
        version_id,
        version_number,
        raw_text,
        parsed_json,
        thesis_updated_at,
    ) = _resolve_thesis_version_unsafe(client, uid)

    model = "none"
    has_emb = False
    try:
        er = (
            client.table("fund_thesis_embeddings")
            .select("model")
            .eq("version_id", version_id)
            .eq("user_id", uid)
            .limit(1)
            .execute()
        )
    except Exception as e:
        if _is_transient_transport_error(e):
            logger.debug("get_active_thesis_metadata embedding transient failure: %s", e)
        else:
            logger.warning("get_active_thesis_metadata embedding query failed: %s", e)
        # Metadata is best-effort: a failed embedding-meta lookup degrades to rule_based.
        model = "none"
        has_emb = False
    else:
        erows = getattr(er, "data", None) or []
        if erows:
            model = str(erows[0].get("model") or "none")
            has_emb = model.strip().lower() not in ("", "none")
    if not has_emb:
        model = "none"
    dim = _EMBED_MODEL_DIMS.get(model, 0) if has_emb else 0

    return ActiveThesisMeta(
        thesis_id=thesis_id,
        version_id=version_id,
        version_number=version_number,
        raw_text=raw_text,
        parsed_json=parsed_json,
        has_embeddings=has_emb,
        embedding_model=model,
        embedding_dim=dim,
        thesis_updated_at=thesis_updated_at,
    )


def _resolve_active_thesis_unsafe(client: Any, uid: str) -> ActiveThesis:
    """
    Load active thesis for uid (already validated).
    Missing or empty embeddings resolve to [] (pipeline still runs); they are
    backfilled by fund_thesis_ops.ensure_active_thesis_embedding (pipeline hook)
    or backfill_thesis_embeddings (POST /api/fund-thesis/backfill-embeddings).
    """
    (
        thesis_id,
        version_id,
        version_number,
        raw_text,
        parsed_json,
        thesis_updated_at,
    ) = _resolve_thesis_version_unsafe(client, uid)

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
        if _is_transient_transport_error(e):
            logger.debug("get_active_thesis embedding transient failure (continuing without vector): %s", e)
        else:
            logger.warning("get_active_thesis embedding query failed (continuing without vector): %s", e)
        embedding = []
        model = "none"
    else:
        erows = getattr(er, "data", None) or []
        if not erows:
            # No embedding row yet — fund_thesis_ops backfill generates it when a
            # key is available (pipeline hook / backfill endpoint).
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
                # Stored vector was empty — fund_thesis_ops backfill will regenerate
                # it once OPENAI_API_KEY is available.
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
        thesis_updated_at=thesis_updated_at,
    )


def _bootstrap_default_thesis_or_raise(client: Any, uid: str) -> None:
    """
    Persist first thesis + version without OpenAI (hardcoded parsed_json, no embedding API).
    Fully idempotent: if versions already exist but active_version_id is null, re-links to the
    most recent version instead of creating a new one (prevents spurious version inflation).
    """
    from fund_thesis_ops import create_fund_thesis_version_for_user
    from datetime import datetime, timezone

    # Check current state before doing any writes.
    try:
        tr = client.table("fund_thesis").select("id,active_version_id").eq("user_id", uid).limit(1).execute()
        trows = getattr(tr, "data", None) or []
    except Exception as e:
        raise FundThesisMissingError(f"bootstrap fund_thesis query failed: {e}") from e

    if trows:
        thesis_id = str(trows[0].get("id") or "").strip()
        av = trows[0].get("active_version_id")
        active_vid = str(av).strip() if av else ""

        if thesis_id and active_vid:
            try:
                _resolve_active_thesis_unsafe(client, uid)
                logger.debug(
                    "[FundThesis] Bootstrap skipped; active thesis already resolvable for user_id=%s",
                    uid[:24],
                )
                return
            except FundThesisMissingError:
                logger.info(
                    "[FundThesis] active_version_id stale for user_id=%s; re-linking latest version",
                    uid[:24],
                )
                active_vid = ""

        if thesis_id:
            # Thesis row exists but no active_version_id — find the most recent version.
            try:
                vr = (
                    client.table("fund_thesis_versions")
                    .select("id,version_number")
                    .eq("thesis_id", thesis_id)
                    .eq("user_id", uid)
                    .order("version_number", desc=True)
                    .limit(1)
                    .execute()
                )
                vrows = getattr(vr, "data", None) or []
            except Exception as e:
                raise FundThesisMissingError(f"bootstrap versions query failed: {e}") from e

            if vrows:
                # Versions exist — re-link active_version_id without creating a new version.
                latest_vid = str(vrows[0]["id"])
                now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                try:
                    client.table("fund_thesis").update(
                        {"active_version_id": latest_vid, "updated_at": now_iso}
                    ).eq("id", thesis_id).eq("user_id", uid).execute()
                    invalidate_thesis_cache(uid)
                    logger.info("[FundThesis] Re-linked active_version_id to v%s for user_id=%s", vrows[0].get("version_number"), uid[:24])
                    return
                except Exception as e:
                    raise FundThesisMissingError(f"bootstrap re-link failed: {e}") from e

    # No fund_thesis row or no versions at all — create the default from scratch.
    # Re-check: a concurrent request may have created versions while we were deciding.
    try:
        tr2 = client.table("fund_thesis").select("id,active_version_id").eq("user_id", uid).limit(1).execute()
        trows2 = getattr(tr2, "data", None) or []
    except Exception as e:
        raise FundThesisMissingError(f"bootstrap fund_thesis re-check failed: {e}") from e
    if trows2:
        thesis_id2 = str(trows2[0].get("id") or "").strip()
        av2 = trows2[0].get("active_version_id")
        active_vid2 = str(av2).strip() if av2 else ""
        if thesis_id2 and active_vid2:
            try:
                _resolve_active_thesis_unsafe(client, uid)
                return
            except FundThesisMissingError:
                pass
        if thesis_id2:
            try:
                vr2 = (
                    client.table("fund_thesis_versions")
                    .select("id,version_number")
                    .eq("thesis_id", thesis_id2)
                    .eq("user_id", uid)
                    .order("version_number", desc=True)
                    .limit(1)
                    .execute()
                )
                vrows2 = getattr(vr2, "data", None) or []
            except Exception as e:
                raise FundThesisMissingError(f"bootstrap versions re-check failed: {e}") from e
            if vrows2:
                latest_vid = str(vrows2[0]["id"])
                now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                client.table("fund_thesis").update(
                    {"active_version_id": latest_vid, "updated_at": now_iso}
                ).eq("id", thesis_id2).eq("user_id", uid).execute()
                invalidate_thesis_cache(uid)
                logger.info(
                    "[FundThesis] Re-linked active_version_id after concurrent bootstrap for user_id=%s",
                    uid[:24],
                )
                return

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


async def bootstrap_default_thesis_with_repository(repository: Any, uid: str) -> None:
    """Bootstrap or repair the default thesis through the shared PostgreSQL repository."""
    from tenant_context import require_user_id

    user_id = require_user_id(uid, context="bootstrap_default_thesis_with_repository")
    result = await repository.ensure_default(
        user_id,
        raw_text=generate_default_thesis_raw_text(),
        parsed_json=dict(DEFAULT_THESIS_PARSED_JSON),
    )
    logger.info(
        "[FundThesis] PostgreSQL bootstrap user_id=%s version=%s skipped=%s",
        user_id[:24], result["version_number"], result["skipped"],
    )


def get_active_thesis(
    client: Any, user_id: str, *, use_cache: bool = True
) -> Optional[ActiveThesis]:
    """
    Resolve fund_thesis row and active version from Supabase (read-only).
    Returns None only when no thesis definitively exists for the user.
    Raises FundThesisQueryError on transient/unexpected DB errors so callers
    can distinguish "missing" from "unknown state" and avoid spurious bootstraps.
    Embeddings are optional ([] if absent).

    Results are cached per user for a short window (FUND_THESIS_CACHE_TTL_SECONDS)
    to collapse the redundant triad burst within one pipeline cycle / lookup; the
    cache is invalidated on any thesis write. Pass use_cache=False to force a read
    (e.g. immediately after a bootstrap, when staleness must not be tolerated).
    """
    uid = require_user_id(user_id, context="get_active_thesis")
    if use_cache and _thesis_cache_ttl() > 0:
        now = time.monotonic()
        with _thesis_cache_lock:
            hit = _thesis_full_cache.get(uid)
        if hit is not None and hit[0] > now:
            return hit[1]
    try:
        result: Optional[ActiveThesis] = _resolve_active_thesis_unsafe(client, uid)
    except FundThesisQueryError:
        raise  # never cache transient/unknown-state errors
    except FundThesisMissingError:
        result = None
    if use_cache:
        _cache_store_full(uid, result)
    return result


async def get_active_thesis_from_repository(
    repository: Any,
    user_id: str,
    *,
    use_cache: bool = True,
) -> Optional[ActiveThesis]:
    """Resolve the active thesis through a provider-neutral async repository."""
    uid = require_user_id(user_id, context="get_active_thesis_from_repository")
    if use_cache and _thesis_cache_ttl() > 0:
        now = time.monotonic()
        with _thesis_cache_lock:
            hit = _thesis_full_cache.get(uid)
        if hit is not None and hit[0] > now:
            return hit[1]

    row = await repository.get_active(uid, include_embedding=True)
    if row is None:
        return None
    result = ActiveThesis(
        thesis_id=str(row["thesis_id"]),
        version_id=str(row["version_id"]),
        version_number=int(row["version_number"]),
        raw_text=str(row.get("raw_text") or ""),
        parsed_json=dict(row.get("parsed_json") or {}),
        embedding=[float(value) for value in row.get("embedding") or []],
        embedding_model=str(row.get("embedding_model") or "none"),
        thesis_updated_at=(
            str(row["thesis_updated_at"])
            if row.get("thesis_updated_at") is not None
            else None
        ),
    )
    if use_cache:
        _cache_store_full(uid, result)
    return result


def get_active_thesis_metadata(
    client: Any, user_id: str, *, use_cache: bool = True
) -> Optional[ActiveThesisMeta]:
    """
    Metadata-only resolve (mode / dimension / version info) that never pulls the
    embedding_vector. Use for endpoints like /api/fund-thesis/runtime that only
    need to know whether embeddings exist, not their contents.

    Served from the metadata cache, or derived for free from a warm full-thesis
    cache entry; falls back to a lightweight Supabase read (model column only).
    """
    uid = require_user_id(user_id, context="get_active_thesis_metadata")
    if use_cache and _thesis_cache_ttl() > 0:
        now = time.monotonic()
        with _thesis_cache_lock:
            mhit = _thesis_meta_cache.get(uid)
            if mhit is not None and mhit[0] > now:
                return mhit[1]
            fhit = _thesis_full_cache.get(uid)
        if fhit is not None and fhit[0] > now:
            derived = _meta_from_active(fhit[1]) if fhit[1] is not None else None
            with _thesis_cache_lock:
                _thesis_meta_cache[uid] = (fhit[0], derived)
            return derived
    try:
        meta: Optional[ActiveThesisMeta] = _resolve_active_thesis_meta_unsafe(client, uid)
    except FundThesisQueryError:
        raise
    except FundThesisMissingError:
        meta = None
    if use_cache:
        _cache_store_meta(uid, meta)
    return meta


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
    if score_raw is None:
        score_raw = ri.get("fund_thesis_alignment_score")
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


# PostgREST JSON projection: pull only the three thesis fields out of review_info
# instead of the whole (large, multi-review) blob. Cuts egress per row from a full
# review_info JSON to ~3 short scalars. Aliases map to _projected_thesis_fields keys.
_THESIS_ALIGNMENT_PROJECTION = (
    "v:review_info->>fund_thesis_version_id,"
    "s:review_info->>thesis_alignment_score,"
    "s2:review_info->>fund_thesis_alignment_score,"
    "m:review_info->>thesis_matches_fund"
)


def _projected_thesis_fields(row: Any) -> tuple[Optional[float], Optional[bool], Optional[str]]:
    """Parse a row projected via _THESIS_ALIGNMENT_PROJECTION (scalar strings, not a dict)."""
    if not isinstance(row, dict):
        return None, None, None
    raw_score = row.get("s")
    if raw_score is None or (isinstance(raw_score, str) and not raw_score.strip()):
        raw_score = row.get("s2")
    score: Optional[float] = None
    if raw_score is not None and not (isinstance(raw_score, str) and not raw_score.strip()):
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            score = None
    m_raw = row.get("m")
    if m_raw is None:
        mb: Optional[bool] = None
    elif isinstance(m_raw, bool):
        mb = m_raw
    else:
        s = str(m_raw).strip().lower()
        mb = None if s == "" else s in ("true", "1", "yes", "t")
    v = row.get("v")
    version_id = str(v).strip() if v else None
    return score, mb, version_id or None


def compute_thesis_alignment_stats(
    client: Any,
    user_id: str,
    *,
    active_version_id: str,
    previous_version_id: Optional[str] = None,
    row_limit: int = 2000,
    startup_rows: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Aggregate thesis alignment from a bounded StartupRepository projection.
    """
    uid = require_user_id(user_id, context="compute_thesis_alignment_stats")
    active_version_id = active_version_id.strip()
    prev = (previous_version_id or "").strip() or None

    scores_active: List[float] = []
    scores_prev: List[float] = []
    match_active = 0
    total_active = 0
    row_limit = max(1, min(int(row_limit), 2000))
    rows = (startup_rows or [])[:row_limit]

    for row in rows:
        score, matches, vid = _projected_thesis_fields(row)
        if vid != active_version_id:
            continue
        total_active += 1
        if score is not None:
            scores_active.append(score)
        if matches is True or (matches is None and score is not None and score >= 0.6):
            match_active += 1

    if prev:
        for row in rows:
            score, _, vid = _projected_thesis_fields(row)
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
