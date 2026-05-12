"""
Shared settings loader for API and agent engines.
Backed by Supabase settings table so UI toggles control backend agents.
Settings are keyed by user_id so each user has their own settings.
user_id must always be passed explicitly when using Supabase (no run_context).
"""
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

from supabase_doc_store import doc_get, doc_set

_SETTINGS_TABLE = "settings"
_SETTINGS_CACHE_TTL_SECONDS = 2.0
_SETTINGS_CACHE: dict[str, tuple[float, dict]] = {}
logger = logging.getLogger(__name__)


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
    # Future org/fund ownership connects here. Today this document is keyed by
    # Clerk user_id, so the current user owns the single fund configuration.
    "fund_config": {
        "versionLabel": "Fund Thesis v1",
        "version": 1,
        "lastSavedAt": None,
        "mandate": {
            "fundName": "",
            "mandateName": "Core mandate",
            "preferredSectors": [],
            "excludedSectors": [],
            "preferredStages": ["Pre-seed", "Seed"],
            "geographyPreferences": ["US", "Europe"],
            "thesisText": "",
            "businessModels": "",
            "checkSizeMin": 250000,
            "checkSizeMax": 1500000,
            "ownershipTarget": 8,
            "minimumTraction": "",
        },
        "scoringWeights": [],
        "scoreBands": [],
        "thresholds": {
            "autoPass": 39,
            "monitor": 59,
            "escalation": 75,
            "partnerReview": 60,
            "staleAfterHours": 48,
            "confidenceFloor": 0.55,
            "missingDataThreshold": 35,
        },
        "risk": {
            "sensitivity": "balanced",
            "requireAcknowledgement": True,
            "onlyGateHighSeverity": True,
            "missingFounderPenalty": 8,
            "missingTractionPenalty": 7,
            "contradictionPenalty": 12,
            "weakSourcePenalty": 5,
        },
        "memo": {
            "style": "standard",
            "deepDiveCollapsed": True,
            "includeEvidenceExcerpts": True,
            "includeMissingData": True,
            "includeScoreReasoning": True,
            "includeSourceConfidence": True,
            "tone": "partner",
        },
        "rubric": [],
    },
    "user_preferences": {
        "layoutPreferences": {},
        "savedFilters": [],
        "displayPreferences": {},
        "personalOverrides": {},
    },
    "fund_memory": {
        "historical_decisions": [],
        "recurring_risk_patterns": [],
        "calibration_observations": [],
        "precedent_references": [],
        "mandate_drift_notes": [],
    },
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
        logger.info("settings_load user_id=%s source=defaults", key[:24])
        return json.loads(json.dumps(out))
    out = json.loads(json.dumps(DEFAULT_SETTINGS))
    for section in (
        "fund_config",
        "user_preferences",
        "fund_memory",
        "fund_identity",
        "cost_budget",
        "agent_config",
        "portfolio",
    ):
        if section in data and isinstance(data[section], dict):
            if section in ("fund_config", "user_preferences", "fund_memory"):
                out[section] = _deep_merge_dict(out.get(section, {}), data[section])
            else:
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
    logger.info(
        "settings_load user_id=%s source=database fund_config=%s rubric=%d score_bands=%d",
        key[:24],
        bool(data.get("fund_config")),
        len(((out.get("fund_config") or {}).get("rubric") or [])),
        len(((out.get("fund_config") or {}).get("scoreBands") or [])),
    )
    return json.loads(json.dumps(out))


def _deep_merge_dict(base: dict, saved: dict) -> dict:
    out = json.loads(json.dumps(base))
    for key, value in saved.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge_dict(out[key], value)
        else:
            out[key] = value
    return out


def save_settings(settings: dict, user_id: Optional[str] = None) -> None:
    """Persist settings to Supabase for a user."""
    key = _settings_key(user_id, for_save=True)
    if not key:
        raise ValueError("user_id required to save settings")
    doc_set(_SETTINGS_TABLE, settings, key, user_id=key)
    _SETTINGS_CACHE.pop(key, None)
    logger.info("settings_save user_id=%s sections=%s", key[:24], sorted(settings.keys()))


def get_fund_config(user_id: Optional[str] = None, *, use_cache: bool = True) -> dict:
    fc = load_settings(user_id, use_cache=use_cache).get("fund_config")
    return dict(fc) if isinstance(fc, dict) else {}


