"""Fund-thesis routes: read active thesis + version metadata, runtime alignment
stats, create/activate versions, reprocess-missing, and embedding backfill.

Split out of api.py. The transport-retry classifier moved here with it (it had
no other caller).
"""
import asyncio
import os
from typing import Any, Dict, Optional

import httpx
import env_config
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from routers.deps import (
    require_supabase_for_thesis as _require_supabase_for_thesis,
    safe_table_execute as _safe_table_execute,
    enforce_rate_limits as _enforce_rate_limits,
    SETTINGS_MUTATION_POLICY as _SETTINGS_MUTATION_POLICY,
)
from security.request_guards import require_authenticated_user
from fund_thesis import (
    FundThesisIncompleteError,
    FundThesisQueryError,
    _bootstrap_default_thesis_or_raise,
    bootstrap_default_thesis_with_repository,
    compute_thesis_alignment_stats,
    get_active_thesis,
    get_active_thesis_metadata,
    thesis_has_embeddings,
)
from fund_thesis_ops import (
    activate_fund_thesis_version_with_repository,
    backfill_thesis_embeddings_with_repository,
    create_fund_thesis_version_with_repository,
)
from pipeline_runner import reprocess_startups_missing_fund_thesis
from pipeline_execution import PipelineExecutionState
from startup_repository import StartupRepository

router = APIRouter()


def get_service_client():
    """Legacy dev/test seam; normal thesis routes require PostgreSQL."""
    from supabase_client import get_service_client as _get_service_client

    return _get_service_client()


def _get_thesis_repository(request: Request) -> Any:
    app = getattr(request, "app", None)
    state = getattr(app, "state", None)
    intelligence = getattr(state, "fund_intelligence_repository", None)
    repository = getattr(intelligence, "thesis_repository", None)
    return repository


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
async def api_get_fund_thesis(request: Request):
    """Active thesis, version list metadata, embedding status, recent pipeline links."""
    uid = request.state.user_id
    repository = _get_thesis_repository(request)
    try:
        active = await repository.get_active(uid)
        if active is None:
            await bootstrap_default_thesis_with_repository(repository, uid)
            active = await repository.get_active(uid)
        if active is None:
            raise HTTPException(status_code=404, detail="No fund thesis yet. POST /api/fund-thesis/versions with raw_text.")
    except FundThesisQueryError as e:
        # Transient DB error — surface as 503 so callers can retry. Do NOT bootstrap
        # here, as doing so on query errors is what causes spurious version creation.
        raise HTTPException(status_code=503, detail=f"Thesis query failed: {e}")
    except FundThesisIncompleteError as e:
        raise HTTPException(status_code=503, detail=str(e))

    versions = await repository.list_versions(uid, thesis_id=active["thesis_id"], limit=50)
    versions = [
        {"id": row["version_id"], "version_number": row["version_number"], "is_active": row["is_active"], "created_at": row["created_at"]}
        for row in versions
    ]
    emb_row = await repository.get_embedding(uid, active["version_id"]) or {}
    links = await repository.get_pipeline_links(uid, limit=20)
    has_emb = bool(active.get("embedding"))
    emb_status = "ready" if has_emb else "pending"
    emb_model = active.get("embedding_model") if has_emb else "none"
    dim = len(active.get("embedding") or [])
    return {
        "thesis_id": active["thesis_id"],
        "active_version_id": active["version_id"],
        "active_version_number": active["version_number"],
        "parsed_json": active["parsed_json"],
        "raw_text": str(active["raw_text"] or "")[:50000],
        "mode": "embedding" if has_emb else "rule_based",
        "embedding": {
            "status": emb_status,
            "model": emb_model,
            "dimension": dim,
            "dimensions": dim,
            "created_at": emb_row.get("created_at"),
        },
        "versions": versions,
        "recent_pipeline_links": links,
    }


@router.get("/api/fund-thesis/runtime")
async def get_fund_thesis_runtime(request: Request):
    """Lightweight thesis runtime (mode / embeddings) for System panel; alignment extras without parsed_json."""
    try:
        return await _get_fund_thesis_runtime_impl(request)
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


