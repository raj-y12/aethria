"""
FastAPI server for Aethria.
Serves app-front-end: GET /api/startups, GET/PATCH /settings.
(Web-front-end waitlist uses Vercel serverless /api/waitlist.)
"""
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from storage import Storage
from settings_loader import DEFAULT_SETTINGS, get_settings_path, load_settings
from memo_generator import MemoGenerator

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
    allow_methods=["GET", "PATCH", "POST"],
    allow_headers=["*"],
)

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

    scout_block = {
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
    }
    if scout.get("prompt_version"):
        scout_block["prompt_version"] = scout["prompt_version"]

    out = {
        "id": sid,
        "scout": scout_block,
        "timestamps": timestamps,
    }

    if review:
        review_block = {
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
        if review.get("prompt_version"):
            review_block["prompt_version"] = review["prompt_version"]
        out["review"] = review_block
    else:
        out["review"] = None

    if partner:
        partner_block = {
            "decision": partner.get("decision", "NO"),
            "confidence": partner.get("conviction_level"),
            "rationale": partner.get("rationale"),
            "next_action": partner.get("next_action"),
            "human_review_required": partner.get("human_review_required", False),
        }
        if partner.get("prompt_version"):
            partner_block["prompt_version"] = partner["prompt_version"]
        out["partner"] = partner_block
    else:
        out["partner"] = None

    return out


def _get_storage() -> Storage:
    storage_path = os.getenv("STORAGE_PATH", "data/startups.json")
    root = Path(__file__).resolve().parent
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
    storage = _get_storage()
    all_startups = storage.get_all_startups(skip_invalid=True)
    pending = sum(
        1 for s in all_startups
        if s.partner_info and s.partner_info.human_review_required and s.human_resolution is None
    )
    return {"status": "ok", "pending_escalations": pending}


@app.get("/api/escalations")
def get_escalations():
    """Return startups requiring human review that haven't been resolved."""
    storage = _get_storage()
    all_startups = storage.get_all_startups(skip_invalid=True)
    escalations = []
    for s in all_startups:
        if s.partner_info and s.partner_info.human_review_required:
            if s.human_resolution is None:
                escalations.append(_backend_to_frontend(s.to_dict()))
    return escalations


@app.post("/api/escalations/{startup_id}/resolve")
def resolve_escalation(startup_id: str, body: dict):
    """Resolve a human review escalation."""
    decision = body.get("decision")
    notes = body.get("notes", "")
    if decision not in ("YES", "NO", "MAYBE"):
        raise HTTPException(status_code=422, detail="decision must be YES, NO, or MAYBE")
    storage = _get_storage()
    startup = storage.get_startup(startup_id)
    if not startup:
        raise HTTPException(status_code=404, detail="Startup not found")
    from datetime import datetime
    resolution = {
        "decision": decision,
        "notes": notes,
        "resolved_at": datetime.now().isoformat(),
    }

    def updater(data):
        for i, item in enumerate(data):
            if item.get("startup_id") == startup_id:
                item["human_resolution"] = resolution
                return data
        return data

    storage._atomic_update(updater)
    return {"status": "ok", "resolution": resolution}


@app.get("/api/settings")
def get_settings():
    """Return current settings (control plane) with budget status and system health."""
    from portfolio.cost_control import CostController
    from portfolio.store import PortfolioStore
    settings = load_settings()
    try:
        cc = CostController()
        settings["budget_status"] = cc.get_all_budget_status()
    except Exception:
        settings["budget_status"] = {}
    
    # Read calibration data from agent_metrics
    try:
        store = PortfolioStore()
        metrics = store._read_file(store.files["agent_metrics"])
        system_health = {}
        for m in metrics:
            if m.get("id") == "verdict_distribution":
                system_health["verdict_distribution"] = m.get("verdict_distribution")
                system_health["calibration_warning"] = m.get("calibration_warning")
                break
        settings["system_health"] = system_health
    except Exception:
        settings["system_health"] = {}
    
    try:
        from settings_loader import get_meta_agent_settings
        settings["meta_agent"] = get_meta_agent_settings()
    except Exception:
        settings["meta_agent"] = {}

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
    return current


@app.get("/api/analytics/watchlist")
def get_watchlist_analytics():
    """Return watchlist age statistics."""
    from portfolio.store import PortfolioStore
    from datetime import datetime
    store = PortfolioStore()
    watchlist = store.get_all_watchlist()
    if not watchlist:
        return {"total": 0, "stale": 0, "avg_days": 0.0}
    now = datetime.now()
    days_list = []
    stale = 0
    for entry in watchlist:
        added = entry.get("added_at")
        if added:
            d = (now - datetime.fromisoformat(added)).days
            days_list.append(d)
            if entry.get("stale_warning"):
                stale += 1
    return {
        "total": len(watchlist),
        "stale": stale,
        "avg_days": sum(days_list) / len(days_list) if days_list else 0.0,
    }


@app.get("/api/signals")
def get_signals():
    """Return recent signals (last 50)."""
    from portfolio.store import PortfolioStore
    store = PortfolioStore()
    signals = store._read_file(store.files["signals"])
    signals.sort(key=lambda s: s.get("detected_at", ""), reverse=True)
    return signals[:50]


@app.get("/api/analytics/rejections")
def get_rejection_analytics():
    """Return rejection pattern analytics."""
    from portfolio.rejection import RejectionAnalyzer
    analyzer = RejectionAnalyzer()
    return analyzer.get_patterns()


@app.get("/api/analytics/concentration")
def get_concentration_analytics():
    """Return sector concentration and theme cluster data."""
    from analytics.clustering import ClusterAnalyzer
    analyzer = ClusterAnalyzer()
    return analyzer._read()


@app.get("/api/meta/reports")
def get_meta_reports():
    """Return last 10 Meta-Agent cycle reports."""
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parent / "data" / "meta" / "meta_reports.json"
    if not path.exists():
        return []
    try:
        with open(path, "r") as f:
            reports = json.load(f)
        if not isinstance(reports, list):
            return []
        return reports[-10:]
    except (json.JSONDecodeError, IOError):
        return []


@app.get("/api/meta/prompt-library")
def get_prompt_library():
    """Return versioned history of all prompt variants."""
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parent / "data" / "meta" / "prompt_library.json"
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


@app.get("/api/meta/weights")
def get_scout_weights():
    """Return current scout type run weights."""
    from meta_agent.reweighter import load_weights
    return load_weights()


@app.get("/api/meta/calibration")
def get_calibration_state():
    """Return current calibration state and active overrides."""
    from meta_agent.calibrator import load_calibration_state
    return load_calibration_state()


@app.post("/api/meta/trigger")
def trigger_meta_cycle():
    """Manually trigger a Meta-Agent cycle (development/oversight use)."""
    import asyncio
    from meta_agent.agent import MetaAgent
    agent = MetaAgent()
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, agent.run_cycle())
                report = future.result(timeout=120)
        else:
            report = asyncio.run(agent.run_cycle())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Meta-Agent cycle failed: {e}")
    return {"status": "triggered", "cycle_number": report.get("cycle_number") if report else 0}


