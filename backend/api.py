"""
FastAPI server for Aethria.
Serves app-front-end: GET /api/startups, GET/PATCH /settings.
(Web-front-end waitlist uses Vercel serverless /api/waitlist.)
"""
import json
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from storage import Storage
from settings_loader import DEFAULT_SETTINGS, get_settings_path, load_settings, get_meta_agent_settings
from memo_generator import MemoGenerator
from meta_agent.agent import MetaAgent  # For manual trigger
from meta_agent.mutator import _PROMPT_LIBRARY_PATH, _read_json_dict, _read_json_list
from meta_agent.reweighter import load_weights
from meta_agent.calibrator import load_calibration_state
from portfolio.store import PortfolioStore
from portfolio.cost_control import CostController

app = FastAPI(title="Aethria API")

# CORS: localhost for dev; extend with ALLOWED_ORIGINS (comma-separated) for production domain
_cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]
_extra = os.getenv("ALLOWED_ORIGINS", "")
if _extra:
    _cors_origins.extend(o.strip() for o in _extra.split(",") if o.strip())
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "PATCH", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def _now_iso() -> str:
    """Return current time as ISO 8601 string in UTC."""
    return datetime.now(timezone.utc).isoformat()


def _get_root() -> Path:
    return Path(__file__).resolve().parent


def _get_portfolio_store() -> PortfolioStore:
    """Return a PortfolioStore rooted at data/portfolio."""
    root = _get_root()
    return PortfolioStore(data_dir=str(root / "data" / "portfolio"))


def _read_json_list(path: Path) -> List[Dict[str, Any]]:
    """Best-effort JSON list reader. Returns [] on missing/invalid files."""
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _read_json_dict_file(path: Path) -> Dict[str, Any]:
    """Best-effort JSON dict reader. Returns {} on missing/invalid files."""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _get_pending_escalations(storage: Storage) -> List[Dict[str, Any]]:
    """
    Return raw startup dicts where partner_info.human_review_required is True
    and no human_resolution has been recorded.
    """
    raw = storage.get_all()
    pending: List[Dict[str, Any]] = []
    for item in raw:
        partner = item.get("partner_info") or item.get("partner")
        if not partner:
            continue
        if not partner.get("human_review_required"):
            continue
        human_resolution = item.get("human_resolution")
        if human_resolution and human_resolution.get("resolved_at"):
            continue
        pending.append(item)
    return pending


def _get_system_health(storage: Storage) -> Dict[str, Any]:
    """
    Assemble system health object from multiple backend sources.
    Mirrors the shape expected by the front-end SystemHealth type.
    """
    # Calibration warning from portfolio agent_metrics
    portfolio_store = _get_portfolio_store()
    metrics_file = portfolio_store.files.get("agent_metrics")
    calibration_warning = None
    if metrics_file is not None:
        metrics = _read_json_list(metrics_file)
        for m in metrics:
            if m.get("id") == "verdict_distribution":
                calibration_warning = m.get("calibration_warning")
                break

    # Pending escalations based on startups requiring human review
    pending_escalations = len(_get_pending_escalations(storage))

    # Queue depths
    try:
        unreviewed = storage.count_unreviewed()
    except Exception:
        unreviewed = 0
    try:
        undecided = storage.count_undecided()
    except Exception:
        undecided = 0
    try:
        watchlist = len(portfolio_store.get_all_watchlist())
    except Exception:
        watchlist = 0

    # Budget status per agent from CostController
    cost_controller = CostController()
    all_budgets: Dict[str, Any] = getattr(cost_controller, "budgets", {}) or {}
    budget_status: List[Dict[str, Any]] = []
    for agent_type, defaults in cost_controller.default_budgets.items():
        agent_budget = all_budgets.get(agent_type, {})
        calls_today = agent_budget.get("calls_today", 0)
        tokens_today = agent_budget.get("tokens_today", 0)
        last_calls = agent_budget.get("last_call_time") or {}
        if not isinstance(last_calls, dict):
            last_calls = {}
        if not last_calls:
            budget_status.append(
                {
                    "agent_id": agent_type,
                    "daily_calls_used": calls_today,
                    "daily_calls_limit": defaults.get("calls", 0),
                    "daily_tokens_used": tokens_today,
                    "daily_tokens_limit": defaults.get("tokens", 0),
                    "in_cooldown": False,
                    "cooldown_until": None,
                }
            )
            continue
        for agent_id, last_call_str in last_calls.items():
            try:
                last_call_time = datetime.fromisoformat(last_call_str)
                cooldown_seconds = cost_controller.cooldowns.get(agent_type, 60)
                delta = (datetime.now() - last_call_time).total_seconds()
                in_cooldown = delta < cooldown_seconds
                cooldown_until = (
                    (last_call_time.replace(tzinfo=timezone.utc) + timedelta(seconds=cooldown_seconds)).isoformat()
                    if in_cooldown
                    else None
                )
            except Exception:
                in_cooldown = False
                cooldown_until = None
            budget_status.append(
                {
                    "agent_id": str(agent_id),
                    "daily_calls_used": calls_today,
                    "daily_calls_limit": defaults.get("calls", 0),
                    "daily_tokens_used": tokens_today,
                    "daily_tokens_limit": defaults.get("tokens", 0),
                    "in_cooldown": in_cooldown,
                    "cooldown_until": cooldown_until,
                }
            )

    return {
        "calibration_warning": calibration_warning,
        "pending_escalations": pending_escalations,
        "queue_depths": {
            "unreviewed": unreviewed,
            "undecided": undecided,
            "watchlist": watchlist,
        },
        "budget_status": budget_status,
    }

