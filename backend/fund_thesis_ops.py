"""
OpenAI-backed parse + embed for fund thesis versions (API / admin paths only).
"""
# TODO: background job to backfill embeddings for active (or all) thesis versions when
# OPENAI_API_KEY becomes available (skip_embedding / empty vectors → real embeddings).
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
) -> Dict[str, Any]:
    """
    Ensure fund_thesis row, append new version, optional embed, activate, pipeline link.
    If parsed_json_override is set, LLM parse is skipped. If skip_embedding, no embedding API call
    (stores empty vector + model "none"). Otherwise api_key is required for parse and/or embed.
    Service-role Supabase client required.
    """
    from tenant_context import require_user_id
    from fund_thesis import count_user_startups, insert_thesis_pipeline_link

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

    return {
        "thesis_id": thesis_id,
        "version_id": version_id,
        "version_number": next_v,
    }


def activate_fund_thesis_version(
    client: Any,
    *,
    user_id: str,
    version_id: str,
    pipeline_run_id: Optional[str] = None,
) -> None:
    """Set one version active; must belong to user's thesis."""
    from tenant_context import require_user_id
    from fund_thesis import count_user_startups, insert_thesis_pipeline_link

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
