"""Fund-thesis routes: read active thesis + version metadata, runtime alignment
stats, create/activate versions, reprocess-missing, and embedding backfill.

Split out of api.py. The transport-retry classifier moved here with it (it had
no other caller).
"""
import asyncio
import os
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from routers.deps import (
    require_supabase_for_thesis as _require_supabase_for_thesis,
    safe_table_execute as _safe_table_execute,
    enforce_rate_limits as _enforce_rate_limits,
    SETTINGS_MUTATION_POLICY as _SETTINGS_MUTATION_POLICY,
)
from security.request_guards import require_authenticated_user
from supabase_client import get_service_client
from fund_thesis import (
    FundThesisIncompleteError,
    FundThesisQueryError,
    _bootstrap_default_thesis_or_raise,
    compute_thesis_alignment_stats,
    get_active_thesis,
    get_active_thesis_metadata,
    thesis_has_embeddings,
)
from fund_thesis_ops import (
    activate_fund_thesis_version,
    backfill_thesis_embeddings,
    create_fund_thesis_version_for_user,
)
from pipeline_runner import reprocess_startups_missing_fund_thesis

router = APIRouter()


def _is_retryable_thesis_transport_error(err: Exception) -> bool:
    if isinstance(err, httpx.HTTPError):
        return True
    if isinstance(err, OSError) and getattr(err, "errno", None) == 11:
        return True
    err_name = type(err).__name__
    return err_name in {
        "ReadError",
        "ConnectError",
        "TimeoutException",
        "HTTPError",
        "RemoteProtocolError",
        "ProtocolError",
        "TransportError",
    }


@router.get("/api/fund-thesis")
def api_get_fund_thesis(request: Request):
    """Active thesis, version list metadata, embedding status, recent pipeline links."""
    _require_supabase_for_thesis()
    uid = request.state.user_id
    client = get_service_client()
    try:
        active = get_active_thesis(client, uid)
        if active is None:
            _bootstrap_default_thesis_or_raise(client, uid)
            active = get_active_thesis(client, uid)
        if active is None:
            raise HTTPException(status_code=404, detail="No fund thesis yet. POST /api/fund-thesis/versions with raw_text.")
    except FundThesisQueryError as e:
        # Transient DB error — surface as 503 so callers can retry. Do NOT bootstrap
        # here, as doing so on query errors is what causes spurious version creation.
        raise HTTPException(status_code=503, detail=f"Thesis query failed: {e}")
    except FundThesisIncompleteError as e:
        raise HTTPException(status_code=503, detail=str(e))

    vr_rows = _safe_table_execute(
        lambda: (
            client.table("fund_thesis_versions")
            .select("id,version_number,is_active,created_at")
            .eq("user_id", uid)
            .eq("thesis_id", active.thesis_id)
            .order("version_number", desc=True)
            .limit(50)
            .execute()
        ),
        default_data=[],
        warn_label=f"[{uid[:12]}] fund-thesis versions query",
    )
    versions = getattr(vr_rows, "data", None) or []

    er_resp = _safe_table_execute(
        lambda: (
            client.table("fund_thesis_embeddings")
            .select("model,created_at")
            .eq("version_id", active.version_id)
            .eq("user_id", uid)
            .limit(1)
            .execute()
        ),
        default_data=[],
        warn_label=f"[{uid[:12]}] fund-thesis embeddings query",
    )
    erows = getattr(er_resp, "data", None) or []
    emb_row = erows[0] if erows else {}

    lr_resp = _safe_table_execute(
        lambda: (
            client.table("fund_thesis_pipeline_link")
            .select("id,thesis_version_id,pipeline_run_id,affected_startups_count,created_at")
            .eq("user_id", uid)
            .order("created_at", desc=True)
            .limit(20)
            .execute()
        ),
        default_data=[],
        warn_label=f"[{uid[:12]}] fund-thesis pipeline links query",
    )

    has_emb = thesis_has_embeddings(active)
    emb_status = "ready" if has_emb else "pending"
    emb_model = active.embedding_model if has_emb else "none"
    dim = len(active.embedding)
    return {
        "thesis_id": active.thesis_id,
        "active_version_id": active.version_id,
        "active_version_number": active.version_number,
        "parsed_json": active.parsed_json,
        "raw_text": active.raw_text[:50000],
        "mode": "embedding" if has_emb else "rule_based",
        "embedding": {
            "status": emb_status,
            "model": emb_model,
            "dimension": dim,
            "dimensions": dim,
            "created_at": emb_row.get("created_at"),
        },
        "versions": versions,
        "recent_pipeline_links": getattr(lr_resp, "data", None) or [],
    }