async def _get_fund_thesis_runtime_impl(request: Request):
    uid = request.state.user_id
    repository = _get_thesis_repository(request)
    if repository is None:
        # Test/dev compatibility only. Production is fenced at the PostgreSQL
        # repository boundary and never enters this branch.
        _require_supabase_for_thesis()
        client = get_service_client()
        try:
            legacy = get_active_thesis_metadata(client, uid)
            if legacy is None:
                return JSONResponse(status_code=200, content={"mode": "missing", "embedding_status": "pending", "has_embeddings": False})
            timeline_response = (
                client.table("fund_thesis_versions")
                .select("id,version_number,is_active,created_at")
                .eq("user_id", uid)
                .eq("thesis_id", legacy.thesis_id)
                .order("version_number", desc=True)
                .limit(15)
                .execute()
            )
            timeline = getattr(timeline_response, "data", None) or []
            stats = compute_thesis_alignment_stats(
                client, uid, active_version_id=legacy.version_id,
                previous_version_id=None, startup_rows=[],
            )
            dim = legacy.embedding_dim
            return JSONResponse(status_code=200, content=jsonable_encoder({
                "thesis_version_id": legacy.version_id,
                "mode": "embedding" if legacy.has_embeddings else "rule_based",
                "embedding_status": "ready" if legacy.has_embeddings else "pending",
                "embedding_model": legacy.embedding_model if legacy.has_embeddings else "none",
                "has_embeddings": legacy.has_embeddings,
                "thesis_ready": True,
                "active_version_id": legacy.version_id,
                "active_version_number": legacy.version_number,
                "fund_thesis_updated_at": getattr(legacy, "thesis_updated_at", None),
                "thesis_mode": "embedding" if legacy.has_embeddings else "rule_based",
                "embedding": {"status": "ready" if legacy.has_embeddings else "pending", "model": legacy.embedding_model, "dimension": dim},
                "embedding_dimensions": dim,
                "alignment_stats": stats,
                "version_timeline": timeline,
                "parsed_json": legacy.parsed_json,
            }))
        except Exception as exc:
            if _is_retryable_thesis_transport_error(exc):
                raise HTTPException(status_code=503, detail="Thesis query failed; please retry") from exc
            raise
    try:
        active = await repository.get_active(uid)
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

    has_emb = bool(active.get("embedding"))
    mode = "embedding" if has_emb else "rule_based"
    embedding_status = "ready" if has_emb else "pending"
    emb_model = (
        str(active.get("embedding_model") or "").strip()
        if has_emb
        else "none"
    )
    if has_emb and not emb_model:
        emb_model = "none"

    timeline_rows = await repository.list_versions(uid, thesis_id=active["thesis_id"], limit=15)
    version_timeline = [
        {"id": row["version_id"], "version_number": row["version_number"], "is_active": row["is_active"], "created_at": row["created_at"]}
        for row in timeline_rows
    ]

    prev_id: Optional[str] = None
    if active["version_number"] > 1:
        for row in version_timeline:
            if row.get("version_number") == active["version_number"] - 1:
                prev_id = str(row.get("id") or "") or None
                break
        if prev_id is None:
            predecessor = await repository.list_versions(uid, thesis_id=active["thesis_id"], limit=500)
            for row in predecessor:
                if row["version_number"] == active["version_number"] - 1:
                    prev_id = row["version_id"]
                    break

    startup_repository = StartupRepository(getattr(request.app.state, "durable_job_pool", None))
    startup_rows = await startup_repository.list_thesis_alignment(
        uid,
        limit=int(os.getenv("FUND_THESIS_RUNTIME_ALIGNMENT_ROW_LIMIT", "500")),
    )
    stats = compute_thesis_alignment_stats(
        None,
        uid,
        active_version_id=active["version_id"],
        previous_version_id=prev_id,
        row_limit=int(os.getenv("FUND_THESIS_RUNTIME_ALIGNMENT_ROW_LIMIT", "500")),
        startup_rows=startup_rows,
    )

    dim = len(active.get("embedding") or [])
    payload: Dict[str, Any] = {
        "thesis_version_id": active["version_id"],
        "mode": mode,
        "embedding_status": embedding_status,
        "embedding_model": emb_model,
        "has_embeddings": has_emb,
        # Backward-compatible fields for SystemIntelligence / clients
        "thesis_ready": True,
        "active_version_id": active["version_id"],
        "active_version_number": active["version_number"],
        "fund_thesis_updated_at": active.get("thesis_updated_at"),
        "thesis_mode": mode,
        "embedding": {
            "status": embedding_status,
            "model": emb_model,
            "dimension": dim,
        },
        "embedding_dimensions": dim,
        "alignment_stats": stats,
        "version_timeline": version_timeline,
        "parsed_json": active["parsed_json"],
    }
    return JSONResponse(status_code=200, content=jsonable_encoder(payload))


