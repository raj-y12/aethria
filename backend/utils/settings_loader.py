"""
Shared settings loader for API and agent engines.
Backed by Supabase settings table so UI toggles control backend agents.
Settings are keyed by user_id so each user has their own settings.
user_id must always be passed explicitly when using Supabase (no run_context).
"""
import json
import os
import time
from pathlib import Path
from typing import Optional

from supabase_doc_store import doc_get, doc_set

_SETTINGS_TABLE = "settings"
_SETTINGS_CACHE_TTL_SECONDS = 2.0
_SETTINGS_CACHE: dict[str, tuple[float, dict]] = {}


def _using_supabase() -> bool:
    return os.getenv("USE_SUPABASE_STORAGE", "").lower() in ("1", "true", "yes")


def _settings_key(user_id: Optional[str], *, for_save: bool = False) -> Optional[str]:
    """Return trimmed user_id for settings doc row, or None if missing."""
    if user_id and user_id.strip():
        return user_id.strip()
    if for_save:
        return None
    return None


DEFAULT_SETTINGS = {
    "fund_identity": {
        "fund_name": "",
        "stage_focus": "",
        "geographic_focus": "",
        "canonical_website": "",
    },
    "cost_budget": {
        "enabled": False,
        "max_tokens_per_run": 50000,
        "daily_cost_ceiling": 10.0,
        "weekly_cost_ceiling": 50.0,
        "cooldown_seconds": 60,
    },
    "agent_config": {
        "scouts_enabled": False,
        "reviewers_enabled": False,
        "partners_enabled": False,
        "max_agents_per_run": 10,
        # Lower default to avoid reviewer starvation on normal-confidence scout rows.
        "confidence_threshold": 0.2,
        "scout_region": "europe",
        "scout_grounded_citations_enabled": True,
        # Default fail-open to preserve pipeline throughput when retrieval providers
        # are flaky; strict mode can be re-enabled per user in settings.
        "scout_fail_closed_on_empty_retrieval": False,
        "scout_retrieval_provider": "tavily",
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
    root = Path(__file__).resolve().parent.parent
    return root / settings_path if not Path(settings_path).is_absolute() else Path(settings_path)


def load_settings(user_id: Optional[str] = None, *, use_cache: bool = True) -> dict:
    """Load settings for a user. Requires explicit user_id when USE_SUPABASE_STORAGE is enabled."""
    key = _settings_key(user_id, for_save=False)
    if _using_supabase() and not key:
        raise RuntimeError(
            "load_settings requires explicit user_id when USE_SUPABASE_STORAGE is enabled"
        )
    if not key:
        return json.loads(json.dumps(DEFAULT_SETTINGS))
    cached = _SETTINGS_CACHE.get(key) if use_cache else None
    now = time.monotonic()
    if cached and (now - cached[0]) <= _SETTINGS_CACHE_TTL_SECONDS:
        return json.loads(json.dumps(cached[1]))
    data = doc_get(_SETTINGS_TABLE, key, user_id=key)
    if not data or not isinstance(data, dict):
        out = json.loads(json.dumps(DEFAULT_SETTINGS))
        _SETTINGS_CACHE[key] = (now, out)
        return json.loads(json.dumps(out))
    out = json.loads(json.dumps(DEFAULT_SETTINGS))
    for section in ("fund_identity", "cost_budget", "agent_config", "portfolio"):
        if section in data and isinstance(data[section], dict):
            for k, v in data[section].items():
                if k in out.get(section, {}):
                    out[section][k] = v
    # Migration 1: scout_fail_closed_on_empty_retrieval default changed from True
    # to False; stored settings auto-saved with the old default must be reset.
    ac = out.get("agent_config")
    if isinstance(ac, dict) and ac.get("scout_fail_closed_on_empty_retrieval") is True:
        stored_ac = data.get("agent_config") if isinstance(data, dict) else None
        if isinstance(stored_ac, dict) and "scout_fail_closed_on_empty_retrieval" in stored_ac:
            ac["scout_fail_closed_on_empty_retrieval"] = DEFAULT_SETTINGS["agent_config"]["scout_fail_closed_on_empty_retrieval"]
    # Migration 2: confidence_threshold default changed from 0.5 to 0.2 to improve
    # reviewer throughput; only rewrite explicit legacy-default values.
    if isinstance(ac, dict):
        stored_ac = data.get("agent_config") if isinstance(data, dict) else None
        stored_threshold = stored_ac.get("confidence_threshold") if isinstance(stored_ac, dict) else None
        if stored_threshold in (0.5, "0.5"):
            ac["confidence_threshold"] = DEFAULT_SETTINGS["agent_config"]["confidence_threshold"]
    _SETTINGS_CACHE[key] = (time.monotonic(), out)
    return json.loads(json.dumps(out))


def save_settings(settings: dict, user_id: Optional[str] = None) -> None:
    """Persist settings to Supabase for a user."""
    key = _settings_key(user_id, for_save=True)
    if not key:
        raise ValueError("user_id required to save settings")
    doc_set(_SETTINGS_TABLE, settings, key, user_id=key)
    _SETTINGS_CACHE.pop(key, None)


def is_scouts_enabled(user_id: Optional[str] = None) -> bool:
    # Always read fresh for stage gate checks to avoid stale toggles.
    return load_settings(user_id, use_cache=False).get("agent_config", {}).get("scouts_enabled", False)


def is_reviewers_enabled(user_id: Optional[str] = None) -> bool:
    # Always read fresh for stage gate checks to avoid stale toggles.
    return load_settings(user_id, use_cache=False).get("agent_config", {}).get("reviewers_enabled", False)


def is_partners_enabled(user_id: Optional[str] = None) -> bool:
    # Always read fresh for stage gate checks to avoid stale toggles.
    return load_settings(user_id, use_cache=False).get("agent_config", {}).get("partners_enabled", False)


def _agent_config_safe(user_id: Optional[str] = None) -> dict:
    """Return agent_config or {} if settings cannot be loaded (callers use .get with defaults)."""
    try:
        ac = load_settings(user_id).get("agent_config")
        return dict(ac) if isinstance(ac, dict) else {}
    except Exception:
        return {}


def is_thesis_reprocess_agents_enabled(user_id: Optional[str] = None) -> bool:
    """Fund-thesis backfill re-runs reviewer + partner only."""
    ac = _agent_config_safe(user_id)
    return bool(ac.get("reviewers_enabled", False) and ac.get("partners_enabled", False))


def is_cost_budget_enabled(user_id: Optional[str] = None) -> bool:
    return bool(load_settings(user_id).get("cost_budget", {}).get("enabled", False))


def get_scout_region(user_id: Optional[str] = None) -> str:
    region = load_settings(user_id).get("agent_config", {}).get("scout_region", "europe")
    if region not in ("europe", "global"):
        return "europe"
    return region


def is_scout_serp_enabled(user_id: Optional[str] = None) -> bool:
    return bool(load_settings(user_id).get("agent_config", {}).get("scout_serp_enabled", False))


def is_scout_grounded_citations_enabled(user_id: Optional[str] = None) -> bool:
    return bool(
        load_settings(user_id).get("agent_config", {}).get("scout_grounded_citations_enabled", True)
    )


def is_scout_fail_closed_on_empty_retrieval(user_id: Optional[str] = None) -> bool:
    return bool(
        load_settings(user_id).get("agent_config", {}).get("scout_fail_closed_on_empty_retrieval", False)
    )


def get_scout_retrieval_provider(user_id: Optional[str] = None) -> str:
    raw = str(load_settings(user_id).get("agent_config", {}).get("scout_retrieval_provider", "tavily"))
    lowered = raw.strip().lower()
    return lowered if lowered in ("tavily", "serpapi") else "tavily"


def get_canonical_website_hostname(user_id: Optional[str] = None) -> Optional[str]:
    try:
        from utils.reference_verify import hostname_from_user_hint
    except ImportError:
        return None
    raw = (load_settings(user_id).get("fund_identity") or {}).get("canonical_website")
    return hostname_from_user_hint(raw) if raw else None


def get_scout_serp_daily_budget(user_id: Optional[str] = None) -> int:
    raw = load_settings(user_id).get("agent_config", {}).get("scout_serp_daily_budget", 5)
    try:
        n = int(raw)
    except Exception:
        return 5
    return max(0, n)


def get_meta_agent_settings() -> dict:
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