@router.get("/api/fund-thesis/runtime")
def get_fund_thesis_runtime(request: Request):
    """Lightweight thesis runtime (mode / embeddings) for System panel; alignment extras without parsed_json."""
    try:
        return _get_fund_thesis_runtime_impl(request)
    except FundThesisQueryError:
        raise HTTPException(status_code=503, detail="Thesis query failed; please retry") from None
    except OSError as e:
        # EAGAIN under memory/socket pressure on small hosts (e.g. Render OOM edge).
        if getattr(e, "errno", None) == 11:
            raise HTTPException(status_code=503, detail="Thesis query failed; please retry") from e
        raise
    except Exception as e:
        if _is_retryable_thesis_transport_error(e):
            raise HTTPException(status_code=503, detail="Thesis query failed; please retry") from e
        raise


def _get_fund_thesis_runtime_impl(request: Request):
    _require_supabase_for_thesis()
    uid = request.state.user_id
    client = get_service_client()
    try:
        # Metadata-only: never re-pulls the ~1536-float embedding_vector on this
        # high-frequency poll; only mode / dimension / version info is needed here.
        active = get_active_thesis_metadata(client, uid)
        if active is None:
            return JSONResponse(
                status_code=200,
                content={
                    "mode": "missing",
                    "embedding_status": "pending",
                    "has_embeddings": False,
                },
            )
    except FundThesisQueryError:
        raise HTTPException(status_code=503, detail="Thesis query failed; please retry")
    except FundThesisIncompleteError as e:
        return JSONResponse(
            status_code=200,
            content={
                "mode": "missing",
                "embedding_status": "pending",
                "has_embeddings": False,
                "thesis_ready": False,
                "error": "incomplete",
                "detail": str(e),
                "alignment_stats": {},
            },
        )

    has_emb = active.has_embeddings
    mode = "embedding" if has_emb else "rule_based"
    embedding_status = "ready" if has_emb else "pending"
    emb_model = (
        (active.embedding_model or "").strip()
        if has_emb
        else "none"
    )
    if has_emb and not emb_model:
        emb_model = "none"

    # Fetch the version timeline once and reuse it: the immediately-previous version
    # (for drift) is almost always present here (active is the newest version), so we
    # derive prev_id from this result instead of issuing a separate point query.
    tl_r = (
        client.table("fund_thesis_versions")
        .select("id,version_number,is_active,created_at")
        .eq("user_id", uid)
        .eq("thesis_id", active.thesis_id)
        .order("version_number", desc=True)
        .limit(15)
        .execute()
    )
    version_timeline = getattr(tl_r, "data", None) or []

    prev_id: Optional[str] = None
    if active.version_number > 1:
        for row in version_timeline:
            if row.get("version_number") == active.version_number - 1:
                prev_id = str(row.get("id") or "") or None
                break
        # Fallback only if the predecessor fell outside the 15-row timeline window.
        if prev_id is None:
            pr = (
                client.table("fund_thesis_versions")
                .select("id")
                .eq("user_id", uid)
                .eq("thesis_id", active.thesis_id)
                .eq("version_number", active.version_number - 1)
                .limit(1)
                .execute()
            )
            prow = getattr(pr, "data", None) or []
            if prow:
                prev_id = str(prow[0].get("id") or "") or None

    stats = compute_thesis_alignment_stats(
        client,
        uid,
        active_version_id=active.version_id,
        previous_version_id=prev_id,
        row_limit=int(os.getenv("FUND_THESIS_RUNTIME_ALIGNMENT_ROW_LIMIT", "500")),
    )

    dim = active.embedding_dim
    payload: Dict[str, Any] = {
        "thesis_version_id": active.version_id,
        "mode": mode,
        "embedding_status": embedding_status,
        "embedding_model": emb_model,
        "has_embeddings": has_emb,
        # Backward-compatible fields for SystemIntelligence / clients
        "thesis_ready": True,
        "active_version_id": active.version_id,
        "active_version_number": active.version_number,
        "fund_thesis_updated_at": active.thesis_updated_at,
        "thesis_mode": mode,
        "embedding": {
            "status": embedding_status,
            "model": emb_model,
            "dimension": dim,
        },
        "embedding_dimensions": dim,
        "alignment_stats": stats,
        "version_timeline": version_timeline,
        "parsed_json": active.parsed_json,
    }
    return JSONResponse(status_code=200, content=payload)


