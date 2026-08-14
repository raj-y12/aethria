"""Shared keys and helpers for the provider-neutral prompt library."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, FrozenSet, List, Optional

from batch1.store import doc_get, doc_set

from meta.analyser import REVIEWER_AGENT_NAMES, SCOUT_AGENT_NAMES

_PROMPT_LIBRARY_TABLE = "meta_prompt_library"

# Full library blob: AgentName:hash -> entry
PROMPT_LIBRARY_DATA_KEY = "default"
# Per-tenant map: agent_target -> library_key (e.g. MarketDrivenScout -> MarketDrivenScout:abc)
PROMPT_ACTIVE_KEY = "prompt_active"
# Fixed startup ids for Phase 2 prompt evaluation replay
EVAL_STARTUP_IDS_KEY = "eval_startup_ids"
# Last evaluation result per library_key (for optional promote gate)
LAST_EVAL_BY_LIBRARY_KEY = "last_prompt_eval_by_key"


def load_prompt_library(user_id: str) -> Dict[str, Any]:
    data = doc_get(_PROMPT_LIBRARY_TABLE, PROMPT_LIBRARY_DATA_KEY, user_id=user_id)
    return data if isinstance(data, dict) else {}


def save_prompt_library(user_id: str, library: Dict[str, Any]) -> None:
    doc_set(_PROMPT_LIBRARY_TABLE, library, PROMPT_LIBRARY_DATA_KEY, user_id=user_id)


def load_prompt_active(user_id: str) -> Dict[str, str]:
    data = doc_get(_PROMPT_LIBRARY_TABLE, PROMPT_ACTIVE_KEY, user_id=user_id)
    if not isinstance(data, dict):
        return {}
    out: Dict[str, str] = {}
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, str) and v.strip():
            out[k] = v.strip()
    return out


def save_prompt_active(user_id: str, active: Dict[str, str]) -> None:
    doc_set(_PROMPT_LIBRARY_TABLE, active, PROMPT_ACTIVE_KEY, user_id=user_id)


VALID_PROMOTE_AGENT_TARGETS: FrozenSet[str] = frozenset(SCOUT_AGENT_NAMES.keys()) | frozenset(
    REVIEWER_AGENT_NAMES
)

REVIEWER_EVAL_AGENT_TARGETS: FrozenSet[str] = frozenset(REVIEWER_AGENT_NAMES)


def load_eval_startup_ids(user_id: str) -> List[str]:
    data = doc_get(_PROMPT_LIBRARY_TABLE, EVAL_STARTUP_IDS_KEY, user_id=user_id)
    if not isinstance(data, dict):
        return []
    raw = data.get("startup_ids")
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for x in raw:
        s = str(x).strip()
        if s and s not in out:
            out.append(s)
    return out


def save_eval_startup_ids(user_id: str, startup_ids: List[str], *, max_n: int = 50) -> Dict[str, Any]:
    trimmed = [str(x).strip() for x in startup_ids if str(x).strip()][:max_n]
    payload = {
        "startup_ids": trimmed,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    doc_set(_PROMPT_LIBRARY_TABLE, payload, EVAL_STARTUP_IDS_KEY, user_id=user_id)
    return payload


def load_last_eval_map(user_id: str) -> Dict[str, Any]:
    data = doc_get(_PROMPT_LIBRARY_TABLE, LAST_EVAL_BY_LIBRARY_KEY, user_id=user_id)
    return data if isinstance(data, dict) else {}


def save_last_eval_for_library_key(
    user_id: str,
    library_key: str,
    *,
    passed: bool,
    regression_count: int,
    agreement_count: int,
    n: int,
    mean_abs_delta: float,
) -> None:
    cur = load_last_eval_map(user_id)
    cur = dict(cur)
    cur[library_key] = {
        "passed": passed,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "regression_count": regression_count,
        "agreement_count": agreement_count,
        "n": n,
        "mean_abs_delta": mean_abs_delta,
    }
    doc_set(_PROMPT_LIBRARY_TABLE, cur, LAST_EVAL_BY_LIBRARY_KEY, user_id=user_id)


def get_last_eval_record(user_id: str, library_key: str) -> Optional[Dict[str, Any]]:
    m = load_last_eval_map(user_id)
    ent = m.get(library_key)
    return ent if isinstance(ent, dict) else None


def eval_record_fresh(record: Dict[str, Any], ttl_hours: int) -> bool:
    raw = record.get("evaluated_at")
    if not raw or not isinstance(raw, str):
        return False
    try:
        s = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return datetime.now(timezone.utc) - dt < timedelta(hours=ttl_hours)