@app.post("/api/waitlist")
def add_to_waitlist(body: dict):
    """Add a new entry to the waitlist."""
    import json
    from pathlib import Path
    from datetime import datetime

    name = body.get("name", "").strip()
    email = body.get("email", "").strip()
    role = body.get("role", "").strip()
    firm = body.get("firm", "").strip()
    linkedin = body.get("linkedin", "").strip()

    if not name or not email:
        raise HTTPException(status_code=422, detail="name and email are required")

    waitlist_path = Path(__file__).resolve().parent / "data" / "waitlist.json"
    waitlist_path.parent.mkdir(parents=True, exist_ok=True)

    entries = []
    if waitlist_path.exists():
        try:
            with open(waitlist_path, "r") as f:
                entries = json.load(f)
        except (json.JSONDecodeError, IOError):
            entries = []

    for e in entries:
        if e.get("email", "").lower() == email.lower():
            position = entries.index(e) + 1
            return {"status": "already_registered", "position": position}

    entry = {
        "name": name,
        "email": email,
        "role": role,
        "firm": firm,
        "linkedin": linkedin,
        "submitted_at": body.get("submitted_at", datetime.now().isoformat()),
    }
    entries.append(entry)

    import os
    temp_path = waitlist_path.with_suffix(".tmp")
    with open(temp_path, "w") as f:
        json.dump(entries, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    temp_path.replace(waitlist_path)

    return {"status": "ok", "position": len(entries)}


@app.get("/api/waitlist")
def get_waitlist():
    """Return full waitlist."""
    import json
    from pathlib import Path
    waitlist_path = Path(__file__).resolve().parent / "data" / "waitlist.json"
    if not waitlist_path.exists():
        return {"count": 0, "entries": []}
    try:
        with open(waitlist_path, "r") as f:
            entries = json.load(f)
        return {"count": len(entries), "entries": entries}
    except (json.JSONDecodeError, IOError):
        return {"count": 0, "entries": []}
