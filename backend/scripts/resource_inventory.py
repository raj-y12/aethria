#!/usr/bin/env python3
"""
Read-only inventory of repo resources/**/*.json vs backend Python references.

Run from repo root:
  python3 backend/scripts/resource_inventory.py
"""
from __future__ import annotations

import sys
from pathlib import Path


def _repo_and_backend() -> tuple[Path, Path]:
    script = Path(__file__).resolve()
    backend = script.parent.parent
    repo = backend.parent
    return repo, backend


def _collect_py_sources(backend: Path) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    for p in sorted(backend.rglob("*.py")):
        if "venv" in p.parts or "__pycache__" in p.parts:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        out.append((p, text))
    return out


def _path_mentions(text: str, rel_posix: str, basename: str) -> bool:
    if rel_posix in text:
        return True
    parts = rel_posix.split("/")
    if len(parts) >= 2 and all(f'"{segment}"' in text for segment in parts[-2:]):
        return True
    return f'"{basename}"' in text and "resources" in text


def _appears_loaded(text: str, rel_posix: str, basename: str) -> bool:
    if "json.load" not in text:
        return False
    return _path_mentions(text, rel_posix, basename)


def _likely_runtime_critical(rel_posix: str) -> bool:
    return (
        rel_posix.endswith("partner_rules.json")
        or rel_posix.endswith("reviewer_rules.json")
        or rel_posix.endswith("evaluation_rubric_v1.json")
    )


def main() -> int:
    repo, backend = _repo_and_backend()
    resources_dir = repo / "resources"
    if not resources_dir.is_dir():
        print(f"resources/ not found at {resources_dir}", file=sys.stderr)
        return 1

    py_sources = _collect_py_sources(backend)

    json_files = sorted(resources_dir.rglob("*.json"))
    rows: list[tuple[str, str, str, str]] = []

    for jf in json_files:
        rel = jf.relative_to(repo).as_posix()
        base = jf.name

        ref_any = False
        load_any = False
        for _, text in py_sources:
            if _path_mentions(text, rel, base):
                ref_any = True
            if _appears_loaded(text, rel, base):
                load_any = True

        crit = "yes" if _likely_runtime_critical(rel) else "no"
        rows.append((rel, "yes" if load_any else "no", "yes" if ref_any else "no", crit))

    sys.path.insert(0, str(backend))
    try:
        from utils.resource_paths import (
            resolve_evaluation_rubric_path,
            resolve_partner_rules_path,
            resolve_reviewer_rules_path,
        )

        canonical = [
            ("partner_rules", resolve_partner_rules_path()),
            ("reviewer_rules", resolve_reviewer_rules_path()),
            ("evaluation_rubric_v1", resolve_evaluation_rubric_path()),
        ]
    except ImportError as e:
        canonical = []
        canon_err = str(e)
    else:
        canon_err = ""

    print("resource_inventory (read-only)")
    print(f"repo_root={repo}")
    print()
    print(f"{'file':<60} {'loaded?':<8} {'ref?':<8} {'critical?':<10}")
    print("-" * 90)
    for rel, load, ref, crit in rows:
        print(f"{rel:<60} {load:<8} {ref:<8} {crit:<10}")

    if canon_err:
        print("\n(canonical config paths unavailable:", canon_err, ")")
    elif canonical:
        print("\ncanonical_runtime_config (resources/config)")
        print(f"{'resource_id':<22} {'path'}")
        print("-" * 90)
        for rid, path in canonical:
            try:
                disp = str(path.resolve())
            except OSError:
                disp = str(path)
            print(f"{rid:<22} {disp}")

    print()
    print("Heuristics: loaded = path/basename appears in a .py that also contains json.load.")
    print("            ref     = path or resources + basename chain appears in a .py file.")
    print("            critical= partner_rules, reviewer_rules, or evaluation_rubric_v1.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
