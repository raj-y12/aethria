"""
FastAPI server for Aethria.
Serves app-front-end: GET /api/startups, GET/PATCH /settings.
Serves web-front-end: POST /api/waitlist (early access signup).
Single API for both frontends when running on a domain.
"""
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from storage import Storage
from routers.web import router as web_router
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

app.include_router(web_router)


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
    return {"status": "ok"}


@app.get("/api/settings")
def get_settings():
    """Return current settings (control plane)."""
    return load_settings()


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
