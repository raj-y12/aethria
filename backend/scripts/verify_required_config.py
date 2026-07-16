#!/usr/bin/env python3
"""
Dev-only: verify resources/config/active.json and default v1 policy files exist and parse.

Exits 0 always; prints errors to stderr for missing/invalid files.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    script = Path(__file__).resolve()
    backend = script.parent.parent
    repo = backend.parent
    sys.path.insert(0, str(backend))
    from utils.resource_paths import REQUIRED_CONFIG_FILES, project_root

    root = project_root()
    print("verify_required_config (dev-only)")
    print(f"repo_root={root}\n")
    ok = True
    for rel in REQUIRED_CONFIG_FILES:
        path = root / rel.replace("\\", "/")
        label = rel
        if not path.is_file():
            print(f"ERROR: missing {label} -> {path.resolve()}", file=sys.stderr)
            ok = False
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"ERROR: invalid JSON {label}: {e}", file=sys.stderr)
            ok = False
            continue
        print(f"OK: {label}")

    # Optional: ensure policy_resolver loads
    try:
        from core.policy_resolver import get_partner_rules, reload as policy_reload

        policy_reload()
        _ = get_partner_rules()
        print("OK: policy_resolver.load (reload + get_partner_rules)")
    except Exception as e:
        print(f"ERROR: policy_resolver: {e}", file=sys.stderr)
        ok = False

    print()
    print("Summary:", "all checks OK" if ok else "one or more issues (see above)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
