"""
OpenAI-backed parse + embed for fund thesis versions (API / admin paths only).

Embeddings can legitimately be absent: a thesis bootstrapped without an
OPENAI_API_KEY (or via fund-config sync with skip_embedding) stores an empty
vector + model "none", and the pipeline runs thesis-blind on the vector side.
``backfill_thesis_embeddings`` / ``ensure_active_thesis_embedding`` generate the
real vectors once a key is available — exposed via POST
/api/fund-thesis/backfill-embeddings and called opportunistically (best-effort)
at the start of each pipeline cycle.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

from openai import OpenAI

logger = logging.getLogger(__name__)

_DEFAULT_EMBED_MODEL = "text-embedding-3-small"

_PARSE_SYSTEM = """You extract a structured investment mandate from a fund's written thesis.
Output ONLY valid JSON with these keys (use arrays or strings; empty array if unknown):
- sectors: string[]  (target sectors or themes)
- stage_focus: string[]  (e.g. Pre-Seed, Seed, Series A)
- geography: string[]  (regions or countries)
- exclusions: string[]  (hard passes, anti-thesis)
- check_size: string  (ticket size narrative or range)
- risk_profile: string  (e.g. conservative, balanced, venture)
- investment_rules: string[]  (3-10 bullet rules the pipeline must respect)
"""


def parse_fund_thesis_raw(raw_text: str, api_key: str, model: Optional[str] = None) -> Dict[str, Any]:
    """LLM structured parse; returns dict suitable for parsed_json column."""
    text = (raw_text or "").strip()
    if not text:
        return {
            "sectors": [],
            "stage_focus": [],
            "geography": [],
            "exclusions": [],
            "check_size": "",
            "risk_profile": "",
            "investment_rules": [],
        }
    client = OpenAI(api_key=api_key)
    m = model or os.getenv("FUND_THESIS_PARSE_MODEL", "gpt-4o-mini")
    user = f"Fund thesis document:\n\n{text[:48000]}\n\nReturn JSON only."
    resp = client.chat.completions.create(
        model=m,
        messages=[
            {"role": "system", "content": _PARSE_SYSTEM},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        max_completion_tokens=2048,
    )
    content = resp.choices[0].message.content
    if not content:
        raise ValueError("empty parse response")
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("parse result must be object")
    out: Dict[str, Any] = {
        "sectors": _as_str_list(data.get("sectors")),
        "stage_focus": _as_str_list(data.get("stage_focus")),
        "geography": _as_str_list(data.get("geography")),
        "exclusions": _as_str_list(data.get("exclusions")),
        "check_size": str(data.get("check_size") or ""),
        "risk_profile": str(data.get("risk_profile") or ""),
        "investment_rules": _as_str_list(data.get("investment_rules")),
    }
    return out


def _as_str_list(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, str) and v.strip():
        return [v.strip()]
    return []


def embed_text_for_thesis(text: str, api_key: str, model: Optional[str] = None) -> List[float]:
    """Single text embedding as list of floats (stored JSONB)."""
    client = OpenAI(api_key=api_key)
    m = model or os.getenv("FUND_THESIS_EMBED_MODEL", _DEFAULT_EMBED_MODEL)
    t = (text or "").strip()
    if not t:
        t = "empty"
    resp = client.embeddings.create(model=m, input=t[:8000])
    vec = resp.data[0].embedding
    return [float(x) for x in vec]


def _vector_is_empty(ev: Any) -> bool:
    """True when a stored embedding_vector carries no usable numbers."""
    if ev is None:
        return True
    if isinstance(ev, list):
        return len(ev) == 0
    if isinstance(ev, dict):
        return not (ev.get("values") or [])
    return True


def _embedding_row_needs_backfill(row: Optional[Dict[str, Any]]) -> bool:
    """A version needs embedding when it has no row, an empty vector, or model 'none'."""
    if not row:
        return True
    if str(row.get("model") or "none").strip().lower() == "none":
        return True
    return _vector_is_empty(row.get("embedding_vector"))


def backfill_thesis_embeddings(
    client: Any,
    user_id: str,
    *,
    api_key: str,
    limit: int = 50,
    only_active: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Generate real embeddings for the user's thesis versions that lack them.

    Idempotent and tenant-scoped: scans ``fund_thesis_versions`` for the user,
    finds those whose ``fund_thesis_embeddings`` row is missing / empty / model
    "none", and (unless ``dry_run``) embeds the version's raw_text and upserts
    the vector (unique on version_id). ``only_active`` limits to the active
    version. Returns ``{scanned, eligible, embedded, failed, skipped}``.
    """
    from tenant_context import require_user_id
    from fund_thesis import invalidate_thesis_cache

    uid = require_user_id(user_id, context="backfill_thesis_embeddings")
    ak = (api_key or "").strip()
    if not ak and not dry_run:
        raise ValueError("api_key (OPENAI_API_KEY) required to backfill embeddings")
    lim = max(1, min(int(limit), 500))

    active_version_id = ""
    if only_active:
        tr = client.table("fund_thesis").select("active_version_id").eq("user_id", uid).limit(1).execute()
        trows = getattr(tr, "data", None) or []
        active_version_id = str((trows[0].get("active_version_id") if trows else "") or "").strip()
        if not active_version_id:
            return {"scanned": 0, "eligible": 0, "embedded": 0, "failed": 0, "skipped": 0}

    vq = (
        client.table("fund_thesis_versions")
        .select("id,raw_text")
        .eq("user_id", uid)
        .order("version_number", desc=True)
        .limit(lim)
    )
    if only_active:
        vq = vq.eq("id", active_version_id)
    versions = getattr(vq.execute(), "data", None) or []

    # Existing embedding rows for this user (one query, then matched in memory).
    er = (
        client.table("fund_thesis_embeddings")
        .select("version_id,embedding_vector,model")
        .eq("user_id", uid)
        .execute()
    )
    existing = {str(r.get("version_id")): r for r in (getattr(er, "data", None) or [])}

    eligible = [v for v in versions if _embedding_row_needs_backfill(existing.get(str(v.get("id"))))]
    if dry_run:
        return {
            "scanned": len(versions),
            "eligible": len(eligible),
            "embedded": 0,
            "failed": 0,
            "skipped": len(versions) - len(eligible),
        }

    embed_model = os.getenv("FUND_THESIS_EMBED_MODEL", _DEFAULT_EMBED_MODEL)
    embedded = 0
    failed = 0
    for v in eligible:
        vid = str(v.get("id") or "").strip()
        if not vid:
            failed += 1
            continue
        try:
            raw = str(v.get("raw_text") or "")
            vector = embed_text_for_thesis(raw[:8000], ak, model=embed_model)
            client.table("fund_thesis_embeddings").upsert(
                {
                    "user_id": uid,
                    "version_id": vid,
                    "embedding_vector": vector,
                    "model": embed_model,
                },
                on_conflict="version_id",
            ).execute()
            embedded += 1
        except Exception as e:
            logger.warning("[ThesisEmbedBackfill] failed for version %s: %s", vid[:12], e)
            failed += 1

    if embedded:
        invalidate_thesis_cache(uid)
    logger.info(
        "[ThesisEmbedBackfill] user_id=%s scanned=%s eligible=%s embedded=%s failed=%s",
        uid[:24], len(versions), len(eligible), embedded, failed,
    )
    return {
        "scanned": len(versions),
        "eligible": len(eligible),
        "embedded": embedded,
        "failed": failed,
        "skipped": len(versions) - len(eligible),
    }


