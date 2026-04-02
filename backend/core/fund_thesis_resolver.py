"""
Resource-backed fund thesis lens (resources/config/fund_thesis/<version>.json).

Separate from Supabase ActiveThesis — this is the versioned policy "intelligence layer"
for prompts and non-blocking alignment scoring. No pipeline blocking on load failures.
"""
from __future__ import annotations

import json
import logging
import math
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_lock = threading.RLock()
_loaded: bool = False
_cached: Optional["FundThesis"] = None
_cached_version_label: Optional[str] = None
_cached_path: Optional[Path] = None


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _read_active() -> dict[str, Any]:
    from core.policy_resolver import read_active_json_from_disk

    return read_active_json_from_disk()


def resolve_fund_thesis_version(active: Optional[dict[str, Any]] = None) -> Optional[str]:
    """
    Version id for fund_thesis/*.json (e.g. v1).
    Precedence: fund_thesis_versions[fund_thesis_active] if versions map present; else fund_thesis string.
    """
    data = active if active is not None else _read_active()
    versions = data.get("fund_thesis_versions")
    active_key = (data.get("fund_thesis_active") or "default").strip()
    if isinstance(versions, dict) and versions:
        v = versions.get(active_key)
        if v is not None and str(v).strip():
            return str(v).strip()
        v = versions.get("default")
        if v is not None and str(v).strip():
            return str(v).strip()
    ft = data.get("fund_thesis")
    if ft is not None and str(ft).strip():
        return str(ft).strip()
    return None


class FundThesis(BaseModel):
    """Structured investment lens (resource file)."""

    version: str = ""
    name: str = ""
    description: str = ""
    investment_focus: List[str] = Field(default_factory=list)
    exclusion_criteria: List[str] = Field(default_factory=list)
    stage_preference: List[str] = Field(default_factory=list)
    geography: Optional[List[str]] = None
    check_size_range: Optional[str] = None
    risk_tolerance: Optional[str] = None
    sectors_weighting: Optional[Dict[str, float]] = None
    signals_of_interest: Optional[List[str]] = None
    signals_of_avoidance: Optional[List[str]] = None


def _load_file_for_version(version: str) -> Tuple[FundThesis, Path]:
    root = _repo_root()
    path = root / "resources" / "config" / "fund_thesis" / f"{version}.json"
    if not path.is_file():
        raise FileNotFoundError(f"Missing required resource file: {path.resolve()}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Fund thesis JSON must be an object: {path}")
    thesis = FundThesis.model_validate(raw)
    return thesis, path


def _ensure_loaded() -> None:
    global _loaded, _cached, _cached_version_label, _cached_path
    with _lock:
        if _loaded:
            return
        ver = resolve_fund_thesis_version()
        if not ver:
            _cached = None
            _cached_version_label = None
            _cached_path = None
            _loaded = True
            return
        thesis, path = _load_file_for_version(ver)
        _cached = thesis
        _cached_version_label = ver
        _cached_path = path
        _loaded = True


def reload() -> None:
    """Clear cache; next access reloads from active.json + versioned file."""
    global _loaded, _cached, _cached_version_label, _cached_path
    with _lock:
        _loaded = False
        _cached = None
        _cached_version_label = None
        _cached_path = None


def get_fund_thesis() -> Optional[FundThesis]:
    _ensure_loaded()
    with _lock:
        return _cached


def get_resolved_version_label() -> Optional[str]:
    _ensure_loaded()
    with _lock:
        return _cached_version_label


def get_thesis_weight_for_sector(sector: str) -> float:
    t = get_fund_thesis()
    if not t or not t.sectors_weighting:
        return 1.0
    s = (sector or "").strip().lower()
    for k, w in t.sectors_weighting.items():
        if k.strip().lower() == s:
            return float(w)
    for k, w in t.sectors_weighting.items():
        if k.strip().lower() in s or s in k.strip().lower():
            return float(w)
    return 1.0


def _startup_text_blob(startup: Dict[str, Any]) -> str:
    parts = [
        str(startup.get("name") or ""),
        str(startup.get("one_line") or ""),
        str(startup.get("sector") or ""),
        str(startup.get("problem") or ""),
        str(startup.get("solution") or ""),
        str(startup.get("target_users") or ""),
        str(startup.get("why_now") or ""),
        str(startup.get("primary_thesis") or ""),
    ]
    return " ".join(parts).lower()


def matches_exclusion_criteria(startup: Dict[str, Any]) -> bool:
    t = get_fund_thesis()
    if not t or not t.exclusion_criteria:
        return False
    blob = _startup_text_blob(startup)
    for phrase in t.exclusion_criteria:
        p = (phrase or "").strip().lower()
        if len(p) >= 3 and p in blob:
            return True
    return False


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    v = dot / (na * nb)
    return max(0.0, min(1.0, (v + 1.0) / 2.0))


