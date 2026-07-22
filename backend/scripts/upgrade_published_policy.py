#!/usr/bin/env python3
"""Explicit dry-run/apply CLI for tenant published-policy upgrades."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.scoring.policy_upgrade import (  # noqa: E402
    upgrade_published_policy,
)


def _selected_fund_config(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("selected fund config file must contain a JSON object")
    nested = payload.get("fund_config")
    if nested is not None:
        if not isinstance(nested, dict):
            raise ValueError("fund_config must be a JSON object")
        return nested
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Dry-run or atomically apply a tenant-scoped legacy published-policy "
            "upgrade from an operator-selected current fund configuration."
        )
    )
    parser.add_argument("--user-id", required=True)
    parser.add_argument(
        "--fund-config-file",
        type=Path,
        required=True,
        help="JSON fund_config object (or settings object containing fund_config)",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    try:
        report = upgrade_published_policy(
            args.user_id,
            fund_config=_selected_fund_config(args.fund_config_file),
            apply=bool(args.apply),
        )
    except Exception as exc:
        error = {
            "status": "failed",
            "error": type(exc).__name__,
            "detail": str(exc),
        }
        if args.as_json:
            print(json.dumps(error, sort_keys=True))
        else:
            print(f"Published-policy upgrade failed: {error['detail']}", file=sys.stderr)
        return 1

    payload = report.model_dump(mode="json")
    if args.as_json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(
            f"Published-policy upgrade {payload['mode']}: {payload['status']} "
            f"({payload.get('old_policy_id') or 'none'} -> {payload['new_policy_id']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
