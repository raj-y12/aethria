"""
Shared settings loader for API and agent engines.
Settings transport is direct PostgreSQL; normalization remains in this module.
Settings are keyed by user_id so each user has their own settings.
user_id must always be passed explicitly (no run_context).
"""
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

from settings_repository import SettingsRepository

_SETTINGS_TABLE = "settings"
_SETTINGS_CACHE_TTL_SECONDS = 2.0
_SETTINGS_CACHE: dict[str, tuple[float, dict]] = {}
logger = logging.getLogger(__name__)


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
        "activePolicyVersionId": None,
        "draftPolicyHash": None,
        "publishedPolicyHash": None,
        "lastPublishedAt": None,
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
        # Two INDEPENDENT gates (they used to be one flag, which meant citation
        # grounding silently rode on an empty-retrieval setting):
        #   scout_citation_allowlist_enforced — when retrieval returned sources,
        #     the model may only cite those sources. Fail-closed by default: a
        #     payload whose citations all fall outside the retrieved set is rejected.
        #   scout_fail_closed_on_empty_retrieval — when retrieval returns NOTHING,
        #     skip generation instead of letting the model write ungrounded prose.
        "scout_citation_allowlist_enforced": True,
        "scout_fail_closed_on_empty_retrieval": True,
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


async def load_settings(
    user_id: Optional[str] = None,
    *,
    repository: SettingsRepository | None = None,
    use_cache: bool = True,
) -> dict:
    """Load, normalize, and cache settings from the injected PostgreSQL repository."""
    key = _settings_key(user_id, for_save=False)
    if not key:
        return json.loads(json.dumps(DEFAULT_SETTINGS))
    cached = _SETTINGS_CACHE.get(key) if use_cache else None
    now = time.monotonic()
    if cached and (now - cached[0]) <= _SETTINGS_CACHE_TTL_SECONDS:
        return json.loads(json.dumps(cached[1]))
    if repository is None:
        raise RuntimeError("load_settings requires an explicit SettingsRepository")
    data = await repository.get(key, key=key)
    if not data or not isinstance(data, dict):
        out = json.loads(json.dumps(DEFAULT_SETTINGS))
        out = await _reconcile_settings_with_active_thesis(out, key, repository)
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
    # Migration 1: scout_fail_closed_on_empty_retrieval no longer controls citation
    # allowlist enforcement — that is now scout_citation_allowlist_enforced. Any
    # stored value was written under the old, coupled semantics (where it meant
    # "enforce the allowlist"), so it cannot be carried over to the new meaning.
    # Reset it to the default and let the dedicated flag govern citations.
    ac = out.get("agent_config")
    if isinstance(ac, dict):
        stored_ac = data.get("agent_config") if isinstance(data, dict) else None
        if isinstance(stored_ac, dict) and "scout_fail_closed_on_empty_retrieval" in stored_ac:
            if "scout_citation_allowlist_enforced" not in stored_ac:
                ac["scout_fail_closed_on_empty_retrieval"] = DEFAULT_SETTINGS[
                    "agent_config"
                ]["scout_fail_closed_on_empty_retrieval"]
    # Migration 2: confidence_threshold default changed from 0.5 to 0.2 to improve
    # reviewer throughput; only rewrite explicit legacy-default values.
    if isinstance(ac, dict):
        stored_ac = data.get("agent_config") if isinstance(data, dict) else None
        stored_threshold = stored_ac.get("confidence_threshold") if isinstance(stored_ac, dict) else None
        if stored_threshold in (0.5, "0.5"):
            ac["confidence_threshold"] = DEFAULT_SETTINGS["agent_config"]["confidence_threshold"]
    out = await _reconcile_settings_with_active_thesis(out, key, repository)
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


async def _reconcile_settings_with_active_thesis(
    settings: dict,
    user_id: str,
    repository: SettingsRepository,
) -> dict:
    """Make the canonical active thesis authoritative for effective settings.

    Settings still owns operator controls such as agent enablement. The
    structured fund mandate is a projection of the canonical thesis, however,
    so stale settings rows must not make the UI or workers observe an older
    mandate. Repositories without the optional thesis lookup retain the legacy
    unit-test/dev behavior.
    """
    getter = getattr(repository, "get_active_thesis_for_settings", None)
    if getter is None:
        return settings
    try:
        thesis = await getter(user_id)
    except Exception:
        logger.warning("settings_thesis_reconcile_failed user_id=%s", user_id[:24], exc_info=True)
        return settings
    if not isinstance(thesis, dict):
        return settings
    settings["fund_config"] = reconcile_fund_config_with_thesis(
        settings.get("fund_config") if isinstance(settings.get("fund_config"), dict) else {},
        raw_text=str(thesis.get("raw_text") or ""),
        parsed_json=thesis.get("parsed_json"),
        version_number=thesis.get("version_number"),
        version_id=thesis.get("version_id"),
    )
    return settings


