"""Analytics, signals, and activity-summary routes.

Split out of api.py. Read-only aggregations plus the activity-seen marker. The
shared read/system-health helpers live in routers/deps.py.
"""
import asyncio
import inspect
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

import env_config
from security.request_guards import require_authenticated_user
from portfolio.rejection import RejectionAnalyzer
from routers.deps import (
    enforce_rate_limits as _enforce_rate_limits,
    SETTINGS_MUTATION_POLICY as _SETTINGS_MUTATION_POLICY,
    get_root as _get_root,
    get_portfolio_store as _get_portfolio_store,
    read_json_dict_file as _read_json_dict_file,
    get_system_health as _get_system_health,
)
from user_state.repository import UserStateRepository
from utils.settings_loader import load_settings
from settings_repository import SettingsRepository
from batch1.context import reset_state, set_state
from batch1.repository import Batch1Repository
from batch4a.repository import Batch4ARepository
from startup_repository import StartupRepository

logger = logging.getLogger("api.analytics")
router = APIRouter()


def _aggregate_activity_totals(
    activity_rows: List[Dict[str, Any]],
    *,
    human_reviewed: int = 0,
    open_in_progress: int = 0,
) -> Dict[str, int]:
    totals = {
        "found": 0,
        "reviewed": 0,
        "decided": 0,
        "agent_decided": 0,
        "human_reviewed": max(0, int(human_reviewed or 0)),
        "open_in_progress": max(0, int(open_in_progress or 0)),
        "escalations": 0,
    }
    for r in activity_rows:
        totals["found"] += int(r.get("startups_found", 0) or 0)
        totals["reviewed"] += int(r.get("reviewed_count", 0) or 0)
        totals["agent_decided"] += int(r.get("decisions_made", 0) or 0)
        totals["escalations"] += int(r.get("escalations_count", 0) or 0)
    totals["decided"] = totals["agent_decided"]
    return totals

@router.get("/api/signals")
async def get_signals(request: Request):
    """
    Return the last 50 portfolio signals sorted by detected_at descending.
    Startup names come from request-scoped storage (Supabase) so they are user-correct.
    """
    store = _get_portfolio_store(request.state.user_id)
    signals_file = store.files.get("signals")
    records = store._read_file(signals_file) if signals_file is not None else []
    # Attach startup names from request-scoped storage (user's startups)
    rows = await StartupRepository(getattr(request.app.state, "durable_job_pool", None)).list_projection(
        request.state.user_id, limit=500, offset=0
    )
    startups_index = {
        str(row.get("startup_id")): str(row.get("display_name") or (row.get("scout_info") or {}).get("name") or "")
        for row in rows
    }
    for r in records:
        if "startup_name" not in r:
            r["startup_name"] = startups_index.get(r.get("startup_id") or "", "")
    records.sort(key=lambda r: r.get("detected_at", ""), reverse=True)
    return records[:50]


@router.get("/api/analytics/rejections")
def get_rejection_analytics(request: Request):
    """
    Return rejection analytics summarising red flags, sectors, and scores (tenant-scoped).
    """
    root = _get_root()
    uid = request.state.user_id
    analyzer = RejectionAnalyzer(
        data_dir=str(root / "data" / "portfolio"),
        user_id=uid,
    )
    patterns = analyzer.get_patterns()
    if not patterns:
        return {
            "most_common_red_flags": [],
            "rejection_by_sector": {},
            "avg_scores_at_rejection": {},
            "most_common_fail_dimensions": [],
        }

    # Red flags as-is from analyzer
    red_flags = patterns.get("most_common_red_flags") or []
    if not isinstance(red_flags, list):
        red_flags = []

    # Rejection by sector: add pct_of_total
    by_sector_raw = patterns.get("rejection_by_sector") or {}
    if not isinstance(by_sector_raw, dict):
        by_sector_raw = {}
    total_rejections = patterns.get("_rejection_count", 0) or 0
    rejection_by_sector: Dict[str, Any] = {}
    for sector, count in by_sector_raw.items():
        try:
            c = int(count)
        except Exception:
            continue
        pct = (c / total_rejections * 100.0) if total_rejections > 0 else 0.0
        rejection_by_sector[sector] = {"count": c, "pct_of_total": round(pct, 2)}

    avg_scores = patterns.get("avg_scores_at_rejection") or {}
    if not isinstance(avg_scores, dict):
        avg_scores = {}

    fail_dims_raw = patterns.get("most_common_fail_dimensions") or []
    if isinstance(fail_dims_raw, list) and fail_dims_raw and isinstance(fail_dims_raw[0], dict):
        most_common_fail_dimensions = [d.get("dimension", "") for d in fail_dims_raw if d.get("dimension")]
    elif isinstance(fail_dims_raw, list):
        most_common_fail_dimensions = [str(d) for d in fail_dims_raw]
    else:
        most_common_fail_dimensions = []

    return {
        "most_common_red_flags": red_flags,
        "rejection_by_sector": rejection_by_sector,
        "avg_scores_at_rejection": avg_scores,
        "most_common_fail_dimensions": most_common_fail_dimensions,
    }