def _save_settings(data: dict) -> None:
    path = get_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _validate_settings(body: dict) -> list[str]:
    errors = []
    cb = body.get("cost_budget")
    if cb is not None:
        if not isinstance(cb, dict):
            errors.append("cost_budget must be an object")
        else:
            if "max_tokens_per_run" in cb and (not isinstance(cb["max_tokens_per_run"], (int, float)) or cb["max_tokens_per_run"] < 0):
                errors.append("cost_budget.max_tokens_per_run must be a non-negative number")
            if "daily_cost_ceiling" in cb and (not isinstance(cb["daily_cost_ceiling"], (int, float)) or cb["daily_cost_ceiling"] < 0):
                errors.append("cost_budget.daily_cost_ceiling must be a non-negative number")
            if "weekly_cost_ceiling" in cb and (not isinstance(cb["weekly_cost_ceiling"], (int, float)) or cb["weekly_cost_ceiling"] < 0):
                errors.append("cost_budget.weekly_cost_ceiling must be a non-negative number")
            if "cooldown_seconds" in cb and (not isinstance(cb["cooldown_seconds"], (int, float)) or cb["cooldown_seconds"] < 0):
                errors.append("cost_budget.cooldown_seconds must be a non-negative number")
    ac = body.get("agent_config")
    if ac is not None:
        if not isinstance(ac, dict):
            errors.append("agent_config must be an object")
        else:
            if "scouts_enabled" in ac and not isinstance(ac["scouts_enabled"], bool):
                errors.append("agent_config.scouts_enabled must be a boolean")
            if "reviewers_enabled" in ac and not isinstance(ac["reviewers_enabled"], bool):
                errors.append("agent_config.reviewers_enabled must be a boolean")
            if "partners_enabled" in ac and not isinstance(ac["partners_enabled"], bool):
                errors.append("agent_config.partners_enabled must be a boolean")
            if "max_agents_per_run" in ac and (not isinstance(ac["max_agents_per_run"], (int, float)) or ac["max_agents_per_run"] < 1):
                errors.append("agent_config.max_agents_per_run must be at least 1")
            if "confidence_threshold" in ac:
                v = ac["confidence_threshold"]
                if not isinstance(v, (int, float, str)):
                    errors.append("agent_config.confidence_threshold must be a number or string")
                elif isinstance(v, (int, float)) and (v < 0 or v > 1):
                    errors.append("agent_config.confidence_threshold must be between 0 and 1 when numeric")
            # Scout-specific config
            if "scout_region" in ac:
                if not isinstance(ac["scout_region"], str):
                    errors.append("agent_config.scout_region must be a string")
                elif ac["scout_region"] not in ("europe", "global"):
                    errors.append("agent_config.scout_region must be one of: europe, global")
            if "scout_serp_enabled" in ac and not isinstance(ac["scout_serp_enabled"], bool):
                errors.append("agent_config.scout_serp_enabled must be a boolean")
            if "scout_serp_daily_budget" in ac:
                v = ac["scout_serp_daily_budget"]
                if not isinstance(v, (int, float)) or v < 0:
                    errors.append("agent_config.scout_serp_daily_budget must be a non-negative number")
    pf = body.get("portfolio")
    if pf is not None:
        if not isinstance(pf, dict):
            errors.append("portfolio must be an object")
        else:
            if "auto_watchlist" in pf and not isinstance(pf["auto_watchlist"], bool):
                errors.append("portfolio.auto_watchlist must be a boolean")
            if "signal_scan_frequency" in pf and not isinstance(pf["signal_scan_frequency"], str):
                errors.append("portfolio.signal_scan_frequency must be a string")
            if "memo_verbosity" in pf and not isinstance(pf["memo_verbosity"], str):
                errors.append("portfolio.memo_verbosity must be a string")
    return errors