def ensure_active_thesis_embedding(client: Any, user_id: str, api_key: str) -> bool:
    """Best-effort: embed the active thesis version if it lacks a vector. Never raises.

    Cheap opportunistic hook for the pipeline ("backfill once a key is
    available"): at most one embedding API call, only when the active version is
    missing its vector. Returns True if a vector was written this call.
    """
    try:
        if not (api_key or "").strip():
            return False
        result = backfill_thesis_embeddings(
            client, user_id, api_key=api_key, only_active=True, limit=1
        )
        return bool(result.get("embedded"))
    except Exception as e:  # pragma: no cover - opportunistic, must never break the pipeline
        logger.debug("ensure_active_thesis_embedding skipped: %s", e)
        return False


def create_fund_thesis_version_for_user(
    client: Any,
    *,
    user_id: str,
    raw_text: str,
    api_key: str = "",
    parsed_json_override: Optional[Dict[str, Any]] = None,
    pipeline_run_id: Optional[str] = None,
    additional_parsed_fields: Optional[Dict[str, Any]] = None,
    skip_embedding: bool = False,
    skip_if_unchanged: bool = False,
) -> Dict[str, Any]:
    """
    Ensure fund_thesis row, append new version, optional embed, activate, pipeline link.
    If parsed_json_override is set, LLM parse is skipped. If skip_embedding, no embedding API call
    (stores empty vector + model "none"). Otherwise api_key is required for parse and/or embed.
    Service-role Supabase client required.
    """
    from tenant_context import require_user_id
    from fund_thesis import count_user_startups, insert_thesis_pipeline_link, invalidate_thesis_cache

    uid = require_user_id(user_id, context="create_fund_thesis_version_for_user")
    raw = (raw_text or "").strip()
    if not raw:
        raise ValueError("raw_text required")

    if isinstance(parsed_json_override, dict):
        parsed = dict(parsed_json_override)
    else:
        ak = (api_key or "").strip()
        if not ak:
            raise ValueError("api_key (OPENAI_API_KEY) required when parsed_json_override is not set")
        parsed = parse_fund_thesis_raw(raw, ak)
    if isinstance(additional_parsed_fields, dict) and additional_parsed_fields:
        merged = dict(parsed)
        merged.update(additional_parsed_fields)
        parsed = merged

    if skip_if_unchanged:
        from fund_thesis import get_active_thesis
        from utils.settings_loader import thesis_payload_fingerprint

        active = get_active_thesis(client, uid)
        if active is not None:
            incoming = thesis_payload_fingerprint(raw_text=raw, parsed_json=parsed)
            current = thesis_payload_fingerprint(raw_text=active.raw_text, parsed_json=active.parsed_json)
            if incoming == current:
                return {
                    "thesis_id": active.thesis_id,
                    "version_id": active.version_id,
                    "version_number": active.version_number,
                    "skipped": True,
                }

    if skip_embedding:
        vector: List[float] = []
        embed_model = "none"
    else:
        ak = (api_key or "").strip()
        if not ak:
            raise ValueError("api_key (OPENAI_API_KEY) required when skip_embedding is False")
        embed_source = raw if len(raw) < 8000 else raw[:8000]
        vector = embed_text_for_thesis(embed_source, ak)
        embed_model = os.getenv("FUND_THESIS_EMBED_MODEL", _DEFAULT_EMBED_MODEL)

    tr = client.table("fund_thesis").select("id,active_version_id").eq("user_id", uid).limit(1).execute()
    trows = getattr(tr, "data", None) or []

    if not trows:
        client.table("fund_thesis").insert({"user_id": uid}).execute()
        tr = client.table("fund_thesis").select("id").eq("user_id", uid).limit(1).execute()
        trows = getattr(tr, "data", None) or []
        if not trows:
            raise RuntimeError("failed to create fund_thesis row")
    thesis_id = str(trows[0]["id"])

    vr = (
        client.table("fund_thesis_versions")
        .select("version_number")
        .eq("thesis_id", thesis_id)
        .eq("user_id", uid)
        .order("version_number", desc=True)
        .limit(1)
        .execute()
    )
    vrows = getattr(vr, "data", None) or []
    next_v = 1
    if vrows and vrows[0].get("version_number") is not None:
        try:
            next_v = int(vrows[0]["version_number"]) + 1
        except (TypeError, ValueError):
            next_v = 1

    version_id = str(uuid4())
    client.table("fund_thesis_versions").update({"is_active": False}).eq("thesis_id", thesis_id).eq(
        "user_id", uid
    ).execute()

    client.table("fund_thesis_versions").insert(
        {
            "id": version_id,
            "user_id": uid,
            "thesis_id": thesis_id,
            "version_number": next_v,
            "raw_text": raw,
            "parsed_json": parsed,
            "is_active": True,
        }
    ).execute()

    client.table("fund_thesis_embeddings").insert(
        {
            "user_id": uid,
            "version_id": version_id,
            "embedding_vector": vector,
            "model": embed_model,
        }
    ).execute()

    from datetime import datetime, timezone

    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    client.table("fund_thesis").update(
        {"active_version_id": version_id, "updated_at": now_iso}
    ).eq("id", thesis_id).eq("user_id", uid).execute()

    affected = count_user_startups(client, uid)
    try:
        insert_thesis_pipeline_link(
            client,
            user_id=uid,
            thesis_version_id=version_id,
            pipeline_run_id=pipeline_run_id,
            affected_startups_count=affected,
        )
    except Exception as e:
        logger.warning("insert_thesis_pipeline_link failed: %s", e)

    invalidate_thesis_cache(uid)

    return {
        "thesis_id": thesis_id,
        "version_id": version_id,
        "version_number": next_v,
        "skipped": False,
    }


