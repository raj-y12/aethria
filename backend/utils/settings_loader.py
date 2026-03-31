"""
Shared settings loader for API and agent engines.
Backed by Supabase settings table so UI toggles control backend agents.
Settings are keyed by user_id so each user has their own settings.
User ID is always dynamic: from request in API, or from run context in agents (set_run_user_id).
No .env default — agents must be started with an explicit user_id (e.g. CLI --user-id or API trigger).
"""
import json
import os
from pathlib import Path
from typing import Optional

from run_context import get_run_user_id, set_run_user_id
from supabase_doc_store import doc_get, doc_set

_SETTINGS_TABLE = "settings"


def _settings_key(user_id: Optional[str] = None, *, for_save: bool = False) -> Optional[str]:
    """Resolve the doc store key. Uses explicit user_id, else run context. Returns None if neither set."""
    if user_id and user_id.strip():
        return user_id.strip()
    ctx = get_run_user_id()
    if ctx and ctx.strip():
        return ctx.strip()
    if for_save:
        return None  # caller will raise
    return None

DEFAULT_SETTINGS = {
    "fund_identity": {
        "fund_name": "",
        "stage_focus": "",
        "geographic_focus": "",
        # Official site for your fund/product (e.g. https://aethria.co). Used to drop
        # wrong-TLD / parallel-domain links from Scout references when no per-deal website.
        "canonical_website": "",
    },
    "cost_budget": {
        "enabled": False,  # Set True to enforce token/call limits and cooldowns; False = bypass for now
        "max_tokens_per_run": 50000,
        "daily_cost_ceiling": 10.0,
        "weekly_cost_ceiling": 50.0,
        "cooldown_seconds": 60,
    },
    "agent_config": {
        "scouts_enabled": True,
        "reviewers_enabled": True,
        "partners_enabled": True,
        "max_agents_per_run": 10,
        "confidence_threshold": 0.5,
        # Scout-specific config
        # Region focus for discovery. "europe" by default; UI can switch later.
        "scout_region": "europe",  # options: "europe", "global"
        # Optional SERP usage for discovery; conservative defaults to protect quota.
        "scout_serp_enabled": False,
        "scout_serp_daily_budget": 5,
    },
    "portfolio": {
        "auto_watchlist": True,
        "signal_scan_frequency": "hourly",
        "memo_verbosity": "standard",
    },
}


def get_settings_path() -> Path:
    settings_path = os.getenv("SETTINGS_PATH", "data/settings.json")
    root = Path(__file__).resolve().parent.parent  # backend
    return root / settings_path if not Path(settings_path).is_absolute() else Path(settings_path)


def load_settings(user_id: Optional[str] = None) -> dict:
    """Load settings for a user. In API pass request.state.user_id; in agents omit to use run context."""
    key = _settings_key(user_id, for_save=False)
    if not key:
        return json.loads(json.dumps(DEFAULT_SETTINGS))
    # key is the user_id for settings table; pass so doc_get uses (user_id, key) correctly
    data = doc_get(_SETTINGS_TABLE, key, user_id=key)
    if not data or not isinstance(data, dict):
        return json.loads(json.dumps(DEFAULT_SETTINGS))
    out = json.loads(json.dumps(DEFAULT_SETTINGS))
    for section in ("fund_identity", "cost_budget", "agent_config", "portfolio"):
        if section in data and isinstance(data[section], dict):
            for k, v in data[section].items():
                if k in out.get(section, {}):
                    out[section][k] = v
    return out


def save_settings(settings: dict, user_id: Optional[str] = None) -> None:
    """Persist settings to Supabase for a user. user_id required (from request or run context)."""
    key = _settings_key(user_id, for_save=True)
    if not key:
        raise ValueError("user_id required to save settings (pass explicitly or set run context with set_run_user_id)")
    doc_set(_SETTINGS_TABLE, settings, key, user_id=key)


def is_scouts_enabled(user_id: Optional[str] = None) -> bool:
    return load_settings(user_id).get("agent_config", {}).get("scouts_enabled", True)


def is_reviewers_enabled(user_id: Optional[str] = None) -> bool:
    return load_settings(user_id).get("agent_config", {}).get("reviewers_enabled", True)


def is_partners_enabled(user_id: Optional[str] = None) -> bool:
    return load_settings(user_id).get("agent_config", {}).get("partners_enabled", True)


def is_cost_budget_enabled(user_id: Optional[str] = None) -> bool:
    """Whether to enforce cost/token budgets and cooldowns. False = bypass (no limits)."""
    return bool(load_settings(user_id).get("cost_budget", {}).get("enabled", False))


def get_scout_region(user_id: Optional[str] = None) -> str:
    """
    Return the current scout region focus.
    Values: "europe" (default) or "global".
    """
    region = load_settings(user_id).get("agent_config", {}).get("scout_region", "europe")
    if region not in ("europe", "global"):
        return "europe"
    return region


def is_scout_serp_enabled(user_id: Optional[str] = None) -> bool:
    """Whether Scouts are allowed to use SERP (guarded + rate-limited)."""
    return bool(load_settings(user_id).get("agent_config", {}).get("scout_serp_enabled", False))


def get_canonical_website_hostname(user_id: Optional[str] = None) -> Optional[str]:
    """
    Hostname from fund_identity.canonical_website (URL or bare domain), if set.
    Used as reference anchor for Scout citation filtering.
    """
    try:
        from utils.reference_verify import hostname_from_user_hint
    except ImportError:
        return None
    raw = (load_settings(user_id).get("fund_identity") or {}).get("canonical_website")
    return hostname_from_user_hint(raw) if raw else None


def get_scout_serp_daily_budget(user_id: Optional[str] = None) -> int:
    """
    Max SERP queries per day across all Scouts.
    Conservative default (5/day) to keep well under 250/month.
    """
    raw = load_settings(user_id).get("agent_config", {}).get("scout_serp_daily_budget", 5)
    try:
        n = int(raw)
    except Exception:
        return 5
    return max(0, n)


def get_meta_agent_settings() -> dict:
    """
    Return Meta-Agent configuration derived from environment variables.

    This surfaces the same knobs used by the Meta-Agent backend so the
    front-end control plane can display them:
    - META_AGENT_ENABLED
    - META_AGENT_INTERVAL_SECONDS
    - META_AGENT_MIN_REVIEWS
    - META_AGENT_MIN_DECISIONS
    - META_AGENT_MUTATION_COOLDOWN_CYCLES
    """
    def _as_int(env_var: str, default: str) -> int:
        raw = os.getenv(env_var, default)
        try:
            return int(str(raw))
        except Exception:
            return int(default)

    enabled = os.getenv("META_AGENT_ENABLED", "true").lower() == "true"

    return {
        "enabled": enabled,
        "interval_seconds": _as_int("META_AGENT_INTERVAL_SECONDS", "86400"),
        "min_reviews": _as_int("META_AGENT_MIN_REVIEWS", "20"),
        "min_decisions": _as_int("META_AGENT_MIN_DECISIONS", "10"),
        "mutation_cooldown_cycles": _as_int("META_AGENT_MUTATION_COOLDOWN_CYCLES", "3"),
    }