@router.get("/api/analytics/watchlist")
async def get_watchlist_analytics(request: Request):
    """
    Return watchlist health analytics: total, stale, average days, and per-entry stats.
    Startup names come from request-scoped storage so they are user-correct.
    """
    store = _get_portfolio_store(request.state.user_id)
    try:
        watchlist = store.get_all_watchlist()
    except Exception:
        watchlist = []

    total = len(watchlist)
    if total == 0:
        return {"total": 0, "stale": 0, "avg_days": 0, "entries": []}

    now = datetime.now(timezone.utc)
    # Build signal index (Supabase)
    signals_file = store.files.get("signals")
    signals = store._read_file(signals_file) if signals_file is not None else []
    signal_counts: Dict[str, int] = {}
    for s in signals:
        sid = s.get("startup_id")
        if not sid:
            continue
        signal_counts[sid] = signal_counts.get(sid, 0) + 1

    # Startup names from request-scoped storage (user's startups)
    rows = await StartupRepository(getattr(request.app.state, "durable_job_pool", None)).list_projection(
        request.state.user_id, limit=500, offset=0
    )
    startups_index = {
        str(row.get("startup_id")): str(row.get("display_name") or (row.get("scout_info") or {}).get("name") or "")
        for row in rows
    }

    stale = 0
    days_total = 0
    entries: List[Dict[str, Any]] = []

    for entry in watchlist:
        sid = entry.get("startup_id")
        name = startups_index.get(sid or "", "")
        added_at_str = entry.get("added_at")
        days_on_watchlist = 0
        try:
            if added_at_str:
                dt = datetime.fromisoformat(added_at_str)
                if not dt.tzinfo:
                    dt = dt.replace(tzinfo=timezone.utc)
                days_on_watchlist = (now - dt).days
        except Exception:
            days_on_watchlist = 0
        days_total += days_on_watchlist
        stale_flag = bool(entry.get("stale_warning", False))
        if stale_flag:
            stale += 1
        entries.append(
            {
                "startup_id": sid,
                "startup_name": name,
                "days_on_watchlist": days_on_watchlist,
                "stale_warning": stale_flag,
                "signal_count": signal_counts.get(sid or "", 0),
            }
        )

    avg_days = days_total / total if total > 0 else 0.0
    return {"total": total, "stale": stale, "avg_days": avg_days, "entries": entries}


@router.get("/api/analytics/concentration")
async def get_concentration_analytics(request: Request):
    """
    Return sector concentration analytics from data/analytics/sector_concentration.json.
    """
    root = _get_root()
    path = root / "data" / "analytics" / "sector_concentration.json"
    user_id = getattr(request.state, "user_id", None)
    pool = getattr(request.app.state, "durable_job_pool", None)
    repository = Batch1Repository(pool) if pool is not None else None
    state = await repository.load_state(user_id) if repository is not None else None
    token = set_state(state) if state is not None else None
    try:
        data = _read_json_dict_file(path, user_id=user_id)
    finally:
        if repository is not None and state is not None:
            try:
                await repository.persist_state(state)
            finally:
                reset_state(token)
    if not data:
        return {
            "by_sector": {},
            "most_concentrated_sector": "",
            "most_concentrated_theme": "",
            "last_updated": "",
        }
    return data


