"""Drift guards for the env-var registry (backend/env_config.py).

These tests fail if someone adds an ``os.getenv("NEW_VAR")`` without registering
it, or edits the registry without regenerating ``.env.example``. That keeps
``env_config.REGISTRY`` the genuine single source of truth instead of decaying.
"""
import json
import os
import pathlib
import re

import pytest

import env_config

BACKEND_ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
ENV_EXAMPLE = REPO_ROOT / ".env.example"
CONFIG_ROOT = REPO_ROOT / "resources" / "config"

_GETENV_RE = re.compile(r"""os\.(?:getenv|environ\.get)\(\s*["']([A-Z_0-9]+)["']""")


def _referenced_env_vars() -> set[str]:
    names: set[str] = set()
    for path in BACKEND_ROOT.rglob("*.py"):
        rel = str(path.relative_to(BACKEND_ROOT))
        if rel.startswith("tests/") or path.name == "env_config.py":
            continue
        for m in _GETENV_RE.finditer(path.read_text()):
            names.add(m.group(1))
    return names


def test_every_referenced_env_var_is_registered():
    referenced = _referenced_env_vars()
    registered = {v.name for v in env_config.REGISTRY}
    missing = referenced - registered
    assert not missing, (
        f"These env vars are read in code but missing from env_config.REGISTRY: "
        f"{sorted(missing)}. Register them so they appear in .env.example."
    )


def test_no_duplicate_registry_entries():
    names = [v.name for v in env_config.REGISTRY]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"Duplicate registry entries: {sorted(dupes)}"


def test_env_example_is_in_sync_with_registry():
    assert ENV_EXAMPLE.exists(), ".env.example is missing — regenerate from env_config.render_env_example()"
    on_disk = ENV_EXAMPLE.read_text()
    expected = env_config.render_env_example()
    assert on_disk == expected, (
        ".env.example is out of sync with env_config.REGISTRY. Regenerate with:\n"
        '  cd backend && python -c "import env_config; print(env_config.render_env_example())" > ../.env.example'
    )


def test_accessors_use_registry_defaults(monkeypatch):
    # Unset -> registry default applies.
    monkeypatch.delenv("REVIEWER_BATCH_SIZE", raising=False)
    assert env_config.get_int("REVIEWER_BATCH_SIZE") == 3
    monkeypatch.delenv("PARTNER_USE_LLM", raising=False)
    assert env_config.get_bool("PARTNER_USE_LLM") is True
    monkeypatch.delenv("SCOUT_ENRICH_MIN_CONFIDENCE", raising=False)
    assert env_config.get_float("SCOUT_ENRICH_MIN_CONFIDENCE") == pytest.approx(0.4)


def test_bool_parsing_matches_legacy_convention(monkeypatch):
    for truthy in ("1", "true", "TRUE", "Yes"):
        monkeypatch.setenv("USE_SUPABASE_STORAGE", truthy)
        assert env_config.use_supabase_storage() is True
    for falsy in ("0", "false", "no", "", "off"):
        monkeypatch.setenv("USE_SUPABASE_STORAGE", falsy)
        assert env_config.use_supabase_storage() is False


def test_int_accessor_tolerates_garbage(monkeypatch):
    monkeypatch.setenv("REVIEWER_BATCH_SIZE", "not-a-number")
    assert env_config.get_int("REVIEWER_BATCH_SIZE") == 3  # falls back to registry default


def test_active_partner_rules_select_versioned_decision_safety_policy():
    active = json.loads((CONFIG_ROOT / "active.json").read_text())
    v2_rules = CONFIG_ROOT / "partner_rules" / "v2.json"
    v3_rules = CONFIG_ROOT / "partner_rules" / "v3.json"

    assert active["partner_rules"] == "v3"
    assert v2_rules.exists()
    assert json.loads(v2_rules.read_text())["version"] == "2.0"
    assert v3_rules.exists()
    assert json.loads(v3_rules.read_text())["version"] == "3.0"
