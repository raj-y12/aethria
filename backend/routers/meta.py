"""Meta-agent routes: cycle reports, insights, prompt library/state, prompt
promote/reset/evaluate, eval-set, scout weights, calibration.

Split out of api.py. Stateless reads + prompt-library mutations; the
queue-coupled POST /api/meta/trigger stays in api.py.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from routers.deps import get_startup_repository as _get_startup_repository
from batch1.store import list_get_all
from meta.prompt_gating import (
    VALID_PROMOTE_AGENT_TARGETS,
    REVIEWER_EVAL_AGENT_TARGETS,
    eval_record_fresh,
    get_last_eval_record,
    load_eval_startup_ids,
    load_prompt_active,
    load_prompt_library,
    save_eval_startup_ids,
    save_prompt_active,
    save_prompt_library,
)
from meta.evaluator import run_prompt_evaluation
from meta.reweighter import load_weights
from meta.calibrator import load_calibration_state
from reviewer.engine import ReviewerEngine
from fund_thesis import (
    FundThesisIncompleteError,
    bootstrap_default_thesis_with_repository,
    get_active_thesis_from_repository,
)
from batch1.context import reset_state, set_state
from batch1.repository import Batch1Repository
from startup_repository import StartupReadStorageAdapter

logger = logging.getLogger("api.meta")
router = APIRouter()


async def _batch1_call(request: Request, fn, *args, **kwargs):
    pool = getattr(request.app.state, "durable_job_pool", None)
    if pool is None:
        return await asyncio.to_thread(fn, *args, **kwargs)
    repository = Batch1Repository(pool)
    state = await repository.load_state(request.state.user_id)
    token = set_state(state)
    try:
        return await asyncio.to_thread(fn, *args, **kwargs)
    finally:
        try:
            if not api_local_snapshot_read_only(request):
                await repository.persist_state(state)
        finally:
            reset_state(token)


def api_local_snapshot_read_only(request: Request) -> bool:
    """Avoid state writes when Meta read routes inspect an imported snapshot."""
    import env_config

    return not env_config.is_production_env() and env_config.get_bool("LOCAL_SNAPSHOT_READ_ONLY")


@router.get("/api/meta/reports")
async def get_meta_reports(request: Request):
    """
    Return the last 10 Meta-Agent cycle reports for the authenticated user.
    """
    uid = request.state.user_id
    reports = await _batch1_call(request, list_get_all, "meta_reports", user_id=uid)
    if not isinstance(reports, list):
        return []
    reports = sorted(
        reports,
        key=lambda x: (x.get("ran_at") or "", int(x.get("cycle_number") or 0)),
        reverse=True,
    )
    return reports[:10]


@router.get("/api/meta/insights")
async def get_meta_insights(request: Request):
    """
    Latest meta cycle: what changed (mutations, weights, calibration) and why (no_action_reasons).
    """
    uid = request.state.user_id
    reports = await _batch1_call(request, list_get_all, "meta_reports", user_id=uid)
    if not isinstance(reports, list) or not reports:
        return {
            "latest": None,
            "what_changed": None,
            "why": [],
        }
    latest = max(
        reports,
        key=lambda x: (x.get("ran_at") or "", int(x.get("cycle_number") or 0)),
    )
    return {
        "latest": {
            "cycle_number": latest.get("cycle_number"),
            "ran_at": latest.get("ran_at"),
            "next_cycle_at": latest.get("next_cycle_at"),
        },
        "what_changed": {
            "mutations_applied": latest.get("mutations_applied") or [],
            "prompt_proposals": latest.get("prompt_proposals")
            or latest.get("mutations_applied")
            or [],
            "weight_updates": latest.get("weight_updates") or [],
            "calibration_changes": latest.get("calibration_changes") or [],
        },
        "why": latest.get("no_action_reasons") or [],
        "signal_summary": latest.get("signal_summary"),
    }


@router.get("/api/meta/prompt-library")
async def get_meta_prompt_library(request: Request):
    """
    Return the full prompt library used by the Meta-Agent.
    """
    lib = await _batch1_call(request, load_prompt_library, request.state.user_id)
    return lib if isinstance(lib, dict) else {}


def _summarize_library_entry(
    library_key: str,
    entry: Dict[str, Any],
    *,
    include_prompt_body: bool,
) -> Dict[str, Any]:
    if not isinstance(entry, dict):
        return {"library_key": library_key, "error": "invalid_entry"}
    prompt = entry.get("prompt")
    out: Dict[str, Any] = {
        "library_key": library_key,
        "created_at": entry.get("created_at"),
        "cycle_number": entry.get("cycle_number"),
        "reasoning": (str(entry.get("reasoning") or ""))[:500],
        "promotion_status": entry.get("promotion_status"),
        "previous_hash": entry.get("previous_hash"),
        "prompt_char_count": len(str(prompt)) if prompt else 0,
    }
    if include_prompt_body and prompt is not None:
        out["prompt"] = str(prompt)
    return out


@router.get("/api/meta/prompt-state")
async def get_meta_prompt_state(
    request: Request,
    include_prompt: Optional[str] = Query(
        default=None,
        description="If set, include full prompt text only for this library_key",
    ),
):
    """
    Active and pending meta prompt proposals (metadata only; full text for one key via include_prompt).
    """
    uid = request.state.user_id
    library, active = await asyncio.gather(
        _batch1_call(request, load_prompt_library, uid),
        _batch1_call(request, load_prompt_active, uid),
    )
    if not isinstance(library, dict):
        library = {}

    active_detail: Dict[str, Any] = {}
    for agent, lib_key in sorted(active.items()):
        ent = library.get(lib_key)
        if isinstance(ent, dict):
            active_detail[agent] = _summarize_library_entry(
                lib_key,
                ent,
                include_prompt_body=bool(include_prompt and include_prompt == lib_key),
            )
        else:
            active_detail[agent] = {
                "library_key": lib_key,
                "warning": "missing_from_library",
            }

    active_keys = set(active.values())
    pending: List[Dict[str, Any]] = []
    for key, ent in library.items():
        if not isinstance(key, str) or ":" not in key:
            continue
        agent_tgt, _ = key.split(":", 1)
        if agent_tgt not in VALID_PROMOTE_AGENT_TARGETS:
            continue
        if key in active_keys:
            continue
        if not isinstance(ent, dict):
            continue
        st = ent.get("promotion_status")
        if st == "superseded":
            continue
        if st not in (None, "pending"):
            continue
        pending.append(
            _summarize_library_entry(
                key,
                ent,
                include_prompt_body=bool(include_prompt and include_prompt == key),
            )
        )
    pending.sort(key=lambda x: (x.get("created_at") or "", x.get("library_key") or ""), reverse=True)

    return {
        "active": active,
        "active_detail": active_detail,
        "pending": pending[:80],
        "restart_note": "Promoted prompts apply after workers restart unless META_AGENT_PROMPT_AUTO_APPLY ran in-process.",
    }


@router.post("/api/meta/prompts/promote")
async def post_meta_prompt_promote(request: Request):
    """Promote a pending library_key to the active prompt for an agent."""
    uid = request.state.user_id
    try:
        body = await request.json()
    except Exception:
        body = {}
    agent_target = str(body.get("agent_target") or "").strip()
    library_key = str(body.get("library_key") or "").strip()
    if not agent_target or not library_key:
        raise HTTPException(status_code=400, detail="agent_target and library_key required")
    if agent_target not in VALID_PROMOTE_AGENT_TARGETS:
        raise HTTPException(status_code=400, detail="invalid agent_target")
    if not library_key.startswith(f"{agent_target}:"):
        raise HTTPException(status_code=400, detail="library_key does not match agent_target")

    # Snapshot reads/writes run off the event loop; PostgreSQL I/O is flushed at the boundary.
    return await _batch1_call(request, _promote_prompt_sync, uid, agent_target, library_key)


def _promote_prompt_sync(uid: str, agent_target: str, library_key: str):
    library = load_prompt_library(uid)
    if not isinstance(library, dict) or library_key not in library:
        raise HTTPException(status_code=404, detail="library_key not found")
    ent = library[library_key]
    if not isinstance(ent, dict) or not str(ent.get("prompt") or "").strip():
        raise HTTPException(status_code=400, detail="library entry has no prompt")

    if agent_target in REVIEWER_EVAL_AGENT_TARGETS and os.getenv(
        "META_PROMPT_REQUIRE_EVAL_PASS", ""
    ).lower() in ("1", "true", "yes"):
        rec = get_last_eval_record(uid, library_key)
        if not rec or not rec.get("passed"):
            raise HTTPException(
                status_code=400,
                detail="Evaluation required: POST /api/meta/prompts/evaluate must pass for this library_key",
            )
        try:
            ttl_h = int(os.getenv("META_PROMPT_EVAL_PASS_TTL_HOURS", "24"))
        except ValueError:
            ttl_h = 24
        if not eval_record_fresh(rec, ttl_h):
            raise HTTPException(
                status_code=400,
                detail="Evaluation stale; run POST /api/meta/prompts/evaluate again",
            )

    active = load_prompt_active(uid)
    prev_key = active.get(agent_target)
    if prev_key and prev_key in library and isinstance(library[prev_key], dict):
        library[prev_key] = dict(library[prev_key])
        library[prev_key]["promotion_status"] = "superseded"

    library[library_key] = dict(ent)
    library[library_key]["promotion_status"] = "promoted"
    active = dict(active)
    active[agent_target] = library_key

    save_prompt_library(uid, library)
    save_prompt_active(uid, active)

    try:
        from batch1.store import list_append_only

        list_append_only(
            "meta_mutation_log",
            {
                "type": "prompt_promoted",
                "agent_target": agent_target,
                "library_key": library_key,
                "previous_library_key": prev_key,
                "applied_at": datetime.now(timezone.utc).isoformat(),
            },
            user_id=uid,
        )
    except Exception as e:
        logger.debug("Could not persist prompt action audit: %s", e)

    return {"ok": True, "active": active, "promoted": library_key}


@router.post("/api/meta/prompts/reset")
async def post_meta_prompt_reset(request: Request):
    """Remove active prompt for an agent (revert to codebase default on next load)."""
    uid = request.state.user_id
    try:
        body = await request.json()
    except Exception:
        body = {}
    agent_target = str(body.get("agent_target") or "").strip()
    if not agent_target or agent_target not in VALID_PROMOTE_AGENT_TARGETS:
        raise HTTPException(status_code=400, detail="invalid agent_target")

    # Snapshot reads/writes run off the event loop; PostgreSQL I/O is flushed at the boundary.
    return await _batch1_call(request, _reset_prompt_sync, uid, agent_target)


def _reset_prompt_sync(uid: str, agent_target: str):
    active = load_prompt_active(uid)
    prev_key = active.get(agent_target)
    if not prev_key:
        return {"ok": True, "active": active, "message": "no active prompt for agent"}

    library = load_prompt_library(uid)
    if isinstance(library, dict) and prev_key in library and isinstance(library[prev_key], dict):
        library = dict(library)
        library[prev_key] = dict(library[prev_key])
        library[prev_key]["promotion_status"] = "superseded"
        save_prompt_library(uid, library)

    active = dict(active)
    del active[agent_target]
    save_prompt_active(uid, active)

    try:
        from batch1.store import list_append_only

        list_append_only(
            "meta_mutation_log",
            {
                "type": "prompt_reset",
                "agent_target": agent_target,
                "previous_library_key": prev_key,
                "applied_at": datetime.now(timezone.utc).isoformat(),
            },
            user_id=uid,
        )
    except Exception as e:
        logger.debug("Could not persist prompt action audit: %s", e)

    return {"ok": True, "active": active}


@router.get("/api/meta/eval-set")
async def get_meta_eval_set(request: Request):
    """Fixed startup ids used for reviewer prompt shadow evaluation."""
    uid = request.state.user_id
    ids = await _batch1_call(request, load_eval_startup_ids, uid)
    try:
        max_n = int(os.getenv("META_PROMPT_EVAL_SET_MAX", "50"))
    except ValueError:
        max_n = 50
    return {"startup_ids": ids, "count": len(ids), "max": max_n}


@router.put("/api/meta/eval-set")
async def put_meta_eval_set(request: Request):
    """Replace eval startup id list (validated against tenant storage)."""
    uid = request.state.user_id
    try:
        body = await request.json()
    except Exception:
        body = {}
    raw = body.get("startup_ids")
    if not isinstance(raw, list):
        raise HTTPException(status_code=400, detail="startup_ids array required")
    try:
        max_n = int(os.getenv("META_PROMPT_EVAL_SET_MAX", "50"))
    except ValueError:
        max_n = 50
    startup_repository = _get_startup_repository(request)
    validated: List[str] = []
    missing: List[str] = []
    seen: set[str] = set()
    for value in raw:
        sid = str(value).strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        if len(validated) >= max_n:
            break
        if await startup_repository.exists(uid, sid):
            validated.append(sid)
        else:
            missing.append(sid)
    payload = await _batch1_call(request, save_eval_startup_ids, uid, validated, max_n=max_n)
    return {"ok": True, **payload, "missing_startup_ids": missing[:30]}


def _put_eval_set_sync(uid: str, raw: List[Any], max_n: int, storage):
    validated: List[str] = []
    missing: List[str] = []
    seen: set[str] = set()
    for x in raw:
        sid = str(x).strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        if len(validated) >= max_n:
            break
        if storage.get_startup(sid):
            validated.append(sid)
        else:
            missing.append(sid)
    payload = save_eval_startup_ids(uid, validated, max_n=max_n)
    return {"ok": True, **payload, "missing_startup_ids": missing[:30]}


@router.post("/api/meta/prompts/evaluate")
async def post_meta_prompt_evaluate(request: Request):
    """
    Shadow-run a pending reviewer prompt against the eval set (or startup_ids override).
    Persists pass/fail summary for optional META_PROMPT_REQUIRE_EVAL_PASS promote gate.
    """
    uid = request.state.user_id
    try:
        body = await request.json()
    except Exception:
        body = {}
    agent_target = str(body.get("agent_target") or "").strip()
    library_key = str(body.get("library_key") or "").strip()
    if not agent_target or not library_key:
        raise HTTPException(status_code=400, detail="agent_target and library_key required")
    if agent_target not in REVIEWER_EVAL_AGENT_TARGETS:
        raise HTTPException(
            status_code=400,
            detail="agent_target must be DefaultReviewer, SkepticalReviewer, or OpportunistReviewer",
        )
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY required for evaluation")

    startup_repository = _get_startup_repository(request)
    storage = StartupReadStorageAdapter(None, await startup_repository.load_snapshot(uid))
    pool = getattr(request.app.state, "durable_job_pool", None)
    repository = Batch1Repository(pool) if pool is not None else None
    state = await repository.load_state(uid) if repository is not None else None
    token = set_state(state) if state is not None else None
    try:
        intelligence = getattr(request.app.state, "fund_intelligence_repository", None)
        thesis_repository = getattr(intelligence, "thesis_repository", None)
        if thesis_repository is None:
            raise HTTPException(status_code=503, detail="PostgreSQL thesis repository is unavailable")
        thesis = await get_active_thesis_from_repository(thesis_repository, uid)
        if thesis is None:
            await bootstrap_default_thesis_with_repository(thesis_repository, uid)
            thesis = await get_active_thesis_from_repository(thesis_repository, uid)
        thesis_ctx = thesis.as_engine_context() if thesis else None
        reviewer_model = os.getenv("REVIEWER_MODEL", "gpt-5-nano")
        reviewer_engine = ReviewerEngine(
            api_key=api_key,
            storage=storage,
            tenant_user_id=uid,
            model=reviewer_model,
            active_thesis=thesis_ctx,
            startup_repository=startup_repository,
        )
        override_ids = body.get("startup_ids")
        sid_list: Optional[List[str]] = None
        if isinstance(override_ids, list):
            sid_list = [str(x).strip() for x in override_ids if str(x).strip()]
        result = await run_prompt_evaluation(
            user_id=uid,
            agent_target=agent_target,
            library_key=library_key,
            storage=storage,
            reviewer_engine=reviewer_engine,
            startup_ids=sid_list,
        )
        return result
    except FundThesisIncompleteError as e:
        raise HTTPException(status_code=400, detail=str(e) or "fund thesis incomplete")
    finally:
        if repository is not None and state is not None:
            try:
                await repository.persist_state(state)
            finally:
                reset_state(token)


@router.get("/api/meta/weights")
async def get_meta_weights(request: Request):
    """
    Return current scout weights used by the Meta-Agent reweighter.
    """
    return await _batch1_call(request, load_weights, request.state.user_id)


@router.get("/api/meta/calibration")
async def get_meta_calibration(request: Request):
    """
    Return current calibration state for reviewer thresholds.
    """
    state = await _batch1_call(request, load_calibration_state, request.state.user_id)
    if not isinstance(state, dict):
        return {}
    return state