@router.get("/api/analytics/system-health")
async def get_system_health(request: Request):
    """
    Aggregate system health metrics (calibration, queues, budgets, escalations).
    """
    user_id = getattr(request.state, "user_id", None)
    pool = getattr(request.app.state, "durable_job_pool", None)
    startup_repository = StartupRepository(pool)
    settings = await load_settings(
        user_id, repository=SettingsRepository(pool)
    )
    repository = Batch1Repository(pool) if pool is not None else None
    state = await repository.load_state(user_id) if repository is not None else None
    token = set_state(state) if state is not None else None
    try:
        return _get_system_health(
            None,
            user_id=user_id,
            settings=settings,
            pending_escalations=len(await startup_repository.list_pending_escalations(user_id)),
            unreviewed=await startup_repository.count_unreviewed(user_id),
            undecided=await startup_repository.count_undecided(user_id),
        )
    finally:
        if repository is not None and state is not None:
            try:
                await repository.persist_state(state)
            finally:
                reset_state(token)


@router.get("/api/activity/summary")
async def get_activity_summary(request: Request):
    """
    Return aggregated pipeline activity since the user's last visit.
    Does NOT update last_seen_at — that only happens when the client explicitly
    acknowledges a report or records the start of an away window.
    """
    user_id: str = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    pool = getattr(getattr(request, "app", None), "state", None)
    pool = getattr(pool, "durable_job_pool", None)
    if pool is None:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "reason": "durable_job_store_unavailable",
            },
        )
    try:
        last_seen_value = await UserStateRepository(pool).get_last_seen_at(user_id)
        last_seen_at = last_seen_value.isoformat() if last_seen_value is not None else None
    except Exception:
        last_seen_at = None

    activity_rows = await Batch4ARepository(pool).list_pipeline_activity_since(user_id, last_seen_at)
    since = last_seen_at or "1970-01-01T00:00:00Z"
    startup_repository = StartupRepository(pool)
    human_reviewed = await startup_repository.count_human_reviewed_since(user_id, since)
    open_in_progress = await startup_repository.count_unresolved(user_id)
    totals, last_seen_at = await asyncio.to_thread(
        _activity_summary_totals_sync, user_id, last_seen_at, activity_rows,
        human_reviewed, open_in_progress,
    )

    logging.getLogger("api").info(
        "activity_summary user_id=%s since=%s agent_decided=%s human_reviewed=%s open_in_progress=%s",
        user_id[:24],
        last_seen_at,
        totals["agent_decided"],
        totals["human_reviewed"],
        totals["open_in_progress"],
    )

    # Reading is side-effect free; the client advances the boundary explicitly.
    return JSONResponse(content=totals)


def _activity_summary_totals_sync(
    user_id: str, last_seen_at: Optional[str], activity_rows: Optional[List[Dict[str, Any]]] = None,
    human_reviewed_override: Optional[int] = None, open_in_progress_override: Optional[int] = None,
):
    # The user_state read is performed asynchronously by the route.
    if not last_seen_at:
        # First visit — include all historical pipeline activity
        last_seen_at = "1970-01-01T00:00:00Z"

    activity_rows = activity_rows or []

    # 3. Aggregate totals. "decided" is retained as a backwards-compatible
    # alias for agent_decided; human decisions are counted separately.
    human_reviewed = int(human_reviewed_override or 0)
    open_in_progress = int(open_in_progress_override or 0)

    # Startup counts are supplied by the async StartupRepository boundary.
    # There is intentionally no synchronous Supabase fallback here.

    totals = _aggregate_activity_totals(
        activity_rows,
        human_reviewed=human_reviewed,
        open_in_progress=open_in_progress,
    )
    return totals, last_seen_at


@router.post("/api/activity/seen")
async def mark_activity_seen(request: Request):
    """Mark the current time as the report boundary / start of an away window."""
    user_id = require_authenticated_user(request)
    limited_result = _enforce_rate_limits(
        f"user:{user_id}:settings_mutation", [_SETTINGS_MUTATION_POLICY]
    )
    limited = await limited_result if inspect.isawaitable(limited_result) else limited_result
    if limited is not None:
        return limited
    try:
        pool = getattr(getattr(request, "app", None), "state", None)
        pool = getattr(pool, "durable_job_pool", None)
        await UserStateRepository(pool).upsert_last_seen_at(
            user_id, datetime.now(timezone.utc)
        )
    except Exception as e:
        logging.getLogger("api").warning("Could not update user_state last_seen_at: %s", e)
        return JSONResponse(status_code=503, content={"ok": False, "detail": "activity marker unavailable"})
    return JSONResponse(content={"ok": True})