def compute_thesis_alignment_score(
    startup: Dict[str, Any],
    embeddings_optional: Optional[Tuple[Optional[List[float]], Optional[List[float]]]] = None,
) -> float:
    """0–1 composite: rule overlap + optional embedding similarity (never raises)."""
    meta: Dict[str, Any] = {}
    score, _ = _compute_alignment_internal(startup, embeddings_optional, meta)
    return score


def _compute_alignment_internal(
    startup: Dict[str, Any],
    embeddings_optional: Optional[Tuple[Optional[List[float]], Optional[List[float]]]],
    meta: Dict[str, Any],
) -> Tuple[float, Dict[str, Any]]:
    t = get_fund_thesis()
    if not t:
        meta.update({"sector_match": False, "excluded": False, "version": None, "rule_component": None})
        return 0.0, meta

    ver = get_resolved_version_label()
    meta["version"] = ver
    excluded = matches_exclusion_criteria(startup)
    meta["excluded"] = excluded

    blob = _startup_text_blob(startup)
    sector = str(startup.get("sector") or "").strip()
    stage = str(startup.get("funding_stage") or "").strip()

    rule = 0.35
    sector_match = False
    for term in t.investment_focus:
        tok = (term or "").strip().lower()
        if len(tok) >= 2 and tok in blob:
            rule += 0.12
            sector_match = True
    for st in t.stage_preference or []:
        stl = (st or "").strip().lower()
        if stl and stl in stage.lower():
            rule += 0.08
            break
    if t.geography:
        for g in t.geography:
            gl = (g or "").strip().lower()
            if gl and gl in blob:
                rule += 0.05
                break
    if t.signals_of_interest:
        hit = sum(1 for s in t.signals_of_interest if (s or "").strip().lower() in blob)
        rule += min(0.1, 0.02 * hit)
    if t.signals_of_avoidance:
        hit = sum(1 for s in t.signals_of_avoidance if (s or "").strip().lower() in blob)
        rule -= min(0.15, 0.03 * hit)

    if sector and t.sectors_weighting:
        w = get_thesis_weight_for_sector(sector)
        if w > 1.0:
            rule += 0.05 * min(w - 1.0, 0.5)
        elif w < 1.0:
            rule -= 0.03

    if excluded:
        rule = min(rule, 0.25)

    rule = max(0.0, min(1.0, rule))
    meta["sector_match"] = sector_match
    meta["rule_component"] = round(rule, 4)

    emb_score: Optional[float] = None
    if embeddings_optional:
        se, te = embeddings_optional
        if (
            isinstance(se, list)
            and isinstance(te, list)
            and se
            and te
            and len(se) == len(te)
        ):
            emb_score = _cosine_similarity([float(x) for x in se], [float(x) for x in te])
            meta["embedding_component"] = round(emb_score, 4)

    if emb_score is not None:
        final = 0.55 * rule + 0.45 * emb_score
    else:
        final = rule

    final = max(0.0, min(1.0, final))
    meta["alignment_score"] = round(final, 4)
    return final, meta


def log_fund_thesis_event(
    startup_id: str,
    alignment_score: float,
    *,
    sector_match: bool,
    excluded: bool,
    version: Optional[str],
) -> None:
    logger.info(
        "[FundThesis] startup_id=%s alignment_score=%.4f sector_match=%s excluded=%s version=%s",
        startup_id,
        alignment_score,
        sector_match,
        excluded,
        version or "",
    )


def format_fund_thesis_context_for_prompt() -> str:
    """Short block for LLM: lens only; does not override rubric/partner rules."""
    t = get_fund_thesis()
    if not t:
        return ""
    ver = get_resolved_version_label() or ""
    payload = t.model_dump(mode="json", exclude_none=True)
    body = json.dumps(payload, ensure_ascii=False, indent=2)[:6000]
    return (
        "\n\nFUND THESIS CONTEXT (DO NOT OVERRIDE RULES — for interpretation and weighting hints only; "
        "keep all rubric thresholds and required JSON schema unchanged):\n"
        f"resource_thesis_version: {ver}\n"
        f"{body}\n"
    )


def compute_and_log_alignment(
    startup_id: str,
    startup: Dict[str, Any],
    embeddings_optional: Optional[Tuple[Optional[List[float]], Optional[List[float]]]] = None,
) -> float:
    meta: Dict[str, Any] = {}
    score, m = _compute_alignment_internal(startup, embeddings_optional, meta)
    if m.get("version"):
        log_fund_thesis_event(
            startup_id,
            score,
            sector_match=bool(m.get("sector_match")),
            excluded=bool(m.get("excluded")),
            version=m.get("version"),
        )
    return score