@router.post("/api/fund-thesis/versions")
async def api_post_fund_thesis_version(request: Request):
    """Create a new thesis version (parse + embed + activate). Optional skip_embedding + parsed_json avoids OpenAI."""
    repository = _get_thesis_repository(request)
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
    startup_repository = StartupRepository(getattr(request.app.state, "durable_job_pool", None))
    affected_startups_count = await startup_repository.count_tenant(uid)
    try:
        out = await create_fund_thesis_version_with_repository(
            repository,
            user_id=uid,
            raw_text=raw_text,
            api_key=api_key,
            parsed_json_override=po,
            pipeline_run_id=pipeline_run_id,
            skip_embedding=skip_embedding,
            skip_if_unchanged=True,
            affected_startups_count=affected_startups_count,
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
    repository = _get_thesis_repository(request)
    body = await request.json()
    version_id = str(body.get("version_id") or "").strip()
    if not version_id:
        raise HTTPException(status_code=422, detail="version_id is required")
    pipeline_run_id = str(body.get("pipeline_run_id") or "").strip() or None
    uid = request.state.user_id
    startup_repository = StartupRepository(getattr(request.app.state, "durable_job_pool", None))
    affected_startups_count = await startup_repository.count_tenant(uid)
    try:
        await activate_fund_thesis_version_with_repository(
            repository,
            user_id=uid,
            version_id=version_id,
            pipeline_run_id=pipeline_run_id,
            affected_startups_count=affected_startups_count,
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
    if getattr(request.app.state, "durable_job_pool", None) is None and env_config.is_production_env():
        raise HTTPException(
            status_code=503,
            detail="The shared PostgreSQL repository is required for thesis reprocessing",
        )
    uid = request.state.user_id
    result = await reprocess_startups_missing_fund_thesis(
        uid,
        dry_run=dry_run,
        fund_intelligence_repository=getattr(
            request.app.state, "fund_intelligence_repository", None
        ),
    )
    if result.state is PipelineExecutionState.BLOCKED:
        status = (
            409
            if result.code in {"thesis_required", "published_policy_required"}
            else 503
        )
        raise HTTPException(
            status_code=status,
            detail={
                "code": result.code,
                "detail": result.detail,
                "recovery_action": result.recovery_action,
            },
        )
    if result.state is PipelineExecutionState.FAILED_STAGE:
        raise HTTPException(
            status_code=500,
            detail={
                "code": result.code,
                "detail": result.detail,
                "recovery_action": result.recovery_action,
                "failed_stage": result.failed_stage,
            },
        )
    # Preserve the existing public count payload while runners use typed semantics.
    return result.metadata


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
    repository = _get_thesis_repository(request)
    uid = require_authenticated_user(request)
    limited = await _enforce_rate_limits(f"user:{uid}:settings_mutation", [_SETTINGS_MUTATION_POLICY])
    if limited:
        return limited
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not dry_run and not api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY required to backfill embeddings")
    try:
        result = await backfill_thesis_embeddings_with_repository(
            repository,
            uid,
            api_key=api_key,
            only_active=only_active,
            dry_run=dry_run,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return result
