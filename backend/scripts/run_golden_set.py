#!/usr/bin/env python3
"""Run an offline, versioned institutional evaluation corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from evaluation.golden_set import run_golden_set


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="v1")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    result = run_golden_set(args.version)
    if args.as_json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(
            f"Golden set {result['version']}: "
            f"{result['passed']} passed, {result['failed']} failed"
        )
        for case in result["cases"]:
            print(f"- {case['case_id']}: {case['status']}")
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