def _to_iso(v) -> str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v) if v else None


def _backend_to_frontend(raw: dict) -> dict:
    """Transform backend startup dict to app-front-end Startup shape."""
    sid = raw.get("startup_id", "")
    scout = raw.get("scout_info") or {}
    review = raw.get("review_info")
    partner = raw.get("partner_info")

    timestamps = {}
    if scout.get("discovered_at"):
        timestamps["discovered_at"] = _to_iso(scout["discovered_at"])
    if review and review.get("reviewed_at"):
        timestamps["reviewed_at"] = _to_iso(review["reviewed_at"])
    if partner and partner.get("partnered_at"):
        timestamps["partnered_at"] = _to_iso(partner["partnered_at"])

    out = {
        "id": sid,
        "scout": {
            "id": sid,
            "scout_type": scout.get("scout_type", "market_driven"),
            "name": scout.get("name", ""),
            "one_line": scout.get("one_line", ""),
            "sector": scout.get("sector", ""),
            "problem": scout.get("problem"),
            "solution": scout.get("solution"),
            "target_users": scout.get("target_users"),
            "why_now": scout.get("why_now", ""),
            "confidence": scout.get("confidence_score", 0.5),
            "funding_stage": scout.get("funding_stage"),
            "est_tam": scout.get("est_tam"),
            "references": scout.get("references") or [],
        },
        "timestamps": timestamps,
    }

    if review:
        out["review"] = {
            "market_score": review.get("market_score"),
            "product_score": review.get("product_score"),
            "technical_score": review.get("technical_score"),
            "execution_score": review.get("execution_score"),
            "defensibility_score": review.get("defensibility_score"),
            "overall_summary": review.get("overall_summary"),
            "key_risks": review.get("key_risks") or [],
            "verdict": review.get("verdict"),
            "score_reasoning": review.get("score_reasoning") or None,
            "diligence_red_flags": review.get("diligence_red_flags") or [],
            "assumption_feedback": review.get("assumption_feedback") or [],
            "team_analysis": review.get("team_analysis") or None,
            "competition_analysis": review.get("competition_analysis") or None,
            "business_model_analysis": review.get("business_model_analysis") or None,
            "investment_thesis": review.get("investment_thesis") or None,
            "risk_mitigation": review.get("risk_mitigation") or None,
        }
    else:
        out["review"] = None

    if partner:
        out["partner"] = {
            "decision": partner.get("decision", "NO"),
            "confidence": partner.get("conviction_level"),
            "rationale": partner.get("rationale"),
            "next_action": partner.get("next_action"),
            "human_review_required": partner.get("human_review_required", False),
        }
    else:
        out["partner"] = None

    return out


def _get_storage() -> Storage:
    storage_path = os.getenv("STORAGE_PATH", "data/startups.json")
    root = _get_root()
    path = root / storage_path if not Path(storage_path).is_absolute() else Path(storage_path)
    return Storage(file_path=str(path))


@app.get("/api/startups")
def get_startups():
    storage = _get_storage()
    raw_list = storage.get_all()
    return [_backend_to_frontend(r) for r in raw_list]


@app.get("/api/startups/{startup_id}/memo")
def get_startup_memo(startup_id: str):
    """Return full investment memo (markdown) for a startup from MemoGenerator."""
    storage = _get_storage()
    startup = storage.get_startup(startup_id)
    if not startup:
        raise HTTPException(status_code=404, detail="Startup not found")
    memo = MemoGenerator().generate_memo(startup, for_display=True)
    return {"memo": memo}