@router.post("/api/fund-thesis/versions")
async def api_post_fund_thesis_version(request: Request):
    """Create a new thesis version (parse + embed + activate). Optional skip_embedding + parsed_json avoids OpenAI."""
    _require_supabase_for_thesis()
    body = await request.json()
    raw_text = str(body.get("raw_text") or "").strip()
    if not raw_text:
        raise HTTPException(status_code=422, detail="raw_text is required")
    parsed_override = body.get("parsed_json")
    pipeline_run_id = str(body.get("pipeline_run_id") or "").strip() or None
    skip_embedding = bool(body.get("skip_embedding"))
    po = parsed_override if isinstance(parsed_override, dict) else None
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key and not (po and skip_embedding):
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY required unless both parsed_json and skip_embedding are set",
        )
    uid = request.state.user_id
    try:
        # Sync Supabase writes + optional OpenAI embedding call: off the event loop.
        out = await asyncio.to_thread(
            create_fund_thesis_version_for_user,
            get_service_client(),
            user_id=uid,
            raw_text=raw_text,
            api_key=api_key,
            parsed_json_override=po,
            pipeline_run_id=pipeline_run_id,
            skip_embedding=skip_embedding,
            skip_if_unchanged=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    status = "unchanged" if out.get("skipped") else "created"
    return {"status": status, **out}


@router.patch("/api/fund-thesis/active")
async def api_patch_fund_thesis_active(request: Request):
    """Activate an existing version (embeddings optional)."""
    _require_supabase_for_thesis()
    body = await request.json()
    version_id = str(body.get("version_id") or "").strip()
    if not version_id:
        raise HTTPException(status_code=422, detail="version_id is required")
    pipeline_run_id = str(body.get("pipeline_run_id") or "").strip() or None
    uid = request.state.user_id
    try:
        await asyncio.to_thread(
            activate_fund_thesis_version,
            get_service_client(),
            user_id=uid,
            version_id=version_id,
            pipeline_run_id=pipeline_run_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"status": "ok", "active_version_id": version_id}


@router.post("/api/fund-thesis/reprocess-missing")
async def api_post_fund_thesis_reprocess_missing(
    request: Request,
    dry_run: bool = Query(False, description="If true, return eligible count only (no OpenAI calls)"),
):
    """
    Re-run reviewer + partner for startups that have reviews but no fund_thesis_version_id
    on review_info. Does not run scout or create new startups.
    """
    _require_supabase_for_thesis()
    uid = request.state.user_id
    client = get_service_client()

    if not dry_run:
        try:
            thesis = await asyncio.to_thread(get_active_thesis, client, uid)
            if thesis is None:
                raise HTTPException(status_code=400, detail="No active thesis")
        except FundThesisIncompleteError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if not os.getenv("OPENAI_API_KEY", "").strip():
            raise HTTPException(
                status_code=503,
                detail="OPENAI_API_KEY required for thesis reprocessing",
            )

    try:
        result = await reprocess_startups_missing_fund_thesis(uid, dry_run=dry_run)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return result


@router.post("/api/fund-thesis/backfill-embeddings")
async def api_post_fund_thesis_backfill_embeddings(
    request: Request,
    dry_run: bool = Query(False, description="If true, return eligible count only (no OpenAI calls)"),
    only_active: bool = Query(False, description="If true, backfill only the active version"),
):
    """
    Generate real embeddings for thesis versions stored without one (empty vector
    / model 'none'). Idempotent and tenant-scoped. Useful after a thesis was
    bootstrapped before OPENAI_API_KEY was configured.
    """
    _require_supabase_for_thesis()
    uid = require_authenticated_user(request)
    limited = _enforce_rate_limits(f"user:{uid}:settings_mutation", [_SETTINGS_MUTATION_POLICY])
    if limited:
        return limited
    client = get_service_client()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not dry_run and not api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY required to backfill embeddings")
    try:
        result = await asyncio.to_thread(
            backfill_thesis_embeddings,
            client,
            uid,
            api_key=api_key,
            only_active=only_active,
            dry_run=dry_run,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return result
