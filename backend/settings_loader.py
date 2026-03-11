"""
Shared settings loader for API and agent engines.
Reads from the same settings file (data/settings.json) so UI toggles
(scouts_enabled, reviewers_enabled, partners_enabled) control backend agents.
"""
import json
import os
from pathlib import Path

DEFAULT_SETTINGS = {
    "cost_budget": {
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
    },
    "portfolio": {
        "auto_watchlist": True,
        "signal_scan_frequency": "hourly",
        "memo_verbosity": "standard",
    },
}


def get_settings_path() -> Path:
    settings_path = os.getenv("SETTINGS_PATH", "data/settings.json")
    root = Path(__file__).resolve().parent
    return root / settings_path if not Path(settings_path).is_absolute() else Path(settings_path)


def load_settings() -> dict:
    path = get_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return json.loads(json.dumps(DEFAULT_SETTINGS))
    try:
        with open(path, "r") as f:
            data = json.load(f)
        out = json.loads(json.dumps(DEFAULT_SETTINGS))
        for section in ("cost_budget", "agent_config", "portfolio"):
            if section in data and isinstance(data[section], dict):
                for k, v in data[section].items():
                    if k in out.get(section, {}):
                        out[section][k] = v
        return out
    except (json.JSONDecodeError, IOError):
        return json.loads(json.dumps(DEFAULT_SETTINGS))


def is_scouts_enabled() -> bool:
    return load_settings().get("agent_config", {}).get("scouts_enabled", True)


def is_reviewers_enabled() -> bool:
    return load_settings().get("agent_config", {}).get("reviewers_enabled", True)


def is_partners_enabled() -> bool:
    return load_settings().get("agent_config", {}).get("partners_enabled", True)


def get_meta_agent_settings() -> dict:
    """Return Meta-Agent configuration from environment."""
    return {
        "interval_seconds": int(os.getenv("META_AGENT_INTERVAL_SECONDS", "86400")),
        "model": os.getenv("META_AGENT_MODEL", "gpt-5-nano"),
        "enabled": os.getenv("META_AGENT_ENABLED", "true").lower() == "true",
        "min_reviews": int(os.getenv("META_AGENT_MIN_REVIEWS", "20")),
        "min_decisions": int(os.getenv("META_AGENT_MIN_DECISIONS", "10")),
        "mutation_cooldown_cycles": int(os.getenv("META_AGENT_MUTATION_COOLDOWN_CYCLES", "3")),
    }