def reconcile_fund_config_with_thesis(
    fund_config: dict,
    *,
    raw_text: str,
    parsed_json: Any,
    version_number: Any = None,
    version_id: Any = None,
) -> dict:
    """Overlay canonical thesis content onto a settings fund-config projection."""
    result = _deep_merge_dict(DEFAULT_SETTINGS["fund_config"], fund_config if isinstance(fund_config, dict) else {})
    parsed = parsed_json
    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except json.JSONDecodeError:
            parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    mandate = result.setdefault("mandate", {})

    mappings = {
        "sectors": ("preferredSectors",),
        "stage_focus": ("preferredStages",),
        "geography": ("geographyPreferences",),
        "exclusions": ("excludedSectorList", "excludedSectors"),
        "check_size_min": ("checkSizeMin",),
        "check_size_max": ("checkSizeMax",),
        "ownership_target": ("ownershipTarget",),
    }
    for parsed_key, target_keys in mappings.items():
        if parsed_key not in parsed:
            continue
        value = parsed[parsed_key]
        if parsed_key in {"sectors", "stage_focus", "geography", "exclusions"}:
            value = [str(item).strip() for item in value or [] if str(item).strip()]
        for target_key in target_keys:
            mandate[target_key] = value
    if "risk_profile" in parsed:
        result.setdefault("risk", {})["sensitivity"] = str(parsed["risk_profile"] or "balanced")
    for parsed_key, target_key in (
        ("score_bands", "scoreBands"),
        ("scoring_weights", "scoringWeights"),
        ("rubric", "rubric"),
        ("thresholds", "thresholds"),
    ):
        if parsed_key in parsed and isinstance(parsed[parsed_key], (dict, list)):
            result[target_key] = parsed[parsed_key]
    if isinstance(version_number, int) or (isinstance(version_number, str) and version_number.isdigit()):
        number = int(version_number)
        result["version"] = number
        result["versionLabel"] = f"Fund Thesis v{number}"
    if version_id:
        result["activePolicyVersionId"] = str(version_id)
    # Only use an explicitly supplied thesis-text field. Historical raw_text
    # values often contain the generated structured summary and would duplicate
    # itself if written into the UI's free-text field.
    explicit_text = parsed.get("thesis_text") or parsed.get("thesisText")
    if isinstance(explicit_text, str) and explicit_text.strip():
        mandate["thesisText"] = explicit_text.strip()
    return result


async def save_settings(
    settings: dict,
    user_id: Optional[str] = None,
    *,
    repository: SettingsRepository | None = None,
) -> None:
    """Replace the persisted settings document for a user."""
    key = _settings_key(user_id, for_save=True)
    if not key:
        raise ValueError("user_id required to save settings")
    if repository is None:
        raise RuntimeError("save_settings requires an explicit SettingsRepository")
    await repository.upsert(key, settings, key=key)
    _SETTINGS_CACHE.pop(key, None)
    logger.info("settings_save user_id=%s sections=%s", key[:24], sorted(settings.keys()))


async def get_fund_config(
    user_id: Optional[str] = None,
    *,
    repository: SettingsRepository | None = None,
    use_cache: bool = True,
) -> dict:
    fc = (await load_settings(user_id, repository=repository, use_cache=use_cache)).get("fund_config")
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


_FUND_CONFIG_META_KEYS = frozenset(
    {
        "version",
        "versionLabel",
        "lastSavedAt",
        "activePolicyVersionId",
        "draftPolicyHash",
        "publishedPolicyHash",
        "lastPublishedAt",
    }
)


