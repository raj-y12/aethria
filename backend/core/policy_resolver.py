"""
Versioned policy resolution: resources/config/active.json + per-policy version files.

No business logic — only active.json + JSON load + in-process cache + reload().
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TRACE_ENV = "AETHRIA_RESOURCE_TRACE"
_traced_ids: set[str] = set()

_REPO_CONFIG = Path("resources") / "config"
_ACTIVE_REL = _REPO_CONFIG / "active.json"

_POLICY_KEYS = ("partner_rules", "reviewer_rules", "evaluation_rubric")
_POLICY_DIRS = {
    "partner_rules": "partner_rules",
    "reviewer_rules": "reviewer_rules",
    "evaluation_rubric": "evaluation_rubric",
}

_lock = threading.RLock()
_loaded: bool = False
_active_meta: dict[str, Any] = {}
_policy_documents: dict[str, Any] = {}
_policy_paths: dict[str, Path] = {}


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _trace(resource_id: str, resolved: Path) -> None:
    raw = os.environ.get(_TRACE_ENV, "").strip().lower()
    if raw not in ("1", "true", "yes", "on"):
        return
    if resource_id in _traced_ids:
        return
    _traced_ids.add(resource_id)
    try:
        display = str(resolved.resolve())
    except OSError:
        display = str(resolved)
    logger.info(
        "aethria_resource_trace resource_id=%s resolved_path=%s",
        resource_id,
        display,
    )


def read_active_json_from_disk() -> dict[str, Any]:
    """Return active.json as parsed dict (reads from disk; not the policy cache)."""
    path = _repo_root() / _ACTIVE_REL
    if not path.is_file():
        raise FileNotFoundError(f"Missing required resource file: {path.resolve()}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in required resource file: {path.resolve()}") from e
    if not isinstance(data, dict):
        raise ValueError(f"active.json must be a JSON object: {path.resolve()}")
    return data


def _load_locked() -> None:
    global _loaded, _active_meta, _policy_documents, _policy_paths
    if _loaded:
        return
    active = read_active_json_from_disk()
    _active_meta = dict(active)
    docs: dict[str, Any] = {}
    paths: dict[str, Path] = {}
    root = _repo_root()
    for key in _POLICY_KEYS:
        ver = active.get(key)
        if not ver or not isinstance(ver, str) or not ver.strip():
            raise ValueError(
                f"active.json must set a non-empty string version for {key!r}"
            )
        ver = ver.strip()
        subdir = _POLICY_DIRS[key]
        path = root / _REPO_CONFIG / subdir / f"{ver}.json"
        if not path.is_file():
            raise FileNotFoundError(f"Missing required resource file: {path.resolve()}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON in required resource file: {path.resolve()}"
            ) from e
        docs[key] = data
        paths[key] = path
        _trace(key, path)
    _policy_documents = docs
    _policy_paths = paths
    _loaded = True


def _ensure_loaded() -> None:
    with _lock:
        _load_locked()


def reload() -> None:
    """Clear cache and reload active.json + all versioned policy files from disk."""
    global _loaded, _active_meta, _policy_documents, _policy_paths, _traced_ids
    with _lock:
        _loaded = False
        _active_meta = {}
        _policy_documents = {}
        _policy_paths = {}
        _traced_ids.clear()
        _load_locked()
    logger.info(
        "policy_resolver reloaded versions partner_rules=%s reviewer_rules=%s evaluation_rubric=%s fund_thesis=%s",
        _active_meta.get("partner_rules"),
        _active_meta.get("reviewer_rules"),
        _active_meta.get("evaluation_rubric"),
        _active_meta.get("fund_thesis"),
    )
    try:
        from core.fund_thesis_resolver import reload as _reload_fund_thesis

        _reload_fund_thesis()
    except Exception as e:
        logger.warning("fund_thesis_resolver reload: %s", e)


def get_partner_rules() -> Any:
    _ensure_loaded()
    with _lock:
        return _policy_documents["partner_rules"]


def get_reviewer_rules() -> Any:
    _ensure_loaded()
    with _lock:
        return _policy_documents["reviewer_rules"]


def get_evaluation_rubric() -> Any:
    _ensure_loaded()
    with _lock:
        return _policy_documents["evaluation_rubric"]


def get_fund_thesis_version() -> str | None:
    """Resolved resource thesis version label (e.g. v1), from active.json + fund_thesis_resolver."""
    try:
        from core.fund_thesis_resolver import get_resolved_version_label

        return get_resolved_version_label()
    except Exception:
        _ensure_loaded()
        with _lock:
            v = _active_meta.get("fund_thesis")
        if v is None:
            return None
        s = str(v).strip()
        return s or None


def get_active_meta_snapshot() -> dict[str, Any]:
    """Shallow copy of active.json fields last used to build the policy cache."""
    _ensure_loaded()
    with _lock:
        return dict(_active_meta)


def get_policy_file_path(policy_key: str) -> Path:
    """Resolved path to the JSON file for a policy key (after cache load)."""
    if policy_key not in _POLICY_DIRS:
        raise KeyError(f"unknown policy key: {policy_key!r}")
    _ensure_loaded()
    with _lock:
        return _policy_paths[policy_key]