def sync_fund_config_to_active_thesis(
    client: Any,
    *,
    user_id: str,
    fund_config: Dict[str, Any],
    api_key: str = "",
    pipeline_run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a thesis version only when fund_config mandate/scoring content changed vs active thesis.
    """
    from utils.settings_loader import fund_config_matches_thesis_payload, fund_config_raw_text, fund_config_to_thesis_parsed_json
    from fund_thesis import get_active_thesis
    from tenant_context import require_user_id

    uid = require_user_id(user_id, context="sync_fund_config_to_active_thesis")
    fc = fund_config if isinstance(fund_config, dict) else {}
    raw_text = fund_config_raw_text(fc).strip()
    if not raw_text:
        return {"skipped": True, "reason": "empty_raw_text"}

    active = get_active_thesis(client, uid)
    if active is not None and fund_config_matches_thesis_payload(
        raw_text=active.raw_text,
        parsed_json=active.parsed_json,
        fund_config=fc,
    ):
        return {
            "skipped": True,
            "thesis_id": active.thesis_id,
            "version_id": active.version_id,
            "version_number": active.version_number,
        }

    return create_fund_thesis_version_for_user(
        client,
        user_id=uid,
        raw_text=raw_text,
        api_key=api_key,
        parsed_json_override=fund_config_to_thesis_parsed_json(fc),
        pipeline_run_id=pipeline_run_id,
        skip_embedding=not bool((api_key or "").strip()),
        skip_if_unchanged=False,
    )


def activate_fund_thesis_version(
    client: Any,
    *,
    user_id: str,
    version_id: str,
    pipeline_run_id: Optional[str] = None,
) -> None:
    """Set one version active; must belong to user's thesis."""
    from tenant_context import require_user_id
    from fund_thesis import count_user_startups, insert_thesis_pipeline_link, invalidate_thesis_cache

    uid = require_user_id(user_id, context="activate_fund_thesis_version")
    vid = (version_id or "").strip()
    if not vid:
        raise ValueError("version_id required")

    vr = (
        client.table("fund_thesis_versions")
        .select("id,thesis_id,user_id")
        .eq("id", vid)
        .eq("user_id", uid)
        .limit(1)
        .execute()
    )
    vrows = getattr(vr, "data", None) or []
    if not vrows:
        raise ValueError("version not found")
    thesis_id = str(vrows[0]["thesis_id"])

    client.table("fund_thesis_versions").update({"is_active": False}).eq("thesis_id", thesis_id).eq(
        "user_id", uid
    ).execute()
    client.table("fund_thesis_versions").update({"is_active": True}).eq("id", vid).eq("user_id", uid).execute()

    from datetime import datetime, timezone

    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    client.table("fund_thesis").update(
        {"active_version_id": vid, "updated_at": now_iso}
    ).eq("id", thesis_id).eq("user_id", uid).execute()

    affected = count_user_startups(client, uid)
    insert_thesis_pipeline_link(
        client,
        user_id=uid,
        thesis_version_id=vid,
        pipeline_run_id=pipeline_run_id,
        affected_startups_count=affected,
    )
    invalidate_thesis_cache(uid)