def _canonical_json_blob(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def fund_config_content_fingerprint(fund_config: dict) -> str:
    """Stable hash of mandate + scoring content (ignores version metadata)."""
    if not isinstance(fund_config, dict):
        return hashlib.sha256(b"{}").hexdigest()
    stripped = {k: v for k, v in fund_config.items() if k not in _FUND_CONFIG_META_KEYS}
    payload = {
        "raw": fund_config_raw_text(stripped).strip(),
        "parsed": fund_config_to_thesis_parsed_json(stripped),
    }
    return hashlib.sha256(_canonical_json_blob(payload).encode("utf-8")).hexdigest()


def fund_config_content_changed(prev: dict, nxt: dict) -> bool:
    if not isinstance(prev, dict) or not prev:
        return bool(nxt)
    if not isinstance(nxt, dict):
        return False
    return fund_config_content_fingerprint(prev) != fund_config_content_fingerprint(nxt)


def normalize_thesis_parsed_json(parsed: Optional[dict]) -> dict:
    """Drop volatile keys before comparing thesis payloads."""
    if not isinstance(parsed, dict):
        return {}
    out = dict(parsed)
    for key in ("settings_version", "source"):
        out.pop(key, None)
    return out


def thesis_payload_fingerprint(*, raw_text: str, parsed_json: Optional[dict]) -> str:
    payload = {
        "raw": (raw_text or "").strip(),
        "parsed": normalize_thesis_parsed_json(parsed_json),
    }
    return hashlib.sha256(_canonical_json_blob(payload).encode("utf-8")).hexdigest()


def fund_config_matches_thesis_payload(*, raw_text: str, parsed_json: Optional[dict], fund_config: dict) -> bool:
    expected = thesis_payload_fingerprint(
        raw_text=fund_config_raw_text(fund_config),
        parsed_json=fund_config_to_thesis_parsed_json(fund_config),
    )
    actual = thesis_payload_fingerprint(raw_text=raw_text, parsed_json=parsed_json)
    return expected == actual


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
                # Advance-intent wins: a label like "Pass to Partner — proceed"
                # carries both substrings but means INVEST, so check invest/proceed
                # BEFORE the "pass" reject match.
                if "invest" in label or "proceed" in label:
                    return "INVEST"
                if "pass" in label:
                    return "PASS"
                return "MONITOR"
    thresholds = fund_config.get("thresholds") if isinstance(fund_config.get("thresholds"), dict) else {}
    invest_bar = float(thresholds.get("escalation") or 80) / 10.0
    pass_bar = float(thresholds.get("partnerReview") or 60) / 10.0
    if score_0_to_10 >= invest_bar:
        return "INVEST"
    if score_0_to_10 >= pass_bar:
        return "MONITOR"
    return "PASS"


async def is_scouts_enabled(user_id: Optional[str] = None, *, repository: SettingsRepository | None = None) -> bool:
    # Always read fresh for stage gate checks to avoid stale toggles.
    return (await load_settings(user_id, repository=repository, use_cache=False)).get("agent_config", {}).get("scouts_enabled", False)


async def is_reviewers_enabled(user_id: Optional[str] = None, *, repository: SettingsRepository | None = None) -> bool:
    # Always read fresh for stage gate checks to avoid stale toggles.
    return (await load_settings(user_id, repository=repository, use_cache=False)).get("agent_config", {}).get("reviewers_enabled", False)


async def is_partners_enabled(user_id: Optional[str] = None, *, repository: SettingsRepository | None = None) -> bool:
    # Always read fresh for stage gate checks to avoid stale toggles.
    return (await load_settings(user_id, repository=repository, use_cache=False)).get("agent_config", {}).get("partners_enabled", False)


async def _agent_config_safe(user_id: Optional[str] = None, *, repository: SettingsRepository | None = None) -> dict:
    """Return agent_config or {} if settings cannot be loaded (callers use .get with defaults)."""
    try:
        ac = (await load_settings(user_id, repository=repository)).get("agent_config")
        return dict(ac) if isinstance(ac, dict) else {}
    except Exception:
        return {}


async def is_thesis_reprocess_agents_enabled(user_id: Optional[str] = None, *, repository: SettingsRepository | None = None) -> bool:
    """Fund-thesis backfill re-runs reviewer + partner only."""
    ac = await _agent_config_safe(user_id, repository=repository)
    return bool(ac.get("reviewers_enabled", False) and ac.get("partners_enabled", False))


async def is_cost_budget_enabled(user_id: Optional[str] = None, *, repository: SettingsRepository | None = None) -> bool:
    return bool((await load_settings(user_id, repository=repository)).get("cost_budget", {}).get("enabled", False))


def _non_negative_number(value, default: float) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, n)