@app.get("/health")
def health():
    """Lightweight health check with pending escalations count."""
    storage = _get_storage()
    pending = len(_get_pending_escalations(storage))
    return {"status": "ok", "pending_escalations": pending}


@app.get("/api/settings")
def get_settings():
    """Return current settings (control plane)."""
    settings = load_settings()
    # Surface Meta-Agent configuration derived from environment variables
    # so the front-end can display current meta-control knobs.
    meta_agent = get_meta_agent_settings()
    meta_agent["model"] = os.getenv("META_AGENT_MODEL", "gpt-5-nano")
    settings["meta_agent"] = meta_agent

    # Embed latest system health snapshot inline so the front-end can avoid extra calls.
    storage = _get_storage()
    settings["system_health"] = _get_system_health(storage)
    return settings


@app.patch("/api/settings")
def patch_settings(body: dict):
    """Update settings. Validates server-side; returns 422 on validation errors."""
    errors = _validate_settings(body)
    if errors:
        raise HTTPException(status_code=422, detail={"message": "Validation failed", "errors": errors})
    current = load_settings()
    for section in ("cost_budget", "agent_config", "portfolio"):
        if section in body and isinstance(body[section], dict):
            if section not in current:
                current[section] = {}
            for k, v in body[section].items():
                current[section][k] = v
    _save_settings(current)
    # Meta-Agent settings are derived from environment; PATCH does not
    # persist or validate them, but we still include the live view.
    meta_agent = get_meta_agent_settings()
    meta_agent["model"] = os.getenv("META_AGENT_MODEL", "gpt-5-nano")
    current["meta_agent"] = meta_agent
    return current


@app.get("/api/meta/reports")
def get_meta_reports():
    """
    Return the last 10 Meta-Agent cycle reports.
    """
    reports = _read_json_list(_PROMPT_LIBRARY_PATH.parent / "meta_reports.json")
    if not isinstance(reports, list):
        return []
    # Return most recent first
    return list(reversed(reports[-10:]))


@app.get("/api/meta/prompt-library")
def get_meta_prompt_library():
    """
    Return the full prompt library used by the Meta-Agent.
    """
    library = _read_json_dict(_PROMPT_LIBRARY_PATH)
    if not isinstance(library, dict):
        return {}
    return library


@app.get("/api/meta/weights")
def get_meta_weights():
    """
    Return current scout weights used by the Meta-Agent reweighter.
    """
    return load_weights()


@app.get("/api/meta/calibration")
def get_meta_calibration():
    """
    Return current calibration state for reviewer thresholds.
    """
    state = load_calibration_state()
    if not isinstance(state, dict):
        return {}
    return state


@app.post("/api/meta/trigger")
async def trigger_meta_cycle():
    """
    Manually trigger a Meta-Agent cycle.

    Returns a lightweight status object with the cycle number. When the
    Meta-Agent is disabled or returns no report, we surface a no-op
    status so the UI can display a graceful message.
    """
    agent = MetaAgent()
    report = await agent.run_cycle()
    if not report:
        return {"status": "no-op", "cycle_number": 0}
    cycle_number = int(report.get("cycle_number", 0))
    return {"status": "ok", "cycle_number": cycle_number}


@app.get("/api/escalations")
async def get_escalations():
    """
    Returns all startups where human_review_required=True and human_resolution is None.
    Shapes each result as an escalation summary for the System Intelligence panel.
    """
    storage = _get_storage()
    pending_raw = _get_pending_escalations(storage)
    items: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for item in pending_raw:
        scout = item.get("scout_info") or {}
        partner = item.get("partner_info") or {}
        startup_id = item.get("startup_id") or scout.get("startup_id") or item.get("id")
        name = scout.get("name", "")
        sector = scout.get("sector", "")
        decision = partner.get("decision")
        conviction = partner.get("conviction_level") or partner.get("confidence")
        rationale = partner.get("rationale")
        llm_reason = partner.get("llm_fallback_reason")
        human_required = bool(partner.get("human_review_required", False))
        partnered_at = partner.get("partnered_at")
        days_pending = None
        escalated_at = None
        try:
            if partnered_at:
                dt = datetime.fromisoformat(str(partnered_at))
                if not dt.tzinfo:
                    dt = dt.replace(tzinfo=timezone.utc)
                escalated_at = dt.isoformat()
                days_pending = (now - dt).days
        except Exception:
            days_pending = None
            escalated_at = None

        items.append(
            {
                "startup_id": startup_id,
                "startup_name": name,
                "sector": sector,
                "partner_decision": decision,
                "conviction_level": conviction,
                "rationale": rationale,
                "llm_fallback_reason": llm_reason,
                "human_review_required": human_required,
                "escalated_at": escalated_at,
                "days_pending": days_pending,
                "human_resolution": item.get("human_resolution"),
            }
        )
    return items