def fund_config_to_thesis_parsed_json(fund_config: dict) -> dict:
    """Convert saved UI fund configuration into the backend active-thesis shape."""
    mandate = fund_config.get("mandate") if isinstance(fund_config.get("mandate"), dict) else {}
    sectors = mandate.get("preferredSectors") or mandate.get("sectors") or []
    geos = mandate.get("geographyPreferences") or mandate.get("geographies") or []
    exclusions = mandate.get("excludedSectorList") or mandate.get("excludedSectors") or []
    if isinstance(exclusions, str):
        exclusions = [x.strip() for x in exclusions.split(",") if x.strip()]
    prefs = []
    for key in ("businessModels", "minimumTraction", "thesisText"):
        val = mandate.get(key)
        if isinstance(val, str) and val.strip():
            prefs.append(val.strip())
    return {
        "sectors": [str(x).strip() for x in sectors if str(x).strip()],
        "stage_focus": [str(x).strip() for x in (mandate.get("preferredStages") or []) if str(x).strip()],
        "geography": [str(x).strip() for x in geos if str(x).strip()],
        "preferences": prefs,
        "exclusions": [str(x).strip() for x in exclusions if str(x).strip()],
        "risk_profile": str((fund_config.get("risk") or {}).get("sensitivity") or "balanced"),
        "check_size_min": mandate.get("checkSizeMin"),
        "check_size_max": mandate.get("checkSizeMax"),
        "ownership_target": mandate.get("ownershipTarget"),
        "score_bands": fund_config.get("scoreBands") or [],
        "scoring_weights": fund_config.get("scoringWeights") or [],
        "rubric": fund_config.get("rubric") or [],
        "thresholds": fund_config.get("thresholds") or {},
        "source": "settings.fund_config",
    }


def fund_config_raw_text(fund_config: dict) -> str:
    mandate = fund_config.get("mandate") if isinstance(fund_config.get("mandate"), dict) else {}
    lines = [
        str(mandate.get("thesisText") or "").strip(),
        f"Preferred sectors: {', '.join(mandate.get('preferredSectors') or mandate.get('sectors') or [])}",
        f"Excluded sectors: {', '.join(mandate.get('excludedSectorList') or [])}",
        f"Preferred stages: {', '.join(mandate.get('preferredStages') or [])}",
        f"Geography: {', '.join(mandate.get('geographyPreferences') or mandate.get('geographies') or [])}",
        f"Business models: {mandate.get('businessModels') or ''}",
        f"Minimum traction: {mandate.get('minimumTraction') or ''}",
    ]
    return "\n".join(line for line in lines if line and not line.endswith(": "))


def dimension_weights_from_fund_config(fund_config: dict) -> dict[str, float]:
    weights: dict[str, float] = {}
    aliases = {"fundFit": "defensibility"}
    for row in fund_config.get("scoringWeights") or []:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or "").strip()
        if not key:
            continue
        dim = aliases.get(key, key)
        if dim not in ("market", "product", "technical", "execution", "defensibility"):
            continue
        try:
            weights[dim] = weights.get(dim, 0.0) + float(row.get("weight") or 0.0)
        except (TypeError, ValueError):
            continue
    return {k: v for k, v in weights.items() if v > 0}


def recommendation_for_score_from_fund_config(score_0_to_10: float, fund_config: dict) -> str:
    score_100 = max(0.0, min(100.0, float(score_0_to_10) * 10.0))
    bands = fund_config.get("scoreBands") if isinstance(fund_config, dict) else None
    if isinstance(bands, list):
        for band in bands:
            if not isinstance(band, dict):
                continue
            try:
                lo = float(band.get("min"))
                hi = float(band.get("max"))
            except (TypeError, ValueError):
                continue
            if lo <= score_100 <= hi:
                label = str(band.get("label") or "").lower()
                if "pass" in label:
                    return "PASS"
                if "proceed" in label or "invest" in label:
                    return "INVEST"
                return "MONITOR"
    thresholds = fund_config.get("thresholds") if isinstance(fund_config.get("thresholds"), dict) else {}
    invest_bar = float(thresholds.get("escalation") or 80) / 10.0
    pass_bar = float(thresholds.get("partnerReview") or 60) / 10.0
    if score_0_to_10 >= invest_bar:
        return "INVEST"
    if score_0_to_10 >= pass_bar:
        return "MONITOR"
    return "PASS"


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