def runtime_limits_from_settings(settings: dict) -> dict:
    """Normalize runtime limits from a loaded settings document."""
    ac = settings.get("agent_config") if isinstance(settings.get("agent_config"), dict) else {}
    cb = settings.get("cost_budget") if isinstance(settings.get("cost_budget"), dict) else {}
    try:
        max_agents = int(ac.get("max_agents_per_run", DEFAULT_SETTINGS["agent_config"]["max_agents_per_run"]))
    except (TypeError, ValueError):
        max_agents = DEFAULT_SETTINGS["agent_config"]["max_agents_per_run"]
    try:
        max_tokens = int(cb.get("max_tokens_per_run", DEFAULT_SETTINGS["cost_budget"]["max_tokens_per_run"]))
    except (TypeError, ValueError):
        max_tokens = DEFAULT_SETTINGS["cost_budget"]["max_tokens_per_run"]
    try:
        cooldown = int(cb.get("cooldown_seconds", DEFAULT_SETTINGS["cost_budget"]["cooldown_seconds"]))
    except (TypeError, ValueError):
        cooldown = DEFAULT_SETTINGS["cost_budget"]["cooldown_seconds"]
    return {
        "max_agents_per_run": max(1, max_agents),
        "max_tokens_per_run": max(0, max_tokens),
        "cooldown_seconds": max(0, cooldown),
        "daily_cost_ceiling": _non_negative_number(
            cb.get("daily_cost_ceiling", DEFAULT_SETTINGS["cost_budget"]["daily_cost_ceiling"]),
            DEFAULT_SETTINGS["cost_budget"]["daily_cost_ceiling"],
        ),
        "weekly_cost_ceiling": _non_negative_number(
            cb.get("weekly_cost_ceiling", DEFAULT_SETTINGS["cost_budget"]["weekly_cost_ceiling"]),
            DEFAULT_SETTINGS["cost_budget"]["weekly_cost_ceiling"],
        ),
    }


async def get_runtime_limits(user_id: Optional[str] = None, *, repository: SettingsRepository | None = None) -> dict:
    """Runtime limits saved from Settings > Operations."""
    return runtime_limits_from_settings(await load_settings(user_id, repository=repository))


async def get_scout_region(user_id: Optional[str] = None, *, repository: SettingsRepository | None = None) -> str:
    region = (await load_settings(user_id, repository=repository)).get("agent_config", {}).get("scout_region", "europe")
    if region not in ("europe", "global"):
        return "europe"
    return region


async def is_scout_grounded_citations_enabled(user_id: Optional[str] = None, *, repository: SettingsRepository | None = None) -> bool:
    return bool(
        (await load_settings(user_id, repository=repository)).get("agent_config", {}).get("scout_grounded_citations_enabled", True)
    )


async def is_scout_fail_closed_on_empty_retrieval(user_id: Optional[str] = None, *, repository: SettingsRepository | None = None) -> bool:
    """Whether generation is skipped when retrieval returns no sources at all.

    Independent of citation allowlist enforcement — see
    `is_scout_citation_allowlist_enforced`.
    """
    return bool(
        (await load_settings(user_id, repository=repository))
        .get("agent_config", {})
        .get("scout_fail_closed_on_empty_retrieval", True)
    )


async def is_scout_citation_allowlist_enforced(user_id: Optional[str] = None, *, repository: SettingsRepository | None = None) -> bool:
    """Whether cited URLs must come from the retrieved source pack.

    Fail-closed by default and independent of whether generation is permitted
    when retrieval is empty: if sources WERE retrieved, the model does not get to
    cite anything else.
    """
    return bool(
        (await load_settings(user_id, repository=repository))
        .get("agent_config", {})
        .get("scout_citation_allowlist_enforced", True)
    )


async def get_canonical_website_hostname(user_id: Optional[str] = None, *, repository: SettingsRepository | None = None) -> Optional[str]:
    try:
        from utils.reference_verify import hostname_from_user_hint
    except ImportError:
        return None
    raw = ((await load_settings(user_id, repository=repository)).get("fund_identity") or {}).get("canonical_website")
    return hostname_from_user_hint(raw) if raw else None


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