@app.post("/api/escalations/{startup_id}/resolve")
async def resolve_escalation(startup_id: str, body: Dict[str, Any]):
    """
    Resolve an escalation by writing human_resolution to startups.json.
    Body: {decision: "YES"|"NO"|"MAYBE", notes: str}
    """
    decision = str(body.get("decision", "")).upper()
    notes = body.get("notes") or ""
    if decision not in ("YES", "NO", "MAYBE"):
        raise HTTPException(status_code=422, detail="decision must be YES, NO, or MAYBE")

    storage = _get_storage()
    found = {"value": False}

    def _updater(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        for i, item in enumerate(data):
            if item.get("startup_id") == startup_id:
                hr = {
                    "decision": decision,
                    "notes": notes,
                    "resolved_at": _now_iso(),
                }
                new_item = dict(item)
                new_item["human_resolution"] = hr
                data[i] = new_item
                found["value"] = True
                break
        return data

    try:
        storage._atomic_update(_updater)  # type: ignore[attr-defined]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve escalation: {e}")

    if not found["value"]:
        raise HTTPException(status_code=404, detail="Startup not found")

    return {"status": "ok"}


@app.get("/api/signals")
async def get_signals():
    """
    Return the last 50 portfolio signals sorted by detected_at descending.
    """
    store = _get_portfolio_store()
    signals_file = store.files.get("signals")
    records = _read_json_list(signals_file) if signals_file is not None else []
    # Attach startup names where possible
    startups_index = {s.get("id"): s for s in store.get_all_startups()}
    for r in records:
        sid = r.get("startup_id")
        startup = startups_index.get(sid or "")
        if startup and "startup_name" not in r:
            r["startup_name"] = startup.get("name")
    records.sort(key=lambda r: r.get("detected_at", ""), reverse=True)
    return records[:50]


@app.get("/api/analytics/rejections")
async def get_rejection_analytics():
    """
    Return rejection analytics summarising red flags, sectors, and scores.
    """
    root = _get_root()
    patterns_path = root / "data" / "portfolio" / "rejection_patterns.json"
    patterns = _read_json_dict_file(patterns_path)
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


@app.get("/api/analytics/watchlist")
async def get_watchlist_analytics():
    """
    Return watchlist health analytics: total, stale, average days, and per-entry stats.
    """
    store = _get_portfolio_store()
    try:
        watchlist = store.get_all_watchlist()
    except Exception:
        watchlist = []

    total = len(watchlist)
    if total == 0:
        return {"total": 0, "stale": 0, "avg_days": 0, "entries": []}

    now = datetime.now(timezone.utc)
    # Build signal index
    signals_file = store.files.get("signals")
    signals = _read_json_list(signals_file) if signals_file is not None else []
    signal_counts: Dict[str, int] = {}
    for s in signals:
        sid = s.get("startup_id")
        if not sid:
            continue
        signal_counts[sid] = signal_counts.get(sid, 0) + 1

    startups_index = {s.get("id"): s for s in store.get_all_startups()}

    stale = 0
    days_total = 0
    entries: List[Dict[str, Any]] = []

    for entry in watchlist:
        sid = entry.get("startup_id")
        startup = startups_index.get(sid or "")
        name = startup.get("name") if startup else ""
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


@app.get("/api/analytics/concentration")
async def get_concentration_analytics():
    """
    Return sector concentration analytics from data/analytics/sector_concentration.json.
    """
    root = _get_root()
    path = root / "data" / "analytics" / "sector_concentration.json"
    data = _read_json_dict_file(path)
    if not data:
        return {
            "by_sector": {},
            "most_concentrated_sector": "",
            "most_concentrated_theme": "",
            "last_updated": "",
        }
    return data


@app.get("/api/analytics/system-health")
async def get_system_health():
    """
    Aggregate system health metrics (calibration, queues, budgets, escalations).
    """
    storage = _get_storage()
    return _get_system_health(storage)
